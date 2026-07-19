#!/usr/bin/env python3
"""Backfill the list_skills discovery scope for the admin group.

Skills gained a per-asset ``list_skills`` DISCOVERY gate (parity with
``list_service`` / ``list_agents`` / ``list_<type>_entity``). Before this
feature there was no such gate: every user (including anonymous) could discover
public skills, and no scope document held a ``list_skills`` key. With the gate
enforced, a caller that does not hold ``list_skills`` (or ``["all"]``) sees ZERO
skills -- including public ones.

This one-time migration grants ``list_skills: ["all"]`` to the
``mcp-registry-admin`` group and triggers an auth-server scope reload.

BEHAVIOR CHANGE (announced): this backfill grants the scope to
``mcp-registry-admin`` ONLY. After upgrade, skills become admin-only until an
admin explicitly grants ``list_skills`` to other groups via the IAM UI ("User
Groups" -> UI Permissions -> List Skills). Skills that were previously visible
to non-admins (public/group-restricted) are hidden from them until such a grant
is made -- this is the intended, stricter parity with ``list_service``.

The migration is IDEMPOTENT: minting is a per-key ``$set`` merge, so re-running
it simply re-writes the same value. Safe to run repeatedly.

Usage:
    # Dry run (default) - report what would be granted
    SECRET_KEY=... DOCUMENTDB_HOST=localhost \\
        uv run python scripts/backfill-skill-list-scope.py

    # Actually apply changes
    SECRET_KEY=... DOCUMENTDB_HOST=localhost \\
        uv run python scripts/backfill-skill-list-scope.py --apply

    # MongoDB CE (single-node) backend
    MCP_STORAGE_BACKEND=mongodb-ce DOCUMENTDB_HOST=localhost \\
        uv run python scripts/backfill-skill-list-scope.py --apply

The script adds the repo root to sys.path itself, so it can be run from any
working directory (e.g. ``uv run python scripts/backfill-skill-list-scope.py``).
The storage backend and connection are read from the same environment the
registry uses (MCP_STORAGE_BACKEND, DOCUMENTDB_HOST, etc.).
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure the repo root (this file's parent's parent) is importable. Running the
# script directly (``python scripts/backfill-skill-list-scope.py``) puts the
# ``scripts/`` directory on sys.path[0], NOT the repo root, so ``import
# registry`` would fail with ModuleNotFoundError. Prepending the repo root makes
# the script self-contained regardless of the working directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

# The built-in registry-admin group that the discovery scope is granted to.
# Matches scope_service.ADMIN_GROUP_NAME; non-admins are granted list_skills
# explicitly via the IAM UI after upgrade.
ADMIN_GROUP_NAME: str = "mcp-registry-admin"

# The discovery scope granted for all skills. Name matches the canonical
# registry.auth.asset_permissions map entry ("skill", "list") -> list_skills.
LIST_SKILLS_SCOPE: str = "list_skills"


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill the list_skills discovery scope to mcp-registry-admin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run (default)
    uv run python scripts/backfill-skill-list-scope.py

    # Apply changes
    uv run python scripts/backfill-skill-list-scope.py --apply
""",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply changes (default is a dry run)",
    )
    return parser.parse_args()


async def _run_backfill(
    dry_run: bool,
) -> dict[str, bool]:
    """Grant list_skills:["all"] to the admin group.

    Args:
        dry_run: If True, only report what would be granted.

    Returns:
        Summary dict with a ``granted`` flag.
    """
    from registry.repositories.factory import get_scope_repository
    from registry.services.scope_service import trigger_auth_server_reload

    scope_repo = get_scope_repository()

    if dry_run:
        logger.info("DRY RUN - no changes will be made")
        logger.info(
            "  Would grant %s: ['all'] to group '%s'",
            LIST_SKILLS_SCOPE,
            ADMIN_GROUP_NAME,
        )
        return {"granted": False}

    # Per-key $set merge (idempotent); does not round-trip the whole doc, so the
    # privileged-write guard is not involved. list_skills is read-only-prefixed
    # and never admin-conferring, so this is not a privileged write regardless.
    granted = await scope_repo.merge_ui_permissions(ADMIN_GROUP_NAME, {LIST_SKILLS_SCOPE: ["all"]})
    if granted:
        logger.info("  Granted %s: ['all'] to group '%s'", LIST_SKILLS_SCOPE, ADMIN_GROUP_NAME)
        reloaded = await trigger_auth_server_reload()
        logger.info("Triggered auth-server scope reload: success=%s", reloaded)
    else:
        logger.error(
            "  Failed to grant %s to group '%s' (group not found or not updated)",
            LIST_SKILLS_SCOPE,
            ADMIN_GROUP_NAME,
        )

    return {"granted": granted}


async def main() -> None:
    """Main entry point for the backfill migration."""
    args = _parse_args()
    dry_run = not args.apply

    logger.info("=" * 60)
    logger.info("Skill list-scope Backfill")
    logger.info("=" * 60)
    logger.info("Mode: %s", "DRY RUN" if dry_run else "APPLY CHANGES")
    logger.info("=" * 60)

    result = await _run_backfill(dry_run)

    logger.info("=" * 60)
    logger.info("Backfill Summary:")
    logger.info("  Granted: %s", result["granted"])
    if dry_run:
        logger.info("  Note: dry run. Use --apply to make changes.")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
