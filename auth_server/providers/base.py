"""Base authentication provider interface."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @abstractmethod
    def validate_token(self, token: str, **kwargs: Any) -> dict[str, Any]:
        """Validate an access token and return user info.

        Args:
            token: The access token to validate
            **kwargs: Additional provider-specific arguments

        Returns:
            Dictionary containing:
                - valid: Boolean indicating if token is valid
                - username: User's username
                - email: User's email address
                - groups: List of group memberships
                - scopes: List of token scopes
                - client_id: Client ID that issued the token
                - method: Authentication method used
                - data: Raw token claims/data

        Raises:
            ValueError: If token validation fails
        """
        pass

    @abstractmethod
    def get_jwks(self) -> dict[str, Any]:
        """Get JSON Web Key Set for token validation.

        Returns:
            Dictionary containing the JWKS data

        Raises:
            ValueError: If JWKS cannot be retrieved
        """
        pass

    @abstractmethod
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth2 flow
            redirect_uri: Redirect URI used in the authorization request

        Returns:
            Dictionary containing token response:
                - access_token: The access token
                - id_token: The ID token (if available)
                - refresh_token: The refresh token (if available)
                - token_type: Type of token (usually "Bearer")
                - expires_in: Token expiration time in seconds

        Raises:
            ValueError: If code exchange fails
        """
        pass

    @abstractmethod
    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get user information from access token.

        Args:
            access_token: Valid access token

        Returns:
            Dictionary containing user information:
                - username: User's username
                - email: User's email
                - groups: User's group memberships
                - Additional provider-specific fields

        Raises:
            ValueError: If user info cannot be retrieved
        """
        pass

    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str, scope: str | None = None) -> str:
        """Get authorization URL for OAuth2 flow.

        Args:
            redirect_uri: URI to redirect to after authorization
            state: State parameter for CSRF protection
            scope: Optional scope parameter (defaults to provider's default)

        Returns:
            Full authorization URL
        """
        pass

    @abstractmethod
    def get_logout_url(self, redirect_uri: str) -> str:
        """Get logout URL.

        Args:
            redirect_uri: URI to redirect to after logout

        Returns:
            Full logout URL
        """
        pass

    @abstractmethod
    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            Dictionary containing new token response

        Raises:
            ValueError: If token refresh fails
        """
        pass

    @abstractmethod
    def validate_m2m_token(self, token: str) -> dict[str, Any]:
        """Validate a machine-to-machine token.

        Args:
            token: The M2M access token to validate

        Returns:
            Dictionary containing validation result

        Raises:
            ValueError: If token validation fails
        """
        pass

    @abstractmethod
    def get_m2m_token(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """Get a machine-to-machine token using client credentials.

        Args:
            client_id: Optional client ID (uses default if not provided)
            client_secret: Optional client secret (uses default if not provided)
            scope: Optional scope for the token

        Returns:
            Dictionary containing token response

        Raises:
            ValueError: If token generation fails
        """
        pass

    @abstractmethod
    def authorization_server_metadata(self) -> dict[str, Any]:
        """Return the IdP's RFC 8414 Authorization Server Metadata document.

        Implementations should fetch the upstream OIDC/OAuth metadata, normalize
        any provider-specific quirks (e.g. rehoming Cognito's split endpoints onto
        the cognito-domain host), and return a stable RFC 8414-shaped dict.

        Returns:
            Dictionary conforming to RFC 8414 (issuer, authorization_endpoint,
            token_endpoint, jwks_uri, response_types_supported, ...).

        Raises:
            ValueError: If upstream metadata cannot be fetched or normalized.
        """
        pass

    def authorization_server_issuer(self) -> str:
        """Return the canonical issuer URL of the configured authorization server.

        Used as the `authorization_servers` entry in the gateway's RFC 9728
        Protected Resource Metadata document. Default implementation reads the
        `issuer` field from authorization_server_metadata(); providers can
        override for cheaper lookups.
        """
        metadata = self.authorization_server_metadata()
        issuer = metadata.get("issuer")
        if not issuer:
            raise ValueError(
                "Authorization server metadata missing 'issuer' field"
            )
        return issuer

    def protected_resource_metadata(
        self,
        resource: str,
        scopes_supported: list[str],
        resource_documentation: str | None = None,
    ) -> dict[str, Any]:
        """Build an RFC 9728 Protected Resource Metadata document for this gateway.

        The shape is identical across IdPs; the only per-provider input is the
        authorization server issuer (filled in via authorization_server_issuer()).
        Subclasses generally do not need to override this.

        Args:
            resource: Canonical URL of the MCP resource server (gateway).
                Must be HTTPS in non-local environments and have no trailing slash.
            scopes_supported: List of scope strings the gateway recognizes.
                Caller is responsible for sorting/dedup; this method preserves order.
            resource_documentation: Optional URL to operator-facing OAuth docs.

        Returns:
            Dictionary conforming to RFC 9728 §3.
        """
        document: dict[str, Any] = {
            "resource": resource,
            "authorization_servers": [self.authorization_server_issuer()],
            "scopes_supported": list(scopes_supported),
            "bearer_methods_supported": ["header"],
        }
        if resource_documentation:
            document["resource_documentation"] = resource_documentation
        return document
