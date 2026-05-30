#!/usr/bin/env python3
"""Live smoke test for the agent PUT-update path and the async batch endpoint.

Runs against a deployed registry (through nginx, port 80 by default) and
exercises two flows end to end:

1. PUT update path. Registers a fresh agent, fetches it (capturing the ETag),
   PUT-updates a field, and verifies the change took effect on a re-GET.

2. Async batch path. Submits a single batch job mixing register/patch/delete
   items to POST /api/agents/batch, then polls GET /api/agents/batch/{job_id}
   until the job reaches a terminal state, reporting per-item results.

Everything created is cleaned up at the end (best effort), unless --keep is set.

Auth mirrors cli/agent_mgmt.py: a JWT Bearer token is loaded from
.oauth-tokens/ingress.json by default, or supplied via --token / $AGENT_TOKEN.

Usage:
    uv run python scripts/test_agent_batch_live.py
    uv run python scripts/test_agent_batch_live.py --base-url https://registry.example.com
    uv run python scripts/test_agent_batch_live.py --token "$AGENT_TOKEN" --keep
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger("agent-batch-live")

DEFAULT_BASE_URL: str = "http://localhost"  # Through nginx (port 80), not direct :7860
DEFAULT_TOKEN_FILE: str = ".oauth-tokens/ingress.json"
API_BASE: str = "/api/agents"
REQUEST_TIMEOUT: int = 30
TERMINAL_STATES: frozenset[str] = frozenset({"succeeded", "partial", "failed"})


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Summary:
    base_url: str
    checks: list[CheckResult] = field(default_factory=list)
    created_paths: list[str] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> bool:
        self.checks.append(CheckResult(name=name, passed=passed, detail=detail))
        marker = "PASS" if passed else "FAIL"
        logger.info(f"[{marker}] {name}{f' — {detail}' if detail else ''}")
        return passed


def _load_token(token_file: str) -> str:
    """Load a JWT Bearer token from a credentials JSON file."""
    abs_path = os.path.abspath(token_file)
    with open(abs_path) as f:
        data = json.load(f)
    token = data.get("access_token") or data.get("token")
    if not token:
        raise ValueError(f"No access_token/token found in {abs_path}")
    logger.info(f"Token loaded from {abs_path} (length {len(token)})")
    return token


def _resolve_token(
    cli_token: str | None,
    token_file: str,
) -> str:
    """Resolve the Bearer token from --token, $AGENT_TOKEN, or the token file."""
    if cli_token:
        logger.info("Using token from --token argument")
        return cli_token

    env_token = os.getenv("AGENT_TOKEN")
    if env_token:
        logger.info("Using token from $AGENT_TOKEN")
        return env_token

    return _load_token(token_file)


def _request(
    session: requests.Session,
    method: str,
    url: str,
    json_body: dict | None = None,
    extra_headers: dict[str, str] | None = None,
) -> requests.Response:
    """Issue an authenticated request and log a concise summary."""
    headers = dict(extra_headers or {})
    logger.info(f"-> {method} {url}")
    response = session.request(
        method=method,
        url=url,
        json=json_body,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    logger.info(f"<- {response.status_code} ({len(response.content)} bytes)")
    if response.status_code >= 400:
        try:
            logger.warning(f"   body: {json.dumps(response.json())[:500]}")
        except ValueError:
            logger.warning(f"   body: {response.text[:500]}")
    return response


def _register_payload(
    name: str,
    path: str,
    description: str,
) -> dict:
    """Build a minimal valid AgentRegistrationRequest body."""
    return {
        "name": name,
        "path": path,
        "description": description,
        "url": f"http://{path.strip('/')}.invalid:9000/",
        "supportedProtocol": "other",
        "version": "0.0.1",
        "tags": ["batch-live-test"],
        "skills": [
            {
                "id": "echo",
                "name": "Echo",
                "description": "Echoes input back.",
                "tags": [],
            }
        ],
    }


def _run_put_flow(
    session: requests.Session,
    base_url: str,
    summary: Summary,
) -> None:
    """Register an agent, PUT-update it, and verify the change."""
    run_id = uuid.uuid4().hex[:8]
    path = f"/batch-live-put-{run_id}"
    name = f"Batch Live PUT {run_id}"

    reg = _request(
        session,
        "POST",
        f"{base_url}{API_BASE}/register",
        json_body=_register_payload(name, path, "Original description"),
    )
    if not summary.add(
        "PUT flow: register agent", reg.status_code == 201, f"HTTP {reg.status_code}"
    ):
        return
    summary.created_paths.append(path)

    get_before = _request(session, "GET", f"{base_url}{API_BASE}{path}")
    etag = get_before.headers.get("ETag")
    summary.add(
        "PUT flow: GET returns ETag",
        bool(etag),
        f"ETag={etag}",
    )

    updated_desc = "Updated description via PUT"
    put = _request(
        session,
        "PUT",
        f"{base_url}{API_BASE}{path}",
        json_body=_register_payload(name, path, updated_desc),
    )
    if not summary.add("PUT flow: update agent", put.status_code == 200, f"HTTP {put.status_code}"):
        return

    get_after = _request(session, "GET", f"{base_url}{API_BASE}{path}")
    actual_desc = get_after.json().get("description") if get_after.ok else None
    summary.add(
        "PUT flow: description updated",
        actual_desc == updated_desc,
        f"description={actual_desc!r}",
    )
    new_etag = get_after.headers.get("ETag")
    summary.add(
        "PUT flow: ETag changed after update",
        bool(new_etag) and new_etag != etag,
        f"{etag} -> {new_etag}",
    )


def _poll_batch_job(
    session: requests.Session,
    status_url: str,
    timeout_s: float,
    interval_s: float,
) -> dict | None:
    """Poll a batch job until it reaches a terminal state or times out."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = _request(session, "GET", status_url)
        if not resp.ok:
            logger.warning(f"   poll returned HTTP {resp.status_code}")
            return None
        job = resp.json()
        state = job.get("state")
        logger.info(
            f"   job {job.get('job_id')} state={state} "
            f"succeeded={job.get('succeeded')} failed={job.get('failed')}/{job.get('total')}"
        )
        if state in TERMINAL_STATES:
            return job
        time.sleep(interval_s)
    logger.error("   batch job did not reach a terminal state before timeout")
    return None


def _run_batch_flow(
    session: requests.Session,
    base_url: str,
    summary: Summary,
    poll_timeout_s: float,
    poll_interval_s: float,
) -> None:
    """Submit a mixed batch job and verify per-item outcomes."""
    run_id = uuid.uuid4().hex[:8]
    seed_path = f"/batch-live-seed-{run_id}"
    new_path = f"/batch-live-new-{run_id}"
    seed_name = f"Batch Live Seed {run_id}"

    # Seed an agent that the batch will patch and delete.
    seed = _request(
        session,
        "POST",
        f"{base_url}{API_BASE}/register",
        json_body=_register_payload(seed_name, seed_path, "Seed agent for batch"),
    )
    if not summary.add(
        "Batch flow: seed agent registered",
        seed.status_code == 201,
        f"HTTP {seed.status_code}",
    ):
        return
    summary.created_paths.append(seed_path)

    batch_body = {
        "idempotency_key": f"batch-live-{run_id}",
        "items": [
            {
                "op": "register",
                "card": _register_payload(f"Batch Live New {run_id}", new_path, "Created by batch"),
            },
            {
                "op": "patch",
                "path": seed_path,
                "card": {"description": "Patched by batch"},
            },
            {
                "op": "delete",
                "path": seed_path,
            },
        ],
    }

    submit = _request(
        session,
        "POST",
        f"{base_url}{API_BASE}/batch",
        json_body=batch_body,
    )
    if not summary.add(
        "Batch flow: submit accepted (202)",
        submit.status_code == 202,
        f"HTTP {submit.status_code}",
    ):
        return

    payload = submit.json()
    status_url = f"{base_url}{payload['status_url']}"
    # Track the register item's path so cleanup removes it even if delete ran.
    summary.created_paths.append(new_path)

    job = _poll_batch_job(session, status_url, poll_timeout_s, poll_interval_s)
    if not summary.add("Batch flow: job reached terminal state", job is not None):
        return

    summary.add(
        "Batch flow: all 3 items succeeded",
        job.get("state") == "succeeded" and job.get("succeeded") == 3,
        f"state={job.get('state')} succeeded={job.get('succeeded')}/{job.get('total')}",
    )

    results = {r["op"]: r for r in job.get("results", [])}
    for op, r in results.items():
        if r.get("status", 0) >= 400:
            logger.warning(f"   item op={op} status={r.get('status')} error={r.get('error')}")
    summary.add(
        "Batch flow: register item ok",
        results.get("register", {}).get("status") in (200, 201),
        f"status={results.get('register', {}).get('status')}",
    )
    summary.add(
        "Batch flow: patch item ok",
        results.get("patch", {}).get("status") == 200,
        f"status={results.get('patch', {}).get('status')}",
    )
    summary.add(
        "Batch flow: delete item ok",
        results.get("delete", {}).get("status") in (200, 204),
        f"status={results.get('delete', {}).get('status')}",
    )


def _cleanup(
    session: requests.Session,
    base_url: str,
    paths: list[str],
) -> None:
    """Best-effort delete of every agent created during the run."""
    for path in paths:
        resp = _request(session, "DELETE", f"{base_url}{API_BASE}{path}")
        if resp.status_code in (200, 204, 404):
            logger.info(f"   cleaned up {path} (HTTP {resp.status_code})")
        else:
            logger.warning(f"   cleanup of {path} returned HTTP {resp.status_code}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Live smoke test for agent PUT-update and async batch endpoints.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Registry base URL through nginx (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="JWT Bearer token. Falls back to $AGENT_TOKEN, then the token file.",
    )
    parser.add_argument(
        "--token-file",
        default=DEFAULT_TOKEN_FILE,
        help=f"Path to credentials JSON (default: {DEFAULT_TOKEN_FILE})",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=60.0,
        help="Seconds to wait for the batch job to finish (default: 60)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between batch status polls (default: 2)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Do not delete agents created during the run",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    base_url = args.base_url.rstrip("/")

    token = _resolve_token(args.token, args.token_file)
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )

    summary = Summary(base_url=base_url)
    try:
        _run_put_flow(session, base_url, summary)
        _run_batch_flow(session, base_url, summary, args.poll_timeout, args.poll_interval)
    finally:
        if args.keep:
            logger.info(f"--keep set; leaving {len(summary.created_paths)} agent(s) in place")
        elif summary.created_paths:
            logger.info(f"Cleaning up {len(summary.created_paths)} agent(s)...")
            _cleanup(session, base_url, summary.created_paths)

    passed = sum(1 for c in summary.checks if c.passed)
    total = len(summary.checks)
    logger.info(f"Summary: {passed}/{total} checks passed against {base_url}")
    for check in summary.checks:
        marker = "PASS" if check.passed else "FAIL"
        logger.info(f"  [{marker}] {check.name}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
