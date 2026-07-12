# Rate Limiting: End-to-End Test Guide (issue #295)

A hands-on sequence to verify application-level rate limiting on a running gateway. It walks from backwards-compatibility (nothing configured) through group limits, response headers, OTel metrics + logs, and finally a per-agent (M2M `client_id`) limit.

## Conventions

Run from the repo root. All examples assume the local Docker stack and an admin token file at `./.token`.

```bash
export REG=http://localhost                      # gateway base URL
export TOK=.token                                # admin token file
# The confirmed-working data-plane MCP endpoint in this deployment:
export SRV=http://localhost/airegistry-tools/mcp
```

Two important reminders before you start:

- **`RATE_LIMITING_ENABLED=true`** must be set in `.env` (and the containers rebuilt/restarted) or everything is a no-op.
- **`registry_management.py` global flags go BEFORE the subcommand**: `... --token-file .token --registry-url http://localhost <subcommand> ...`. The test script `call_mcp_tool.py` is flat (flags anywhere).
- **Admin is bypassed** on caller limits, and caller limits only apply to **data-plane** (MCP/A2A) calls, never `/api/*`. So to see a caller limit bite, test with a **non-admin** user or an M2M client, calling an **MCP server**.

---

## Step 1 — Backwards compatibility (no config, no groups)

With no definitions and no memberships, every call must pass. Confirm the feature is inert until used.

```bash
# A burst of 100 calls should all be 200 (0 throttled).
uv run python tests/scripts/call_mcp_tool.py \
  --server-url "$SRV" --tool healthcheck --tool-args '{}' \
  --token-file "$TOK" --registry-url "$REG" --count 100
```

Expected: `Done: 100 call(s) ..., 0 throttled (429), 100 succeeded/other`. If you see 429s here, something is already configured — list and clear it:

```bash
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" rate-limit-list
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" rate-limit-member-list
```

---

## Step 2 — Create two groups and verify a per-minute limit

Create a group with a **25 req/min** user limit (above the 20/min user floor), plus a second group with a wider daily volume cap. A definition below the floor on a short window is rejected (see Step 6).

```bash
# Group A: 25/min burst for users
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-set --axis caller --entity-type group --name rl-test \
  --user-max-requests 25 --window-seconds 60

# Group A also gets a daily volume cap (long window, floor does not apply)
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-set --axis caller --entity-type group --name rl-test \
  --user-max-requests 1000 --window-seconds 86400

# Group B: a second, independent group (e.g. a tighter power-user tier)
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-set --axis caller --entity-type group --name rl-test-strict \
  --user-max-requests 30 --window-seconds 60

uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" rate-limit-list
```

Map a **non-admin** test user into `rl-test` (do NOT use admin — admins bypass caller limits), then drive calls **as that user** (use that user's token file):

```bash
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-member-set --subject-type user --subject <test-username> --groups rl-test

# As the test user (their own token), a 30-call burst against the 25/min limit:
uv run python tests/scripts/call_mcp_tool.py \
  --server-url "$SRV" --tool healthcheck --tool-args '{}' \
  --token-file .token-testuser --registry-url "$REG" --count 30
```

Expected: 25× `200`, then `429 (rate limited)`. The per-minute (burst) gate is the tightest, so it trips first.

### Multiple limits at once (burst + volume)

Because `rl-test` now has both a 25/min and a 1000/day limit, both are enforced as independent gates. Within a minute the 25/min gate governs; the daily counter only advances on **allowed** requests (a burst-denied request does not consume the daily budget). To watch the daily gate, lower it temporarily (e.g. `--user-max-requests 20 --window-seconds 86400` sits below neither floor since 86400 > 60s) and drive > 20 allowed calls across minutes.

---

## Step 3 — Verify the 429 response headers

The script prints the rate-limit headers on each line; to see them raw, use curl with `X-Authorization` (the header nginx's `auth_request` reads):

```bash
TOKEN=$(python3 -c "import json;r=open('.token-testuser').read().strip().strip(chr(2)).strip();i=r.rfind('}');print(json.loads(r[:i+1])['tokens']['access_token'])")

# Fire enough to trip, then inspect the throttled response headers:
for i in $(seq 1 30); do
  curl -s -D - -o /dev/null -X POST "$SRV" \
    -H "X-Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"healthcheck","arguments":{}}}' \
  | grep -iE "^HTTP|^x-ratelimit|^retry-after"
done | sort | uniq -c
```

On a throttled request you should see:

```
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 25
X-RateLimit-Remaining: 0
X-RateLimit-Reset: <epoch>
Retry-After: <seconds>
```

---

## Step 4 — Verify OTel metrics (Prometheus)

Enforcement runs in the **auth-server**, which exports Prometheus metrics on `:9464`; the in-cluster Prometheus (job `mcp-auth-server`) scrapes it and is exposed at `http://localhost:9090`.

**Scrape the auth-server exporter directly:**

```bash
docker exec mcp-gateway-registry-auth-server-1 \
  sh -c 'curl -s localhost:9464/metrics' | grep -E "mcpgw_rate_limit"
```

**Or query Prometheus** (browser: `http://localhost:9090/graph`, or curl):

```bash
# how many throttles, by axis/entity_type/window
curl -s 'http://localhost:9090/api/v1/query?query=mcpgw_rate_limit_throttled_total' | jq '.data.result'

# total gate checks (allow vs deny)
curl -s 'http://localhost:9090/api/v1/query?query=mcpgw_rate_limit_checks_total' | jq '.data.result'

# backend op latency (histogram) — the per-op counter-store round trip
curl -s 'http://localhost:9090/api/v1/query?query=mcpgw_rate_limit_backend_duration_milliseconds_count' | jq '.data.result'

# fail-open events (should be 0 in a healthy run)
curl -s 'http://localhost:9090/api/v1/query?query=mcpgw_rate_limit_errors_total' | jq '.data.result'
```

You should see `mcpgw_rate_limit_throttled_total{axis="clr",entity_type="group",window_seconds="60"}` increment by the number of 429s from Steps 2-3, and `..._checks_total` increment for every gate evaluation.

---

## Step 5 — Verify logs / trace messages

The limiter logs a WARNING on each throttle (with the bounded, non-PII fields) and the limiter initializes with an INFO line on first use:

```bash
# Throttle events
docker logs mcp-gateway-registry-auth-server-1 --since 10m 2>&1 | grep "rate-limit throttled"
# -> ... rate-limit throttled: axis=clr entity_type=group name=<user> limit=25/60s

# Limiter initialization (backend, fail_open, cache TTL, timeout)
docker logs mcp-gateway-registry-auth-server-1 2>&1 | grep -i "Rate limiter initialized"

# Fail-open events (backend errors), if any
docker logs mcp-gateway-registry-auth-server-1 --since 10m 2>&1 | grep "rate-limit backend error"
```

For distributed traces, the auth-server is OTel-instrumented; if an OTLP endpoint is configured (`OTEL_EXPORTER_OTLP_ENDPOINT`), the `/validate` spans carry the request attributes. The rate-limit decision is visible in the WARNING logs above regardless.

---

## Step 6 — Verify the floor safeguards

Confirm a too-tight caller limit is rejected at config time (this is what prevents the earlier admin lockout):

```bash
# User number below the 20/min floor on a 60s window -> 400 rejected
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-set --axis caller --entity-type group --name rl-floor-test \
  --user-max-requests 3 --window-seconds 60
# -> "user_max_requests 3 is below the user floor of 20/min ..."

# Agent number below the 10/min floor -> 400 rejected
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-set --axis caller --entity-type group --name rl-floor-test \
  --agent-max-requests 2 --window-seconds 60
# -> "agent_max_requests 2 is below the agent floor of 10/min ..."
```

Also confirm the **admin is never throttled** (caller-axis) and the **dashboard/API is never throttled**: while a caller limit is active on your user, the registry UI and `/api/*` calls keep working — caller limits apply to data-plane MCP/A2A calls only.

---

## Step 7 — Per-agent (M2M `client_id`) limit

Create an M2M service account in Keycloak, get a `client_credentials` token, map its `client_id` into a group, and verify the agent limit is enforced.

**1. Create the M2M service account** (Keycloak admin helper):

```bash
# Creates a confidential client with a service account in the mcp-gateway realm.
bash keycloak/setup/setup-m2m-service-account.sh
# Note the printed client_id and client secret. Or read all client credentials:
bash keycloak/setup/get-all-client-credentials.sh
```

**2. Get a token for that client_id/secret** (client_credentials grant):

```bash
bash keycloak/setup/generate-agent-token.sh rl-agent \
  --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET> \
  --keycloak-url https://mcpgateway.ddns.net --realm mcp-gateway
# writes a token file, e.g. .oauth-tokens/rl-agent.json
```

**3. Map that client_id into a group with an agent limit** (>= the 10/min agent floor):

```bash
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-set --axis caller --entity-type group --name rl-agents \
  --agent-max-requests 10 --window-seconds 60

uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-member-set --subject-type client --subject <CLIENT_ID> --groups rl-agents
```

**4. Drive calls as that agent and confirm the agent limit trips:**

```bash
uv run python tests/scripts/call_mcp_tool.py \
  --server-url "$SRV" --tool healthcheck --tool-args '{}' \
  --token-file .oauth-tokens/rl-agent.json --registry-url "$REG" --count 15
```

Expected: 10× `200`, then `429`. The limiter keys the counter on the agent's `client_id`, picks the group's **agent** number (10), and the `mcpgw_rate_limit_throttled_total{axis="clr",entity_type="group"}` metric increments (the throttle log shows `name=<client_id>`).

---

## Cleanup

```bash
# Remove memberships
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-member-delete --id user:<test-username>
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-member-delete --id client:<CLIENT_ID>

# Remove definitions (list first to get exact ids)
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" rate-limit-list
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-delete --id caller:group:rl-test:60
uv run python api/registry_management.py --token-file "$TOK" --registry-url "$REG" \
  rate-limit-delete --id caller:group:rl-test:86400
# ...repeat for rl-test-strict / rl-agents
```

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| All 200s even with a limit + membership | `RATE_LIMITING_ENABLED` not `true` on the containers; or you tested as **admin** (bypassed); or you hit `/api/*` (control-plane, exempt) instead of an MCP server. |
| `member-set` returns 404 | Containers predate the memberships build; rebuild. |
| Login/dashboard breaks | Should not happen now (data-plane-only scope + admin bypass). If it does, a caller limit is somehow applying to `/api/*` — capture the auth-server logs. |
| Metrics missing in Prometheus | Scrape `auth-server:9464/metrics` directly; if present there but not in Prometheus, check the `mcp-auth-server` job. Enforcement is in auth-server, not registry. |
| 429 on the very first call | The limit is below what the UI's parallel calls need, or a stale ~30s cache — wait 30s or restart auth-server. |
