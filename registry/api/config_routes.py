"""Configuration API endpoint for deployment mode awareness."""

from typing import Any, Dict

from fastapi import APIRouter

from ..core.config import settings, DeploymentMode, RegistryMode

router = APIRouter()


@router.get(
    "",
    summary="Get registry configuration",
    description="Returns the current deployment mode, registry mode, and enabled features",
)
async def get_config() -> Dict[str, Any]:
    """Get current registry configuration."""
    return {
        "deployment_mode": settings.deployment_mode.value,
        "registry_mode": settings.registry_mode.value,
        "nginx_updates_enabled": settings.nginx_updates_enabled,
        "features": {
            "mcp_servers": settings.registry_mode in (
                RegistryMode.FULL,
                RegistryMode.MCP_SERVERS_ONLY,
            ),
            "agents": settings.registry_mode in (
                RegistryMode.FULL,
                RegistryMode.AGENTS_ONLY,
            ),
            "skills": settings.registry_mode in (
                RegistryMode.FULL,
                RegistryMode.SKILLS_ONLY,
            ),
            "federation": settings.registry_mode == RegistryMode.FULL,
            "gateway_proxy": settings.deployment_mode == DeploymentMode.WITH_GATEWAY,
        },
    }
