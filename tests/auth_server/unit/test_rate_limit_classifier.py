"""Unit tests for the /validate rate-limit target classifier (auth_server.server)."""

from unittest.mock import AsyncMock, patch

import pytest

from registry.rate_limiting.models import RateLimitDecision


@pytest.mark.unit
class TestThrottlePassthrough:
    """The /validate throttle must surface as a 403 that nginx rewrites to 429.

    nginx's auth_request module only forwards 401/403 from the subrequest; a 429
    is turned into a 500 at the parent location ("auth request unexpected status:
    429"). So _enforce_rate_limit signals a throttle as a 403 carrying the
    X-RateLimit-* headers (incl. the X-RateLimit-Throttled marker), and the
    @forbidden_error nginx location rewrites it into a real 429 + Retry-After.
    This test is the regression guard for that exact status choice (issue #295).
    """

    async def test_throttle_raises_403_with_marker_header(self):
        """A denied decision raises HTTPException(403) with the throttle headers."""
        from fastapi import HTTPException

        from auth_server.server import _enforce_rate_limit

        denied = RateLimitDecision(
            allowed=False,
            axis="tgt",
            entity_type="mcp_server",
            limit=3,
            remaining=0,
            reset_epoch=1000,
            retry_after=42,
        )
        limiter = AsyncMock()
        limiter.check = AsyncMock(return_value=denied)

        # Force the enforcement path on: feature enabled, limiter returns a deny.
        with (
            patch("rate_limiting_config.RATE_LIMITING_ENABLED", True),
            patch("rate_limiting_config.get_rate_limiter", return_value=limiter),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _enforce_rate_limit(
                    {"username": "alice", "is_admin": False},
                    "https://gw.example.com/mcpgw/mcp",
                    "mcpgw",
                )

        exc = exc_info.value
        # 403 (not 429) so nginx auth_request forwards it instead of 500-ing.
        assert exc.status_code == 403
        assert exc.headers["X-RateLimit-Throttled"] == "1"
        assert exc.headers["X-RateLimit-Limit"] == "3"
        assert exc.headers["Retry-After"] == "42"


@pytest.mark.unit
class TestClassifyTarget:
    """Tests for _classify_rate_limit_target."""

    def test_mcp_server_target(self):
        """A plain MCP server path classifies as mcp_server."""
        from auth_server.server import _classify_rate_limit_target

        entity_type, name = _classify_rate_limit_target(
            "https://gw.example.com/mcpgw/mcp", "mcpgw"
        )
        assert entity_type == "mcp_server"
        assert name == "mcpgw"

    def test_a2a_agent_target(self):
        """An /agent/ path classifies as a2a_agent with the agent path."""
        from auth_server.server import _classify_rate_limit_target

        entity_type, name = _classify_rate_limit_target(
            "https://gw.example.com/agent/booking-agent/", "booking-agent"
        )
        assert entity_type == "a2a_agent"
        assert name == "/booking-agent"

    def test_no_target(self):
        """A request with neither an agent path nor a server name yields (None, None)."""
        from auth_server.server import _classify_rate_limit_target

        entity_type, name = _classify_rate_limit_target(None, None)
        assert entity_type is None
        assert name is None
