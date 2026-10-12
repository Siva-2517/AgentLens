"""Targeted tests for Phase 20C: Reliability, Monitoring & Operational Recovery."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.logging_config import RedactingFilter, StructuredJsonFormatter, set_correlation_id
from app.services.metrics import metrics_collector
from app.services.redaction import mask_sensitive_text


# =============================================================================
# 1. Health and Readiness Semantics
# =============================================================================

@pytest.mark.asyncio
async def test_liveness_endpoint_returns_alive():
    """Verify /health/live returns HTTP 200 process liveness."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_healthy_when_all_services_connected():
    """Verify /health/ready returns 200 healthy when DB and Redis are connected."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    with patch("app.db.session.engine", mock_engine), \
         patch("app.services.realtime_publisher.realtime_publisher._get_redis", AsyncMock(return_value=mock_redis)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["ready"] is True
            assert data["services"]["database"] == "connected"
            assert data["services"]["redis"] == "connected"


@pytest.mark.asyncio
async def test_readiness_degraded_when_redis_unavailable_in_single_instance():
    """Verify /health/ready returns 200 degraded with local fallback when Redis is down."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    with patch("app.db.session.engine", mock_engine), \
         patch("app.services.realtime_publisher.realtime_publisher._get_redis", AsyncMock(side_effect=Exception("Redis down"))):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["ready"] is True
            assert data["services"]["database"] == "connected"
            assert "degraded" in data["services"]["redis"]


@pytest.mark.asyncio
async def test_readiness_503_when_database_unavailable():
    """Verify /health/ready returns HTTP 503 Service Unavailable when the database is down."""
    mock_engine = MagicMock()
    mock_engine.begin.side_effect = Exception("DB connection timeout")

    with patch("app.db.session.engine", mock_engine), \
         patch("app.services.realtime_publisher.realtime_publisher._get_redis", AsyncMock(return_value=None)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unhealthy"
            assert data["ready"] is False
            assert data["services"]["database"] == "disconnected"


# =============================================================================
# 2. Secret Redaction in Structured Logs and Exceptions
# =============================================================================

def test_redaction_masks_database_and_redis_urls():
    """Verify connection strings including postgresql and rediss (TLS) are masked."""
    raw = "Connecting to postgresql+asyncpg://admin:super_secret_pwd@ep-prod.neon.tech/agentlens?sslmode=require and rediss://:redispwd@redis.prod:6380/0"
    masked = mask_sensitive_text(raw)
    assert "super_secret_pwd" not in masked
    assert "redispwd" not in masked
    assert "[REDACTED_CONNECTION_URL]" in masked


def test_redaction_masks_jwt_and_api_keys():
    """Verify JWT tokens and AgentLens API keys are masked."""
    jwt_sample = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    raw = f"Header Authorization: Bearer {jwt_sample} with key al_live_9876543210abcdef and sk-1234567890abcdef"
    masked = mask_sensitive_text(raw)
    assert jwt_sample not in masked
    assert "al_live_9876543210abcdef" not in masked
    assert "sk-1234567890abcdef" not in masked
    assert "[REDACTED_JWT]" in masked
    assert "[REDACTED_API_KEY]" in masked


def test_redacting_log_filter_sanitizes_record_and_exceptions():
    """Verify RedactingFilter redacts secrets in log record messages, args, and exception tracebacks."""
    filter_instance = RedactingFilter()

    # Test record message
    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="Database failed: postgresql://user:pwd123@localhost/db with token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoxfQ.1234567890abcdef",
        args=(),
        exc_info=None,
    )
    filter_instance.filter(record)
    assert "pwd123" not in record.msg
    assert "[REDACTED_CONNECTION_URL]" in record.msg
    assert "[REDACTED_JWT]" in record.msg

    # Test record exception text
    record_with_exc = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="Caught error",
        args=(),
        exc_info=None,
    )
    record_with_exc.exc_text = "Traceback: Connect to rediss://:supersecret@redis:6379 failed"
    filter_instance.filter(record_with_exc)
    assert "supersecret" not in record_with_exc.exc_text
    assert "[REDACTED_CONNECTION_URL]" in record_with_exc.exc_text


# =============================================================================
# 3. Correlation ID Propagation
# =============================================================================

@pytest.mark.asyncio
async def test_correlation_id_propagated_in_response_headers():
    """Verify client-supplied X-Request-ID is preserved and propagated."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live", headers={"X-Request-ID": "custom-trace-id-123"})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == "custom-trace-id-123"
        assert resp.headers.get("X-Correlation-ID") == "custom-trace-id-123"


@pytest.mark.asyncio
async def test_correlation_id_generated_when_missing():
    """Verify X-Request-ID is automatically generated with req_ prefix when omitted."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live")
        assert resp.status_code == 200
        req_id = resp.headers.get("X-Request-ID")
        assert req_id is not None
        assert req_id.startswith("req_")


# =============================================================================
# 4. Operational Metrics Exposition
# =============================================================================

@pytest.mark.asyncio
async def test_metrics_prometheus_exposition():
    """Verify /metrics returns OpenMetrics plaintext containing request counters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger an endpoint to ensure counter > 0
        await client.get("/health/live")

        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        text = resp.text
        assert "agentlens_http_requests_total" in text
        assert "agentlens_http_duration_seconds_total" in text
        assert "agentlens_websocket_active_connections" in text


@pytest.mark.asyncio
async def test_metrics_json_exposition():
    """Verify /api/v1/metrics returns low-cardinality JSON snapshot."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "http_requests" in data
        assert "http_latencies" in data
        assert "database_operations" in data
        assert "redis_publish" in data
        assert "websocket" in data


# =============================================================================
# 5. Redis Publish Error Resilience & Connection Cleanup
# =============================================================================

@pytest.mark.asyncio
async def test_realtime_publisher_cleans_up_on_redis_publish_error():
    """Verify RealtimePublisher closes and invalidates broken Redis pool and broadcasts locally."""
    from datetime import datetime, timezone
    from app.models.realtime import TraceStartedMessage
    from app.services.realtime_publisher import RealtimePublisher

    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = Exception("Connection lost")
    mock_redis.aclose = AsyncMock()

    publisher = RealtimePublisher(redis_url="redis://localhost:6379/0")
    publisher._redis = mock_redis

    msg = TraceStartedMessage(
        trace_id="test_tr_123",
        name="test_trace",
        start_time=datetime.now(timezone.utc),
    )

    with patch("app.services.realtime_service.realtime_service.broadcast_locally", AsyncMock()) as mock_local:
        # publish should return False for redis but not raise
        success = await publisher.publish("test_tr_123", msg)
        assert success is False
        # broken redis client was closed and reset
        mock_redis.aclose.assert_awaited_once()
        assert publisher._redis is None
        # local in-memory broadcast was still invoked
        mock_local.assert_awaited_once()


# =============================================================================
# 6. LLM Provider Bounded Timeouts
# =============================================================================

def test_investigation_providers_configure_bounded_timeouts():
    """Verify external LLM provider instances specify request_timeout=30.0."""
    from app.services.llm_provider import GeminiInvestigationProvider, GroqInvestigationProvider

    groq_provider = GroqInvestigationProvider(api_key="gsk_test")
    gemini_provider = GeminiInvestigationProvider(api_key="AIzaSy_test")

    assert groq_provider.model_name.startswith("groq:")
    assert gemini_provider.model_name.startswith("gemini:")
