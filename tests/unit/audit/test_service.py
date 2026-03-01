"""
Unit tests for AuditLogger service.

Tests the MongoDB-only audit logging functionality.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from registry.audit import (
    AuditLogger,
    Identity,
    RegistryApiAccessRecord,
    Request,
    Response,
)


def make_test_record(request_id: str = "test-123") -> RegistryApiAccessRecord:
    """Create a test audit record."""
    return RegistryApiAccessRecord(
        timestamp=datetime.now(UTC),
        request_id=request_id,
        identity=Identity(
            username="testuser",
            auth_method="oauth2",
            credential_type="bearer_token",
        ),
        request=Request(
            method="GET",
            path="/api/test",
            client_ip="127.0.0.1",
        ),
        response=Response(
            status_code=200,
            duration_ms=50.5,
        ),
    )


class TestAuditLoggerInit:
    """Tests for AuditLogger initialization."""

    def test_init_with_mongodb_enabled(self):
        """Logger initializes correctly with MongoDB enabled."""
        mock_repo = MagicMock()
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=mock_repo,
        )
        assert logger.mongodb_enabled is True
        assert logger.is_open is True
        assert logger.stream_name == "test-stream"

    def test_init_with_mongodb_disabled(self):
        """Logger initializes correctly with MongoDB disabled."""
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=False,
        )
        assert logger.mongodb_enabled is False
        assert logger.is_open is False

    def test_deprecated_params_accepted(self):
        """Deprecated parameters are accepted for backward compatibility."""
        logger = AuditLogger(
            log_dir="/tmp/test",
            rotation_hours=2,
            rotation_max_mb=50,
            local_retention_hours=48,
            stream_name="test-stream",
        )
        # Should not raise, deprecated params are ignored
        assert logger.stream_name == "test-stream"


class TestLogEvent:
    """Tests for log_event method."""

    async def test_log_event_writes_to_mongodb(self):
        """Event is written to MongoDB when enabled."""
        mock_repo = AsyncMock()
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=mock_repo,
        )

        record = make_test_record()
        await logger.log_event(record)

        mock_repo.insert.assert_called_once_with(record)

    async def test_log_event_skipped_when_disabled(self):
        """Event is skipped when MongoDB is disabled."""
        mock_repo = AsyncMock()
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=False,
            audit_repository=mock_repo,
        )

        await logger.log_event(make_test_record())

        mock_repo.insert.assert_not_called()

    async def test_log_event_handles_mongodb_error(self):
        """MongoDB errors are caught and logged, not raised."""
        mock_repo = AsyncMock()
        mock_repo.insert.side_effect = Exception("MongoDB connection failed")
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=mock_repo,
        )

        # Should not raise
        await logger.log_event(make_test_record())

    async def test_multiple_events_logged(self):
        """Multiple events can be logged sequentially."""
        mock_repo = AsyncMock()
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=mock_repo,
        )

        for i in range(3):
            await logger.log_event(make_test_record(f"request-{i}"))

        assert mock_repo.insert.call_count == 3


class TestClose:
    """Tests for close method."""

    async def test_close_is_safe(self):
        """Close method completes without error."""
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=AsyncMock(),
        )
        # Should not raise
        await logger.close()


class TestProperties:
    """Tests for logger properties."""

    def test_current_file_path_returns_none(self):
        """current_file_path returns None (no local files)."""
        logger = AuditLogger(stream_name="test-stream")
        assert logger.current_file_path is None

    def test_is_open_with_mongodb(self):
        """is_open returns True when MongoDB is enabled and repo is set."""
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=MagicMock(),
        )
        assert logger.is_open is True

    def test_is_open_without_mongodb(self):
        """is_open returns False when MongoDB is disabled."""
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=False,
        )
        assert logger.is_open is False

    def test_is_open_without_repo(self):
        """is_open returns False when MongoDB enabled but no repo."""
        logger = AuditLogger(
            stream_name="test-stream",
            mongodb_enabled=True,
            audit_repository=None,
        )
        assert logger.is_open is False
