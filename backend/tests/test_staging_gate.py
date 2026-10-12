"""Phase 20D: Deployment Readiness Audit & Staging Gate Verification Tests.

Validates:
1. Mock provider fallback prohibition in production.
2. Safe mock fallback behavior in development/testing with telemetry recording.
3. Configuration-driven Redis readiness policy (single-instance vs multi-instance).
4. Explicit PostgreSQL TLS/SSL mode validation and parameter parsing.
5. Operational metrics endpoint protection (token auth, disable flag, zero sensitive data).
6. Request / Correlation ID validation, bounding, and header propagation.
"""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app
from app.services.metrics import metrics_collector
from app.services.llm_provider import (
    GroqInvestigationProvider,
    GeminiInvestigationProvider,
    MockInvestigationProvider,
    get_investigation_provider,
)
from app.services.embedding_provider import (
    GeminiEmbeddingProvider,
    MockEmbeddingProvider,
    get_embedding_provider,
)
from app.models.investigation import InvestigationContext, CompactEventSummary

VALID_HIGH_ENTROPY_JWT = "k9#Xm2$vL8*pQ4@wN7!jR5^tY1&bC3~zP6=fG0+hD_vW9"


# ---------------------------------------------------------------------------
# 1. Mock Provider Fallback Audit & Prohibition in Production
# ---------------------------------------------------------------------------

def test_production_config_rejects_mock_llm_provider():
    """In production, LLM_PROVIDER='mock' must fail closed at startup."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key=VALID_HIGH_ENTROPY_JWT,
            cookie_secure=True,
            cors_origins="https://dashboard.example.com",
            database_url="postgresql://user:pass@ep-live.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
            llm_provider="mock",
            embedding_provider="gemini",
            gemini_api_key="valid_key",
            allow_mock_providers=False,
        )
    assert "LLM_PROVIDER cannot be 'mock' in production" in str(exc.value)


def test_production_config_rejects_mock_embedding_provider():
    """In production, EMBEDDING_PROVIDER='mock' must fail closed at startup."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key=VALID_HIGH_ENTROPY_JWT,
            cookie_secure=True,
            cors_origins="https://dashboard.example.com",
            database_url="postgresql://user:pass@ep-live.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
            llm_provider="groq",
            groq_api_key="valid_key",
            embedding_provider="mock",
            allow_mock_providers=False,
        )
    assert "EMBEDDING_PROVIDER cannot be 'mock' in production" in str(exc.value)


def test_get_investigation_provider_rejects_mock_in_production():
    """get_investigation_provider('mock') must raise RuntimeError in production."""
    with patch("app.services.llm_provider.settings.environment", "production"):
        with patch("app.services.llm_provider.settings.allow_mock_providers", False):
            with pytest.raises(RuntimeError) as exc:
                get_investigation_provider("mock")
            assert "prohibited in production" in str(exc.value)


def test_get_embedding_provider_rejects_mock_in_production():
    """get_embedding_provider('mock') must raise RuntimeError in production."""
    with patch("app.services.embedding_provider.settings.environment", "production"):
        with patch("app.services.embedding_provider.settings.allow_mock_providers", False):
            with pytest.raises(RuntimeError) as exc:
                get_embedding_provider("mock")
            assert "prohibited in production" in str(exc.value)


@pytest.mark.asyncio
async def test_groq_failure_in_production_fails_closed_without_silent_mock():
    """When Groq fails in production, it must raise RuntimeError and NOT return mock output."""
    provider = GroqInvestigationProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    context = InvestigationContext(
        trace_id="tr_prod_fail",
        name="test_trace",
        project="default",
        status="failed",
        start_time="2026-10-12T00:00:00Z",
        total_events=2,
        duration_ms=150.0,
        deterministic_findings=[],
        key_events=[
            CompactEventSummary(
                event_id="ev_1",
                event_type="ERROR",
                timestamp="2026-10-12T00:00:00Z",
                summary_data={"message": "db error"},
            )
        ],
    )

    with patch("langchain_groq.ChatGroq.ainvoke", side_effect=ConnectionError("Upstream timeout")):
        with patch("app.services.llm_provider.settings.environment", "production"):
            with patch("app.services.llm_provider.settings.allow_mock_providers", False):
                with pytest.raises(RuntimeError) as exc:
                    await provider.investigate(context)
                assert "mock fallback is disabled in production" in str(exc.value)


@pytest.mark.asyncio
async def test_gemini_embedding_failure_in_production_fails_closed():
    """When Gemini embedding fails in production, it must raise RuntimeError and NOT return mock output."""
    provider = GeminiEmbeddingProvider(api_key="test_key")

    with patch("app.services.embedding_provider.settings.environment", "production"):
        with patch("app.services.embedding_provider.settings.allow_mock_providers", False):
            with patch("langchain_google_genai.GoogleGenerativeAIEmbeddings.aembed_documents", side_effect=Exception("API limit exceeded")):
                with pytest.raises(RuntimeError) as exc:
                    await provider.embed_batch(["sample query"])
                assert "mock fallback is disabled in production" in str(exc.value)


@pytest.mark.asyncio
async def test_mock_fallback_allowed_in_development_and_recorded_in_telemetry():
    """In development, real provider failure falls back to mock and records telemetry."""
    provider = GroqInvestigationProvider(api_key="test_key")
    context = InvestigationContext(
        trace_id="tr_dev_fallback",
        name="test_trace_dev",
        project="default",
        status="failed",
        start_time="2026-10-12T00:00:00Z",
        total_events=1,
        duration_ms=50.0,
        deterministic_findings=[],
        key_events=[
            CompactEventSummary(
                event_id="ev_dev_1",
                event_type="ERROR",
                timestamp="2026-10-12T00:00:00Z",
                summary_data={"message": "service timeout"},
            )
        ],
    )

    with patch("langchain_groq.ChatGroq.ainvoke", side_effect=Exception("Network error")):
        with patch("app.services.llm_provider.settings.environment", "development"):
            with patch("app.services.llm_provider.settings.allow_mock_providers", True):
                res = await provider.investigate(context)
                assert res["status"] in ("investigated", "no_issue_detected")
                # Telemetry should record mock fallback
                metrics_json = metrics_collector.get_metrics_json()
                assert metrics_json["mock_fallbacks"].get("groq", 0) > 0


# ---------------------------------------------------------------------------
# 2. Redis Readiness Policy Driven by Deployment Topology
# ---------------------------------------------------------------------------

def test_readiness_single_instance_redis_down_returns_200_degraded():
    """In single-instance topology with redis_required=False, Redis failure degrades gracefully."""
    client = TestClient(app)

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    with patch("app.main.settings.deployment_topology", "single-instance"):
        with patch("app.main.settings.redis_required", False):
            with patch("app.services.realtime_publisher.realtime_publisher._get_redis", return_value=None):
                with patch("app.db.session.engine", mock_engine):
                    resp = client.get("/health/ready")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "degraded"
                    assert data["ready"] is True
                    assert "degraded" in data["services"]["redis"]


def test_readiness_multi_instance_redis_down_returns_503_unhealthy():
    """In multi-instance topology, Redis failure must return 503 Service Unavailable."""
    client = TestClient(app)

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    with patch("app.main.settings.deployment_topology", "multi-instance"):
        with patch("app.main.settings.redis_required", True):
            with patch("app.services.realtime_publisher.realtime_publisher._get_redis", return_value=None):
                with patch("app.db.session.engine", mock_engine):
                    resp = client.get("/health/ready")
                    assert resp.status_code == 503
                    data = resp.json()
                    assert data["status"] == "unhealthy"
                    assert data["ready"] is False
                    assert "Redis is required" in data["error"]


def test_readiness_database_down_returns_503():
    """Database failure must always return 503 regardless of Redis status."""
    client = TestClient(app)

    mock_engine = MagicMock()
    mock_engine.begin.side_effect = Exception("Database connection refused")

    with patch("app.db.session.engine", mock_engine):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["ready"] is False
        assert data["services"]["database"] == "disconnected"


# ---------------------------------------------------------------------------
# 3. Explicit PostgreSQL SSL/TLS Mode Validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("insecure_param", [
    "sslmode=disable",
    "sslmode=allow",
    "ssl=false",
    "ssl=0",
])
def test_production_rejects_insecure_ssl_parameters(insecure_param):
    """Production must reject explicitly insecure database SSL parameters."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key=VALID_HIGH_ENTROPY_JWT,
            cookie_secure=True,
            cors_origins="https://dashboard.example.com",
            database_url=f"postgresql://user:pass@ep-live.neon.tech/agentlens?{insecure_param}",
            agentlens_api_keys="",
            llm_provider="groq",
            groq_api_key="valid_key",
            embedding_provider="gemini",
            gemini_api_key="valid_key",
        )
    assert "Insecure SSL mode" in str(exc.value)


@pytest.mark.parametrize("valid_ssl_param", [
    "sslmode=require",
    "sslmode=verify-ca",
    "sslmode=verify-full",
    "ssl=true",
    "ssl=1",
])
def test_production_accepts_valid_ssl_parameters(valid_ssl_param):
    """Production must accept verified SSL/TLS database configurations."""
    cfg = Settings(
        environment="production",
        jwt_secret_key=VALID_HIGH_ENTROPY_JWT,
        cookie_secure=True,
        cors_origins="https://dashboard.example.com",
        database_url=f"postgresql://user:pass@ep-live.neon.tech/agentlens?{valid_ssl_param}",
        agentlens_api_keys="",
        llm_provider="groq",
        groq_api_key="valid_key",
        embedding_provider="gemini",
        gemini_api_key="valid_key",
    )
    assert cfg.database_url is not None


# ---------------------------------------------------------------------------
# 4. Operational Metrics Security & Data Privacy
# ---------------------------------------------------------------------------

def test_metrics_token_protection():
    """When metrics_auth_token is configured, unauthorized access is rejected with 401."""
    client = TestClient(app)

    with patch("app.main.settings.metrics_auth_token", "secret_scrape_token_999"):
        # No token -> 401
        res = client.get("/metrics")
        assert res.status_code == 401

        res_json = client.get("/api/v1/metrics")
        assert res_json.status_code == 401

        # Invalid token -> 401
        res = client.get("/metrics", headers={"Authorization": "Bearer wrong"})
        assert res.status_code == 401

        # Valid Bearer header -> 200
        res = client.get("/metrics", headers={"Authorization": "Bearer secret_scrape_token_999"})
        assert res.status_code == 200

        # Valid query parameter -> 200
        res = client.get("/api/v1/metrics?token=secret_scrape_token_999")
        assert res.status_code == 200


def test_metrics_disabled_returns_404():
    """When metrics_enabled is False, metrics endpoints return 404."""
    client = TestClient(app)

    with patch("app.main.settings.metrics_enabled", False):
        res = client.get("/metrics")
        assert res.status_code == 404

        res = client.get("/api/v1/metrics")
        assert res.status_code == 404


def test_metrics_excludes_sensitive_data_and_high_cardinality():
    """Metrics exposition must not contain passwords, tokens, user IDs, or unnormalized paths."""
    client = TestClient(app)

    # Record request to an ID-containing path
    metrics_collector.record_http_request("GET", "/api/v1/traces/tr_sensitive_1234567890abcdef", 200, 0.05)

    with patch("app.main.settings.metrics_auth_token", None):
        res = client.get("/metrics")
        assert res.status_code == 200
        text = res.text

        # Path must be normalized to {id}
        assert 'path="/api/v1/traces/{id}"' in text
        assert "tr_sensitive_1234567890abcdef" not in text
        assert "password" not in text.lower()
        assert "secret" not in text.lower()


# ---------------------------------------------------------------------------
# 5. Correlation & Request ID Bounded Validation
# ---------------------------------------------------------------------------

def test_request_id_validated_and_bounded():
    """Valid request ID is echoed in headers; overly long or malformed IDs are safely regenerated."""
    client = TestClient(app)

    # 1. Valid ID is preserved
    valid_id = "req_custom-abc.123_456"
    resp = client.get("/health/live", headers={"X-Request-ID": valid_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == valid_id
    assert resp.headers.get("X-Correlation-ID") == valid_id

    # 2. Overly long ID (>64 chars) is replaced with a safe generated ID
    long_id = "x" * 128
    resp = client.get("/health/live", headers={"X-Request-ID": long_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") != long_id
    assert resp.headers.get("X-Request-ID").startswith("req_")

    # 3. Invalid characters are replaced with a safe generated ID
    malicious_id = "req_<script>alert(1)</script>"
    resp = client.get("/health/live", headers={"X-Request-ID": malicious_id})
    assert resp.status_code == 200
    assert "<script>" not in resp.headers.get("X-Request-ID")
    assert resp.headers.get("X-Request-ID").startswith("req_")
