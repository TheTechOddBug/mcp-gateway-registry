"""Boundary tests for the pat lifetime helper _resolve_pat_ttl_seconds.

The PAT lifetime is mandatory and bounded: no "never expires", capped at 30
days. This exercises the accept/reject boundary table.
"""

import pytest

import pytest as _pytest

from registry.api.egress_auth_routes import (
    _PAT_MAX_TTL_SECONDS,
    _resolve_pat_header,
    _resolve_pat_ttl_seconds,
)


class TestResolvePatHeader:
    """Validation/defaulting of the pat inject header + value prefix."""

    def test_defaults_to_authorization_bearer(self):
        assert _resolve_pat_header(None, None) == ("Authorization", "Bearer ")

    def test_custom_header_with_empty_prefix(self):
        # GitLab: bare token in a custom header. Explicit "" must be preserved,
        # NOT replaced by the default prefix.
        assert _resolve_pat_header("PRIVATE-TOKEN", "") == ("PRIVATE-TOKEN", "")

    def test_custom_header_keeps_default_prefix_when_omitted(self):
        assert _resolve_pat_header("X-API-Key", None) == ("X-API-Key", "Bearer ")

    @_pytest.mark.parametrize(
        "bad",
        ["bad header", "has:colon", "x" * 65, "with\nnewline", "tab\ttab"],
    )
    def test_bad_header_name_raises(self, bad):
        with _pytest.raises(ValueError):
            _resolve_pat_header(bad, None)

    def test_empty_header_name_defaults_to_authorization(self):
        # An empty/whitespace header name means "use the default", not an error
        # (the edit UI may send an untouched field). It defaults to Authorization.
        assert _resolve_pat_header("", None) == ("Authorization", "Bearer ")
        assert _resolve_pat_header("   ", None) == ("Authorization", "Bearer ")

    def test_prefix_with_crlf_raises(self):
        with _pytest.raises(ValueError):
            _resolve_pat_header("Authorization", "Bearer \r\nX-Evil: 1")

    def test_prefix_too_long_raises(self):
        with _pytest.raises(ValueError):
            _resolve_pat_header("Authorization", "x" * 33)


@pytest.mark.unit
class TestResolvePatTtlSeconds:
    def test_one_minute_accepted(self):
        assert _resolve_pat_ttl_seconds(1, "minutes") == 60

    def test_one_hour_accepted(self):
        assert _resolve_pat_ttl_seconds(1, "hours") == 3600

    def test_one_day_accepted(self):
        assert _resolve_pat_ttl_seconds(1, "days") == 86400

    def test_thirty_days_exact_accepted(self):
        # 30 days is the exact cap and must be allowed.
        assert _resolve_pat_ttl_seconds(30, "days") == _PAT_MAX_TTL_SECONDS

    def test_thirty_days_plus_one_second_rejected(self):
        # 30 days + 60s (the smallest unit over the cap) must be rejected.
        with pytest.raises(ValueError, match="30 days"):
            _resolve_pat_ttl_seconds(43201, "minutes")

    def test_thirty_one_days_rejected(self):
        with pytest.raises(ValueError, match="30 days"):
            _resolve_pat_ttl_seconds(31, "days")

    def test_zero_value_rejected(self):
        with pytest.raises(ValueError, match="positive integer"):
            _resolve_pat_ttl_seconds(0, "days")

    def test_negative_value_rejected(self):
        with pytest.raises(ValueError, match="positive integer"):
            _resolve_pat_ttl_seconds(-5, "hours")

    def test_unknown_unit_rejected(self):
        with pytest.raises(ValueError, match="minutes, hours, days"):
            _resolve_pat_ttl_seconds(1, "weeks")

    def test_empty_unit_rejected(self):
        with pytest.raises(ValueError, match="minutes, hours, days"):
            _resolve_pat_ttl_seconds(1, "")
