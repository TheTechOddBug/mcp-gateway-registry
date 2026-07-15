"""Single source of truth for per-type custom-entity UI-Scope naming.

Each custom entity TYPE, when created, mints a per-type UI-Scope set that gates
discovery and mutation of that type's records, bringing custom entities to
parity with servers/agents. The scope-name convention lives here so it
is never duplicated across the mint path (custom_type_routes), the route gates
(custom_entity_routes), the search filter (search_routes), and the backfill migration.

The scope set per type ``<type>`` is exactly:

- ``list_<type>_entity``   -- gates list/get/search + rating view (read-only).
- ``create_<type>_entity`` -- gates record create.
- ``modify_<type>_entity`` -- gates record update.
- ``delete_<type>_entity`` -- gates record delete.

The mutating three match ``ADMIN_ACTION_PREFIXES`` but are intentionally
EXCLUDED from the admin-derivation rule by ``is_admin_conferring_action`` in
``registry.auth.privileged_constants`` (the security boundary lives there, so
this module imports the predicate rather than redefining the exclusion regex).
"""

import re

from ..auth.privileged_constants import is_admin_conferring_action

# The four actions minted per type. Ordering is stable so callers that iterate
# (mint/cleanup) produce a deterministic scope set. ``get`` is folded into
# ``list`` (a single list scope gates both list and get); see D5 in the LLD.
_ENTITY_SCOPE_ACTIONS: tuple[str, ...] = ("list", "create", "modify", "delete")

# Mutating per-type entity scopes only (list_ is read-only and excluded). Mirrors
# the exclusion regex in privileged_constants; used by is_per_type_entity_scope.
_MUTATING_ENTITY_SCOPE_RE = re.compile(r"^(create|modify|delete)_.+_entity$")


def entity_scope(
    action: str,
    type_name: str,
) -> str:
    """Return the UI-Scope name for an action on a custom type.

    Args:
        action: One of ``_ENTITY_SCOPE_ACTIONS`` (list/create/modify/delete).
        type_name: The custom type name (already constrained to
            ``^[a-z0-9_-]+$`` at the route layer).

    Returns:
        The scope name, e.g. ``entity_scope("create", "dataset")`` ->
        ``"create_dataset_entity"``.
    """
    return f"{action}_{type_name}_entity"


def all_entity_scopes(
    type_name: str,
) -> dict[str, list[str]]:
    """Return the full per-type scope set granted to a group's ui_permissions.

    Each scope is granted for ``["all"]`` (all records of that type). The result
    is shaped like a ui_permissions fragment and is merged into a group document
    on type-create (minted to ``mcp-registry-admin``).

    Args:
        type_name: The custom type name.

    Returns:
        Mapping of scope name -> ``["all"]`` for every action in the set.
    """
    return {entity_scope(action, type_name): ["all"] for action in _ENTITY_SCOPE_ACTIONS}


def is_per_type_entity_scope(
    action: str,
) -> bool:
    """Return True if ``action`` is a MUTATING per-type entity scope.

    A mutating per-type entity scope matches ``^(create|modify|delete)_.+_entity$``
    -- exactly the set the admin-derivation rule excludes. Read-only
    ``list_<type>_entity`` returns False here (it is never admin-conferring, so it
    needs no exclusion). This is cross-checked against the boundary predicate:
    every action matched here MUST be non-admin-conferring, which asserts the
    exclusion regex in privileged_constants stays in sync with this one.

    Args:
        action: A UI-Scopes action name.

    Returns:
        True if the action is a mutating per-type entity scope, False otherwise.
    """
    if not _MUTATING_ENTITY_SCOPE_RE.match(action):
        return False
    # Invariant: a mutating entity scope must be excluded from admin derivation.
    # If this ever fails, the two regexes have drifted apart.
    assert not is_admin_conferring_action(action)  # nosec B101 - boundary invariant
    return True
