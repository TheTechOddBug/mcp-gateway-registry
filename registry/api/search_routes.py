import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..audit import set_audit_action
from ..auth.dependencies import nginx_proxied_auth
from ..core.config import settings, RegistryMode
from ..repositories.factory import get_search_repository
from ..repositories.interfaces import SearchRepositoryBase
from ..services.agent_service import agent_service
from ..services.server_service import server_service

logger = logging.getLogger(__name__)

router = APIRouter()

EntityType = Literal["mcp_server", "tool", "a2a_agent", "skill"]


def get_search_repo() -> SearchRepositoryBase:
    """Dependency injection function for search repository."""
    return get_search_repository()


class MatchingToolResult(BaseModel):
    """Tool matching result - basic info for display.

    Note: inputSchema is NOT included here to avoid duplication.
    Full tool details including inputSchema are in the tools[] array.
    """

    tool_name: str
    description: str | None = None
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)
    match_context: str | None = None


class SyncMetadata(BaseModel):
    """Metadata for items synced from peer registries."""

    is_federated: bool = False
    source_peer_id: str | None = None
    synced_at: str | None = None
    original_path: str | None = None
    is_orphaned: bool = False
    orphaned_at: str | None = None
    is_read_only: bool = True


class ServerSearchResult(BaseModel):
    path: str
    server_name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    num_tools: int = 0
    is_enabled: bool = False
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    match_context: str | None = None
    matching_tools: list[MatchingToolResult] = Field(default_factory=list)
    sync_metadata: SyncMetadata | None = None


class ToolSearchResult(BaseModel):
    server_path: str
    server_name: str
    tool_name: str
    description: str | None = None
    inputSchema: dict | None = Field(default=None, description="JSON Schema for tool input")
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    match_context: str | None = None


class AgentSearchResult(BaseModel):
    path: str
    agent_name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    trust_level: str | None = None
    visibility: str | None = None
    is_enabled: bool = False
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    match_context: str | None = None
    sync_metadata: SyncMetadata | None = None


class SkillSearchResult(BaseModel):
    path: str
    skill_name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    skill_md_url: str | None = None
    skill_md_raw_url: str | None = None
    version: str | None = None
    author: str | None = None
    visibility: str | None = None
    owner: str | None = None
    is_enabled: bool = False
    health_status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    last_checked_time: str | None = None
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    match_context: str | None = None


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512, description="Natural language query")
    entity_types: list[EntityType] | None = Field(
        default=None, description="Optional entity filters"
    )
    max_results: int = Field(
        default=10, ge=1, le=50, description="Maximum results per entity collection"
    )


class SemanticSearchResponse(BaseModel):
    query: str
    search_mode: str = Field(
        default="hybrid", description="Search mode: 'hybrid' (semantic+lexical) or 'lexical-only'"
    )
    servers: list[ServerSearchResult] = Field(default_factory=list)
    tools: list[ToolSearchResult] = Field(default_factory=list)
    agents: list[AgentSearchResult] = Field(default_factory=list)
    skills: list[SkillSearchResult] = Field(default_factory=list)
    total_servers: int = 0
    total_tools: int = 0
    total_agents: int = 0
    total_skills: int = 0


async def _user_can_access_server(path: str, server_name: str, user_context: dict) -> bool:
    """Validate whether the current user can view the specified server."""
    if user_context.get("is_admin"):
        return True

    accessible_servers = user_context.get("accessible_servers") or []
    if "all" in accessible_servers:
        return True

    if not accessible_servers:
        return False

    try:
        if await server_service.user_can_access_server_path(path, accessible_servers):
            return True
    except Exception:
        # Fall through to string comparisons if server lookup failed
        logger.debug("Unable to validate server path via service for %s", path, exc_info=True)

    technical_name = path.strip("/")
    return technical_name in accessible_servers or (
        server_name and server_name in accessible_servers
    )


async def _user_can_access_agent(agent_path: str, user_context: dict) -> bool:
    """Validate user access for a given agent."""
    if user_context.get("is_admin"):
        return True

    accessible_agents = user_context.get("accessible_agents") or []
    if "all" not in accessible_agents and agent_path not in accessible_agents:
        return False

    agent_card = await agent_service.get_agent_info(agent_path)
    if not agent_card:
        return False

    if agent_card.visibility == "public":
        return True

    if agent_card.visibility == "internal":
        return agent_card.registered_by == user_context.get("username")

    if agent_card.visibility == "group-restricted":
        allowed_groups = set(agent_card.allowed_groups)
        user_groups = set(user_context.get("groups", []))
        return bool(allowed_groups & user_groups)

    return False


async def _user_can_access_skill(
    skill_path: str,
    visibility: str,
    owner: str,
    allowed_groups: list,
    user_context: dict,
) -> bool:
    """Validate user access for a given skill based on visibility.

    Args:
        skill_path: The skill path
        visibility: Skill visibility (public, private, group)
        owner: Skill owner username
        allowed_groups: Groups allowed to access the skill
        user_context: User context with username, groups, is_admin

    Returns:
        True if user can access the skill, False otherwise
    """
    if user_context.get("is_admin"):
        return True

    if visibility == "public":
        return True

    if visibility == "private":
        return owner == user_context.get("username")

    if visibility == "group":
        user_groups = set(user_context.get("groups", []))
        skill_groups = set(allowed_groups or [])
        return bool(user_groups & skill_groups)

    return False


@router.post(
    "/semantic",
    response_model=SemanticSearchResponse,
    summary="Unified semantic search for MCP servers and tools",
)
async def semantic_search(
    http_request: Request,
    request: SemanticSearchRequest,
    user_context: Annotated[dict, Depends(nginx_proxied_auth)],
    search_repo: SearchRepositoryBase = Depends(get_search_repo),
) -> SemanticSearchResponse:
    """
    Run a semantic search against MCP servers (and their tools) using FAISS embeddings.
    """
    # Set audit action for search
    set_audit_action(
        http_request, "search", "search", description=f"Semantic search: {request.query[:50]}..."
    )

    logger.info(
        "Semantic search requested by %s (entities=%s, max=%s)",
        user_context.get("username"),
        request.entity_types or ["mcp_server", "tool"],
        request.max_results,
    )

    try:
        raw_results = await search_repo.search(
            query=request.query,
            entity_types=request.entity_types,
            max_results=request.max_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("FAISS search service unavailable: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is temporarily unavailable. Please try again later.",
        ) from exc

    filtered_servers: list[ServerSearchResult] = []
    for server in raw_results.get("servers", []):
        if not await _user_can_access_server(
            server.get("path", ""),
            server.get("server_name", ""),
            user_context,
        ):
            continue

        matching_tools = [
            MatchingToolResult(
                tool_name=tool.get("tool_name", ""),
                description=tool.get("description"),
                relevance_score=tool.get("relevance_score", 0.0),
                match_context=tool.get("match_context"),
            )
            for tool in server.get("matching_tools", [])
        ]

        # Parse sync_metadata if present
        raw_sync = server.get("sync_metadata")
        sync_meta = SyncMetadata(**raw_sync) if raw_sync else None

        filtered_servers.append(
            ServerSearchResult(
                path=server.get("path", ""),
                server_name=server.get("server_name", ""),
                description=server.get("description"),
                tags=server.get("tags", []),
                num_tools=server.get("num_tools", 0),
                is_enabled=server.get("is_enabled", False),
                relevance_score=server.get("relevance_score", 0.0),
                match_context=server.get("match_context"),
                matching_tools=matching_tools,
                sync_metadata=sync_meta,
            )
        )

    filtered_tools: list[ToolSearchResult] = []
    for tool in raw_results.get("tools", []):
        server_path = tool.get("server_path", "")
        server_name = tool.get("server_name", "")
        if not await _user_can_access_server(server_path, server_name, user_context):
            continue

        filtered_tools.append(
            ToolSearchResult(
                server_path=server_path,
                server_name=server_name,
                tool_name=tool.get("tool_name", ""),
                description=tool.get("description"),
                inputSchema=tool.get("inputSchema"),
                relevance_score=tool.get("relevance_score", 0.0),
                match_context=tool.get("match_context"),
            )
        )

    filtered_agents: list[AgentSearchResult] = []
    for agent in raw_results.get("agents", []):
        agent_path = agent.get("path", "")
        if not agent_path:
            continue

        if not await _user_can_access_agent(agent_path, user_context):
            continue

        agent_card_obj = await agent_service.get_agent_info(agent_path)
        agent_card_dict = (
            agent_card_obj.model_dump() if agent_card_obj else agent.get("agent_card", {})
        )

        tags = agent_card_dict.get("tags", []) or agent.get("tags", [])
        raw_skills = agent_card_dict.get("skills", []) or agent.get("skills", [])
        skills = [skill.get("name") if isinstance(skill, dict) else skill for skill in raw_skills]

        # Parse sync_metadata from search result or agent card
        raw_agent_sync = agent.get("sync_metadata") or agent_card_dict.get("sync_metadata")
        agent_sync_meta = SyncMetadata(**raw_agent_sync) if raw_agent_sync else None

        filtered_agents.append(
            AgentSearchResult(
                path=agent_path,
                agent_name=agent_card_dict.get(
                    "name", agent.get("agent_name", agent_path.strip("/"))
                ),
                description=agent_card_dict.get("description", agent.get("description")),
                tags=tags or [],
                skills=[s for s in skills if s],
                trust_level=agent_card_dict.get("trust_level"),
                visibility=agent_card_dict.get("visibility"),
                is_enabled=agent_card_dict.get("is_enabled", False),
                relevance_score=agent.get("relevance_score", 0.0),
                match_context=agent.get("match_context") or agent_card_dict.get("description"),
                sync_metadata=agent_sync_meta,
            )
        )

    filtered_skills: list[SkillSearchResult] = []
    for skill in raw_results.get("skills", []):
        skill_path = skill.get("path", "")
        if not skill_path:
            continue

        visibility = skill.get("visibility", "public")
        owner = skill.get("owner", "")
        allowed_groups = skill.get("allowed_groups", [])

        if not await _user_can_access_skill(
            skill_path, visibility, owner, allowed_groups, user_context
        ):
            continue

        filtered_skills.append(
            SkillSearchResult(
                path=skill_path,
                skill_name=skill.get("skill_name", skill_path.strip("/")),
                description=skill.get("description"),
                tags=skill.get("tags", []),
                skill_md_url=skill.get("skill_md_url"),
                skill_md_raw_url=skill.get("skill_md_raw_url"),
                version=skill.get("version"),
                author=skill.get("author"),
                visibility=visibility,
                owner=owner,
                is_enabled=skill.get("is_enabled", False),
                health_status=skill.get("health_status", "unknown"),
                last_checked_time=skill.get("last_checked_time"),
                relevance_score=skill.get("relevance_score", 0.0),
                match_context=skill.get("match_context"),
            )
        )

    # Filter results based on registry mode
    # In skills-only mode, only return skills; in servers-only mode, only return servers, etc.
    mode = settings.registry_mode

    if mode == RegistryMode.SKILLS_ONLY:
        # Only skills are enabled
        filtered_servers = []
        filtered_tools = []
        filtered_agents = []
    elif mode == RegistryMode.MCP_SERVERS_ONLY:
        # Only servers and tools are enabled
        filtered_agents = []
        filtered_skills = []
    elif mode == RegistryMode.AGENTS_ONLY:
        # Only agents are enabled
        filtered_servers = []
        filtered_tools = []
        filtered_skills = []
    # In FULL mode, return all results (no filtering needed)

    return SemanticSearchResponse(
        query=request.query.strip(),
        servers=filtered_servers,
        tools=filtered_tools,
        agents=filtered_agents,
        skills=filtered_skills,
        total_servers=len(filtered_servers),
        total_tools=len(filtered_tools),
        total_agents=len(filtered_agents),
        total_skills=len(filtered_skills),
    )
