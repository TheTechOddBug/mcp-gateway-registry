"""Boundary tests for the pat lifetime helper _resolve_pat_ttl_seconds.

The PAT lifetime is mandatory and bounded: no "never expires", capped at 30
days. This exercises the accept/reject boundary table.
"""

import pytest

from registry.api.egress_auth_routes import _PAT_MAX_TTL_SECONDS, _resolve_pat_ttl_seconds


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
