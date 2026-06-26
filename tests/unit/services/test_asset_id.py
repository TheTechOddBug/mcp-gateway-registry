"""Unit tests for resolve_asset_id (registry/services/_asset_id.py)."""

import uuid

import pytest

from registry.services._asset_id import (
    MAX_ID_LENGTH,
    InvalidAssetIdError,
    resolve_asset_id,
)


def test_none_generates_a_uuid4_string():
    result = resolve_asset_id(None)
    assert isinstance(result, str)  # a string, not a UUID object
    assert uuid.UUID(result).version == 4  # and a real v4 UUID


def test_supplied_arn_returned_verbatim():
    arn = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-runtime"
    assert resolve_asset_id(arn) == arn


def test_supplied_uuid_string_is_kept_not_regenerated():
    fixed = "11111111-1111-4111-8111-111111111111"
    assert resolve_asset_id(fixed) == fixed


def test_surrounding_whitespace_is_stripped():
    assert resolve_asset_id("  urn:custom:thing  ") == "urn:custom:thing"


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", " \t\n "])
def test_blank_or_whitespace_only_raises(blank):
    with pytest.raises(InvalidAssetIdError):
        resolve_asset_id(blank)


def test_exactly_max_length_is_allowed():
    ok = "x" * MAX_ID_LENGTH
    assert resolve_asset_id(ok) == ok


def test_over_max_length_raises():
    with pytest.raises(InvalidAssetIdError):
        resolve_asset_id("x" * (MAX_ID_LENGTH + 1))


@pytest.mark.parametrize("bad", ["line\none", "tab\there", "bell\x07", "del\x7f"])
def test_control_characters_raise(bad):
    with pytest.raises(InvalidAssetIdError):
        resolve_asset_id(bad)


def test_error_is_a_valueerror_subclass():
    # Pydantic + the route both rely on this to produce a 422.
    assert issubclass(InvalidAssetIdError, ValueError)
