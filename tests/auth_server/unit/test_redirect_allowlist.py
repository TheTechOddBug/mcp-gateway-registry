"""Tests for the exact-match OAuth redirect_uri allowlist.

The auth server validates login-success and logout ``redirect_uri`` targets
before honoring them. When ``OAUTH2_ALLOWED_REDIRECT_URIS`` is configured, an
absolute redirect is permitted ONLY if it exactly matches (normalized) an
allowlisted entry -- a subdomain of the cookie domain that is not on the list
is rejected. When the allowlist is unset, the weaker cookie-domain heuristic is
used for backward compatibility. Relative paths are always allowed.
"""

import pytest

from auth_server.server import (
    _get_allowed_redirect_uris,
    _is_redirect_uri_allowed,
    _normalize_redirect_uri,
)


@pytest.mark.unit
class TestNormalizeRedirectUri:
    """URI normalization used for exact-match comparison."""

    def test_lowercases_scheme_and_host(self):
        assert (
            _normalize_redirect_uri("HTTPS://Registry.Example.COM/login")
            == "https://registry.example.com/login"
        )

    def test_strips_trailing_slash(self):
        assert (
            _normalize_redirect_uri("https://registry.example.com/")
            == "https://registry.example.com"
        )

    def test_drops_default_https_port(self):
        assert (
            _normalize_redirect_uri("https://registry.example.com:443/x")
            == "https://registry.example.com/x"
        )

    def test_keeps_non_default_port(self):
        assert _normalize_redirect_uri("http://localhost:8080/cb") == "http://localhost:8080/cb"

    def test_relative_path_returned_unchanged(self):
        assert _normalize_redirect_uri("/dashboard") == "/dashboard"


@pytest.mark.unit
class TestGetAllowedRedirectUris:
    """Parsing of the comma-separated env allowlist."""

    def test_empty_when_unset(self, monkeypatch):
        monkeypatch.delenv("OAUTH2_ALLOWED_REDIRECT_URIS", raising=False)
        assert _get_allowed_redirect_uris() == set()

    def test_empty_when_blank(self, monkeypatch):
        monkeypatch.setenv("OAUTH2_ALLOWED_REDIRECT_URIS", "   ")
        assert _get_allowed_redirect_uris() == set()

    def test_parses_and_normalizes_entries(self, monkeypatch):
        monkeypatch.setenv(
            "OAUTH2_ALLOWED_REDIRECT_URIS",
            "https://Registry.Example.com/ , https://registry.example.com/login",
        )
        assert _get_allowed_redirect_uris() == {
            "https://registry.example.com",
            "https://registry.example.com/login",
        }


@pytest.mark.unit
class TestRedirectAllowlisted:
    """Allowlist-configured (hardened) mode."""

    @pytest.fixture(autouse=True)
    def _configure(self, monkeypatch):
        monkeypatch.setenv(
            "OAUTH2_ALLOWED_REDIRECT_URIS",
            "https://registry.example.com/,https://registry.example.com/login",
        )
        # A cookie domain that WOULD admit a malicious subdomain under the weak
        # fallback -- proving the allowlist overrides it.
        monkeypatch.setenv("SESSION_COOKIE_DOMAIN", ".example.com")

    def test_exact_match_allowed(self):
        assert _is_redirect_uri_allowed("https://registry.example.com/") is True

    def test_exact_match_allowed_after_normalization(self):
        # Trailing slash difference and case still match a normalized entry.
        assert _is_redirect_uri_allowed("https://Registry.Example.com/login/") is True

    def test_subdomain_of_cookie_domain_not_allowlisted_is_rejected(self):
        # Within .example.com, so the weak fallback would allow it -- but it is
        # not on the exact-match list, so it must be rejected.
        assert _is_redirect_uri_allowed("https://evil.example.com/steal") is False

    def test_unrelated_host_rejected(self):
        assert _is_redirect_uri_allowed("https://attacker.test/cb") is False

    def test_relative_path_always_allowed(self):
        assert _is_redirect_uri_allowed("/dashboard") is True

    def test_non_http_scheme_rejected(self):
        assert _is_redirect_uri_allowed("javascript:alert(1)") is False

    def test_protocol_relative_rejected(self):
        # "//evil.com" would follow off-site despite looking path-like.
        assert _is_redirect_uri_allowed("//evil.com") is False

    def test_backslash_path_rejected(self):
        # Legacy browsers rewrite "\" to "/", turning these into off-site
        # protocol-relative redirects.
        assert _is_redirect_uri_allowed("/\\evil.com") is False
        assert _is_redirect_uri_allowed("/\\\\evil.com") is False
        assert _is_redirect_uri_allowed("\\/evil.com") is False


@pytest.mark.unit
class TestRedirectFallbackWhenAllowlistUnset:
    """Unset allowlist falls back to the cookie-domain heuristic."""

    @pytest.fixture(autouse=True)
    def _configure(self, monkeypatch):
        monkeypatch.delenv("OAUTH2_ALLOWED_REDIRECT_URIS", raising=False)
        monkeypatch.setenv("SESSION_COOKIE_DOMAIN", ".example.com")

    def test_within_cookie_domain_allowed(self):
        # Backward-compatible weak mode: any host within the cookie domain is
        # accepted when no allowlist is configured.
        assert _is_redirect_uri_allowed("https://registry.example.com/x") is True

    def test_relative_path_allowed(self):
        assert _is_redirect_uri_allowed("/login") is True

    def test_outside_cookie_domain_rejected(self):
        assert _is_redirect_uri_allowed("https://attacker.test/cb") is False

    def test_empty_rejected(self):
        assert _is_redirect_uri_allowed("") is False
