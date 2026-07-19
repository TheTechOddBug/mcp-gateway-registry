# Why did the Skills or Agents tab go empty, and how do I grant a group access?

After the skill and agent discovery gate landed, discovery of skills and agents is controlled by a `list_` UI permission, the same way MCP servers already worked. This is a fail-closed change: a non-admin user whose group does **not** hold the grant sees **zero** skills or agents, including public ones, and the tab shows a hint like:

> You don't have access to view agents. Agent discovery is managed by your registry administrator. Ask them to grant your group the "list_agents" permission so agents appear here.

Admins are unaffected: they bypass the discovery check and see everything.

## Quick answer

An administrator grants the group the missing discovery scope (`list_skills` or `list_agents`). There are two ways to do it: the IAM UI (per group, no file editing) or the `registry_management.py` CLI (scriptable, good for many groups). For the brand-new `list_skills` scope there is also a one-time backfill script that grants it to the built-in admin group.

## The permissions involved

| Capability | Permission key | Applies to |
| --- | --- | --- |
| See agents in the UI / search | `list_agents` | Agent paths or `"all"` |
| See skills in the UI / search | `list_skills` | Skill paths or `"all"` |

Grant `["all"]` to let the group discover every skill/agent, or a list of specific resource paths to scope discovery to just those. `list_` scopes are read-only, so `["all"]` is safe and does **not** trigger admin auto-promotion (unlike the mutating `modify_`/`delete_`/`toggle_`/`publish_`/`register_`/`create_` prefixes).

## Finding which groups need the grant

To see which groups are missing `list_agents` / `list_skills` across a whole deployment, run the read-only audit. It lists every group, flags the ones missing a discovery scope, and prints the exact fix commands per group. It changes nothing:

```bash
uv run python scripts/audit-discovery-scopes.py \
  --registry-url http://localhost --token-file .token
```

The audit drives `api/registry_management.py` under the hood, so it uses the same auth as the CLI. For a group whose `server_access` contains a reserved wildcard server (`"*"`/`"all"`), it prints the IAM-UI recipe instead of a re-import command, because the import guard refuses wildcard `server_access`. Use `--scope list_skills` to audit just one scope.

## Option 1: Grant via the IAM UI (recommended for one or two groups)

1. Sign in as an administrator and open **Settings > IAM > Groups**.
2. Click the group you want to edit (for example the read-write group your users belong to).
3. In the **UI Permissions** editor, find the discovery scope:
   - For agents, the **`list_agents`** entry.
   - For skills, the **`list_skills`** entry.
4. Turn on the **All** toggle to grant discovery of every resource, or use the multi-select to pick specific records (the record **name** is shown, the record **path** is stored).
5. **Save** the group. Members pick up the change on their next login or token refresh.

See [IAM Settings UI](../iam-settings-ui.md) for the full Groups editor reference.

## Option 2: Grant via the CLI (scriptable, good for many groups)

The `import-group` command **upserts** a group: it creates the group if it does not exist and updates it in place if it does. So the flow is read the current definition, add the scope, re-import.

```bash
export REGISTRY_URL="https://your-registry"
export TOKEN_FILE=".token"   # an admin JWT token file

# 1. See the group's current scope definition
uv run python api/registry_management.py \
  --registry-url "$REGISTRY_URL" \
  --token-file "$TOKEN_FILE" \
  describe-group --name my-group --json > my-group.json
```

Edit `my-group.json` and add the discovery scope under `ui_permissions`:

```json
{
  "scope_name": "my-group",
  "ui_permissions": {
    "list_service": ["all"],
    "list_agents": ["all"],
    "list_skills": ["all"]
  }
}
```

```bash
# 2. Re-import to apply the change (updates the existing group in place)
uv run python api/registry_management.py \
  --registry-url "$REGISTRY_URL" \
  --token-file "$TOKEN_FILE" \
  import-group --file my-group.json
```

To scope discovery to specific resources instead of the whole family, list their paths rather than `"all"`:

```json
{
  "ui_permissions": {
    "list_agents": ["/flight-booking", "/hotel-search"],
    "list_skills": ["/code-review"]
  }
}
```

## Option 3: One-time `list_skills` backfill (new-scope bootstrap)

`list_skills` is a new scope, so no group holds it after upgrade, not even the admin group. Run the backfill once per deployment to grant `list_skills: ["all"]` to the built-in `mcp-registry-admin` group. It is a dry run by default; add `--apply` to make the change.

The simplest place to run it is **inside a running container**, where the registry's own environment (`.env`, `SECRET_KEY`, and the Mongo/DocumentDB service names) is already present:

```bash
# Docker Compose
docker compose exec registry uv run python scripts/backfill-skill-list-scope.py --apply

# Kubernetes / EKS (exec into the registry pod)
kubectl exec -it deploy/registry -- uv run python scripts/backfill-skill-list-scope.py --apply
```

If you run it **outside** the deployment (a host shell, a one-off ECS task, an admin pod that is not the registry), the registry service names may not resolve. Pass the connection explicitly. The password and `SECRET_KEY` are read from the environment only, never as CLI args:

```bash
# MongoDB CE reached directly (skip replica-set discovery that advertises
# internal hostnames); password + SECRET_KEY come from the environment
DOCUMENTDB_PASSWORD=... SECRET_KEY=... \
  uv run python scripts/backfill-skill-list-scope.py --apply \
  --host localhost --username admin --direct-connection \
  --auth-server-url http://localhost:8888

# Amazon DocumentDB (TLS + SCRAM-SHA-1 via --storage-backend documentdb)
DOCUMENTDB_PASSWORD=... SECRET_KEY=... \
  uv run python scripts/backfill-skill-list-scope.py --apply \
  --storage-backend documentdb --tls \
  --host docdb.cluster-xxxx.us-east-1.docdb.amazonaws.com --username admin \
  --auth-server-url https://your-auth-server
```

Run `uv run python scripts/backfill-skill-list-scope.py --help` for the full connection-argument list (`--host`, `--port`, `--database`, `--username`, `--auth-source`, `--tls`, `--direct-connection`, `--storage-backend`, `--auth-server-url`). The same arguments work for `scripts/backfill-custom-entity-scopes.py`.

This only fixes the built-in admin group. Any non-admin group that should see skills still needs `list_skills` granted explicitly via Option 1 or Option 2. There is no equivalent backfill for `list_agents`, because that scope already existed before the gate.

`--auth-server-url` matters when you run the script outside the deployment: after writing the grant, the script asks the auth-server to reload its scope cache. If that URL is not reachable, the grant is still persisted but the running auth-server keeps the old scopes until it is restarted or reloaded.

## Related mutation scopes (owner self-service)

Discovery (`list_`) is separate from mutation. If a non-admin can now *see* skills or agents but can no longer edit, delete, or toggle ones they own, grant the group the matching mutation scope too. Mutations are a dual gate: the caller needs the scope for the resource (or `"all"`) **and** must be an admin or the resource's owner.

| Action | Skill scope | Agent scope |
| --- | --- | --- |
| Edit | `modify_skill` | `modify_agent` |
| Delete | `delete_skill` | `delete_agent` |
| Enable/disable | `toggle_skill` | `toggle_agent` |

Grant these the same way as the discovery scopes (IAM UI or `import-group`). Note that a group which previously managed agents via the server scopes (`modify_service` / `toggle_service`) must be switched to the agent scopes (`modify_agent` / `toggle_agent`), which are now what the agent routes enforce.

## Related documentation

- [Scopes Management](../scopes-mgmt.md) - full scope file format, the complete UI-permissions reference table, and upgrade notes.
- [IAM Settings UI](../iam-settings-ui.md) - the visual Groups editor.
- [How do I create a non-admin group that can register servers but not delete them?](read-write-non-admin-group.md) - a worked example of a scoped read-write group.
