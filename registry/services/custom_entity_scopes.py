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
# ``list`` (a single list scope gates both list and get).
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


def list_grant_allows_type(
    type_name: str,
    granted: list[str],
) -> bool:
    """Return True if a ``list_<type>_entity`` grant opens the WHOLE type.

    The grant value (a ui_permissions list) is interpreted in three tiers,
    mirroring how ``list_agents`` treats agent paths (``"all"`` or a specific
    path):

    - ``"all"``                -> every record of the type (whole-type).
    - the bare ``type_name``   -> every record of the type (whole-type; the
      original per-type semantics, kept backward-compatible so existing
      ``["all"]``/type-name grants and the mint/backfill are unchanged).
    - a record path ``/type/uuid`` -> only that record (per-record; handled by
      :func:`list_grant_record_paths`, NOT here).

    So this returns True only for the whole-type tiers. A purely record-scoped
    grant returns False here (the caller sees only their granted records, not
    the whole type).

    Args:
        type_name: The custom type name.
        granted: The caller's ``list_<type>_entity`` grant list (may be empty).

    Returns:
        True if the grant opens the entire type, False otherwise.
    """
    return "all" in granted or type_name in granted


def list_grant_record_paths(
    type_name: str,
    granted: list[str],
) -> list[str]:
    """Return the specific record paths a ``list_<type>_entity`` grant allows.

    Extracts the per-record tier of the grant: entries shaped like the record's
    synthetic path ``/<type>/<uuid>`` for THIS type. Whole-type tokens
    (``"all"``, the bare type name) are not paths and are excluded here — callers
    check those via :func:`list_grant_allows_type`. Used to build the list-query
    path filter and the single-record/search per-record checks.

    Args:
        type_name: The custom type name (paths must be under ``/<type>/``).
        granted: The caller's ``list_<type>_entity`` grant list.

    Returns:
        The subset of ``granted`` that are record paths for this type.
    """
    prefix = f"/{type_name}/"
    return [g for g in granted if isinstance(g, str) and g.startswith(prefix)]


def resolve_list_grant(
    type_name: str,
    granted: list[str],
) -> tuple[bool, set[str]]:
    """Resolve a ``list_<type>_entity`` grant into its two discovery tiers.

    Single place that classifies a grant list, so every enforcement site
    (dependencies.user_can_list_custom_entity_type, the search discovery loop)
    interprets the tiers identically instead of re-deriving them:

    - Returns ``(True, set())`` when the grant opens the WHOLE type
      (``"all"`` or the bare type name).
    - Returns ``(False, {paths})`` when the grant is record-scoped — the set of
      ``/<type>/<uuid>`` record paths it allows (possibly empty).

    Admin bypass is intentionally NOT handled here (it is a property of the
    caller's context, not of the grant); callers apply it themselves.

    Args:
        type_name: The custom type name.
        granted: The caller's ``list_<type>_entity`` grant list (may be empty).

    Returns:
        ``(whole_type_open, record_paths)``.
    """
    if list_grant_allows_type(type_name, granted):
        return True, set()
    return False, set(list_grant_record_paths(type_name, granted))


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
