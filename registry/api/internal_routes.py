"""
Internal API routes for virtual MCP server session management.

These endpoints are called by the Lua router via ngx.location.capture
and are protected by nginx 'internal' directive -- they are NOT accessible
from external clients.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException

from registry.repositories.factory import get_backend_session_repository
from registry.schemas.backend_session_models import (
    CreateClientSessionRequest,
    CreateClientSessionResponse,
    GetBackendSessionResponse,
    StoreSessionRequest,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter()


def _get_repo():
    """Get backend session repository or raise 503."""
    repo = get_backend_session_repository()
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="Backend session repository not available",
        )
    return repo


@router.post(
    "/internal/sessions/client",
    response_model=CreateClientSessionResponse,
    status_code=201,
)
async def create_client_session(
    request: CreateClientSessionRequest,
):
    """Create a new client session and return the generated session ID.

    Called by Lua router on MCP 'initialize' requests.
    Generates a vs-<uuid4> client session ID, stores it in MongoDB,
    and returns it to be set as the Mcp-Session-Id response header.
    """
    repo = _get_repo()

    client_session_id = f"vs-{uuid.uuid4().hex}"

    await repo.create_client_session(
        client_session_id=client_session_id,
        user_id=request.user_id,
        virtual_server_path=request.virtual_server_path,
    )

    logger.info(
        f"Created client session {client_session_id} "
        f"for user={request.user_id} path={request.virtual_server_path}"
    )

    return CreateClientSessionResponse(client_session_id=client_session_id)


@router.get(
    "/internal/sessions/client/{client_session_id}",
    status_code=200,
)
async def validate_client_session(
    client_session_id: str,
):
    """Validate that a client session exists.

    Returns 200 if valid, 404 if not found or expired.
    Also bumps last_used_at to keep the session alive.
    """
    repo = _get_repo()

    is_valid = await repo.validate_client_session(client_session_id)
    if not is_valid:
        raise HTTPException(status_code=404, detail="Client session not found")

    return {"status": "valid"}


@router.get(
    "/internal/sessions/backend/{session_key:path}",
    response_model=GetBackendSessionResponse,
)
async def get_backend_session(
    session_key: str,
):
    """Look up a backend session by compound key.

    The session_key is '<client_session_id>:<backend_key>'.
    Returns the backend_session_id if found, 404 otherwise.
    Also bumps last_used_at atomically.
    """
    repo = _get_repo()

    # Split compound key at first ':'
    parts = session_key.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid session key format. Expected '<client_session_id>:<backend_key>'",
        )

    client_session_id, backend_key = parts

    backend_session_id = await repo.get_backend_session(
        client_session_id=client_session_id,
        backend_key=backend_key,
    )

    if backend_session_id is None:
        raise HTTPException(status_code=404, detail="Backend session not found")

    return GetBackendSessionResponse(backend_session_id=backend_session_id)


@router.put(
    "/internal/sessions/backend/{session_key:path}",
    status_code=200,
)
async def store_backend_session(
    session_key: str,
    request: StoreSessionRequest,
):
    """Store or update a backend session.

    The session_key is '<client_session_id>:<backend_key>'.
    Upserts the session document in MongoDB.
    """
    repo = _get_repo()

    # Split compound key at first ':'
    parts = session_key.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid session key format. Expected '<client_session_id>:<backend_key>'",
        )

    client_session_id, backend_key = parts

    await repo.store_backend_session(
        client_session_id=client_session_id,
        backend_key=backend_key,
        backend_session_id=request.backend_session_id,
        user_id=request.user_id,
        virtual_server_path=request.virtual_server_path,
    )

    return {"status": "stored"}


@router.delete(
    "/internal/sessions/backend/{session_key:path}",
    status_code=200,
)
async def delete_backend_session(
    session_key: str,
):
    """Delete a stale backend session.

    Called by Lua router when a backend rejects a cached session ID
    (e.g., after backend restart). The router will then re-initialize.
    """
    repo = _get_repo()

    # Split compound key at first ':'
    parts = session_key.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid session key format. Expected '<client_session_id>:<backend_key>'",
        )

    client_session_id, backend_key = parts

    await repo.delete_backend_session(
        client_session_id=client_session_id,
        backend_key=backend_key,
    )

    return {"status": "deleted"}
