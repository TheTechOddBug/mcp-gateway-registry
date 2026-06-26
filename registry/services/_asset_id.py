# registry/services/_asset_id.py
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)

MAX_ID_LENGTH: int = 512


class InvalidAssetIdError(ValueError):
    """Raised when a supplied id is empty, too long, or has control characters."""


def resolve_asset_id(supplied_id: str | None) -> str:
    """Return the caller-supplied id if valid and non-empty, else a new uuid4 string.

    Generalizes the federation 'use peer id if present, else generate' idiom to
    every registration path. The server route has no Pydantic card model, so this
    function is where server-side id validation actually happens. Raises
    InvalidAssetIdError on a supplied-but-invalid id; the route maps that to 422.
    """
    if supplied_id is None:
        return str(uuid4())  # omitted entirely -> generate, no behavior change
    stripped = supplied_id.strip()
    if not stripped:
        # Supplied but blank is a *caller error*, not a request to generate one.
        raise InvalidAssetIdError("id must be a non-empty string when provided")
    if len(stripped) > MAX_ID_LENGTH:
        raise InvalidAssetIdError(f"id must be <= {MAX_ID_LENGTH} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in stripped):
        raise InvalidAssetIdError("id must not contain control characters")
    return stripped
