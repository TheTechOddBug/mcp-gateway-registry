"""Unit tests for authentication gating on GET /api/config.

The base config endpoint exposes deployment topology, enabled feature flags,
the active auth provider, coding-assistant list, and UI title. This is internal
configuration that aids reconnaissance, so the endpoint must require an
authenticated session and fail closed for anonymous callers.

Pre-login UI needs (application title, available OAuth providers) are served by
the dedicated unauthenticated ``/api/version`` and ``/api/auth/*`` endpoints, so
gating ``/api/config`` does not break the login flow.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from registry.auth.dependencies import enhanced_auth
from registry.main import app


def _mock_authenticated_user() -> dict:
    """Mock enhanced_auth returning an authenticated (non-admin) user."""
    return {
        "username": "regular-user",
        "groups": ["engineering"],
        "scopes": ["mcp-servers-restricted/read"],
        "auth_method": "oauth2",
        "provider": "keycloak",
        "is_admin": False,
    }


@pytest.mark.unit
class TestConfigEndpointAuth:
    """GET /api/config must require authentication and fail closed."""

    def test_anonymous_request_is_rejected(self) -> None:
        """Anonymous GET /api/config must not return configuration.

        With no session cookie and no dependency override, the request must be
        denied (401) so an unauthenticated caller cannot read deployment mode,
        auth provider, or feature flags. This test FAILS against the previously
        unauthenticated handler (which returned 200 with the full config body).
        """
        app.dependency_overrides.clear()
        client = TestClient(app)
        response = client.get("/api/config")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        body = response.json()
        # Sensitive/reconnaissance fields must never appear in the error body.
        for leaked in ("deployment_mode", "registry_mode", "auth_provider", "features"):
            assert leaked not in body

    def test_authenticated_request_returns_full_config(self) -> None:
        """An authenticated user gets the full configuration payload."""
        app.dependency_overrides[enhanced_auth] = _mock_authenticated_user
        try:
            client = TestClient(app)
            response = client.get("/api/config")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "deployment_mode" in data
            assert "registry_mode" in data
            assert "auth_provider" in data
            assert "features" in data
            assert "ui_title" in data
        finally:
            app.dependency_overrides.clear()


@pytest.mark.unit
class TestPreLoginConfigStillWorks:
    """The pre-login surface must keep working after gating /api/config."""

    def test_version_endpoint_serves_ui_title_anonymously(self) -> None:
        """/api/version stays anonymous and serves the pre-login UI title."""
        app.dependency_overrides.clear()
        client = TestClient(app)
        response = client.get("/api/version")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "ui_title" in data
        assert isinstance(data["ui_title"], str)
        assert data["ui_title"]
