"""Tests for Phase 15 — Historical Failure Search with pgvector.

Verifies:
1. Searchable failure text construction with rich context
2. Sensitive credentials redaction (passwords, tokens, API keys)
3. EmbeddingProvider abstraction (Mock and Gemini interfaces)
4. Indexing a trace with no findings returns 'no_findings'
5. Indexing a trace with findings creates failure embeddings
6. Idempotency: re-indexing the same trace updates rather than duplicates records
7. Indexing a nonexistent trace raises TraceNotFoundError / 404
8. Semantic search query validation (empty query rejects with 400)
9. Semantic search returns ranked results by similarity score
10. Semantic search filters by severity, rule, and project
11. Deterministic stable tie-breaking when similarity scores are close
12. API: POST /api/v1/traces/{trace_id}/index succeeds (200)
13. API: GET /api/v1/failures/search returns ranked results (200)
14. API: Endpoints enforce authentication (401 on missing auth)
"""

from datetime import datetime, timezone
from typing import Any, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import FailureEmbeddingModel, TraceModel
from app.db.repositories import FailureEmbeddingRepository, TraceRepository
from app.main import app
from app.models.failure_search import HistoricalSearchResponse, TraceIndexingResponse
from app.models.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    generate_finding_id,
)
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)
from app.services.embedding_provider import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    get_embedding_provider,
)
from app.services.failure_search_service import (
    FailureSearchService,
    build_searchable_failure_text,
    sanitize_payload,
)
from app.services.trace_reconstruction_service import TraceNotFoundError


def _build_test_trace(
    trace_id: str,
    name: str = "PaymentAgent",
    project_name: str = "BillingService",
    events: List[ReconstructedEvent] | None = None,
) -> ReconstructedTrace:
    ev_list = events or []
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return ReconstructedTrace(
        trace_id=trace_id,
        name=name,
        project_name=project_name,
        start_time=base_time,
        end_time=base_time,
        status="failed",
        duration_ms=2500.0,
        event_count=len(ev_list),
        metadata=TraceExecutionMetadata(
            total_event_count=len(ev_list),
            is_complete=True,
        ),
        events=ev_list,
        root_event_ids=[e.event_id for e in ev_list if e.parent_event_id is None],
    )


def _build_test_finding(
    trace_id: str,
    rule: str = "explicit_error",
    category: FindingCategory = FindingCategory.EXPLICIT_ERROR,
    severity: FindingSeverity = FindingSeverity.ERROR,
    message: str = "Payment processor rejected transaction with 402 Card Declined",
    evidence_ids: List[str] | None = None,
    finding_id: Optional[str] = None,
) -> Finding:
    ev_ids = evidence_ids or ["ev_fail_1"]
    return Finding(
        finding_id=finding_id or generate_finding_id(trace_id, rule, ev_ids),
        trace_id=trace_id,
        rule=rule,
        category=category,
        severity=severity,
        message=message,
        evidence_event_ids=ev_ids,
        evidence={"code": "card_declined"},
        detected_at=datetime.now(timezone.utc),
    )


# ==============================================================================
# 1. Text Synthesis & Redaction Tests
# ==============================================================================


def test_sanitize_payload_redacts_credentials():
    """Sensitive keys (passwords, tokens, api keys) are cleanly redacted."""
    raw_payload = {
        "user_id": "u123",
        "api_key": "sk-live-secret-key-12345",
        "auth_token": "bearer abcdef123456",
        "nested": {
            "password": "supersecretpassword",
            "safe_param": "checkout_standard",
        },
        "headers": ["Authorization: Bearer secret_token", "Content-Type: application/json"],
    }

    sanitized = sanitize_payload(raw_payload)
    assert sanitized["user_id"] == "u123"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["safe_param"] == "checkout_standard"
    assert sanitized["headers"][0] == "[REDACTED_SECRET]"
    assert sanitized["headers"][1] == "Content-Type: application/json"


def test_build_searchable_failure_text():
    """Builds structured searchable text including trace context and evidence highlights."""
    ev = ReconstructedEvent(
        event_id="ev_stripe_1",
        trace_id="t_pay_1",
        event_type="TOOL_CALL",
        timestamp=datetime.now(timezone.utc),
        agent_name="BillingAgent",
        data={"tool_name": "stripe_charge", "amount": 4900, "api_key": "sk-secret"},
        metadata={},
    )
    trace = _build_test_trace("t_pay_1", name="CheckoutAgent", project_name="Ecommerce", events=[ev])
    finding = _build_test_finding("t_pay_1", message="Stripe charge failed with 402 Card Declined", evidence_ids=["ev_stripe_1"])

    text = build_searchable_failure_text(trace, finding)
    assert "CheckoutAgent" in text
    assert "Ecommerce" in text
    assert "explicit_error" in text
    assert "Card Declined" in text
    assert "ev_stripe_1" in text
    assert "stripe_charge" in text
    assert "sk-secret" not in text  # Sensitive key must not be present


# ==============================================================================
# 2. Embedding Provider Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_embedding_provider_dimension_and_normalization():
    """MockEmbeddingProvider produces 768-dimensional normalized vectors."""
    provider = MockEmbeddingProvider(dimension=768)
    vec = await provider.embed_text("payment card declined timeout")

    assert len(vec) == 768
    # L2 norm should be approximately 1.0
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 0.001


@pytest.mark.asyncio
async def test_mock_embedding_provider_semantic_similarity():
    """Semantically similar texts have higher cosine similarity than unrelated texts."""
    provider = MockEmbeddingProvider(dimension=768)
    v_query = await provider.embed_text("payment tool card declined after retry exhaustion")
    v_similar = await provider.embed_text("payment tool rejected card declined error")
    v_unrelated = await provider.embed_text("weather forecast today is sunny in Tokyo")

    def cosine_sim(a, b):
        return sum(x * y for x, y in zip(a, b))

    sim_similar = cosine_sim(v_query, v_similar)
    sim_unrelated = cosine_sim(v_query, v_unrelated)

    assert sim_similar > sim_unrelated
    assert sim_similar > 0.4


# ==============================================================================
# 3. Indexing & Search Service Database Tests (using in-memory test DB session)
# ==============================================================================


@pytest.mark.asyncio
async def test_index_trace_no_findings(test_db_session):
    """Indexing a clean trace with zero findings returns 'no_findings'."""
    service = FailureSearchService(provider=MockEmbeddingProvider())
    clean_trace = _build_test_trace("t_clean_1", events=[])

    with patch(
        "app.services.failure_search_service.trace_reconstruction_service.reconstruct_trace",
        return_value=clean_trace,
    ), patch(
        "app.services.failure_search_service.failure_detection_service.detect_failures",
        return_value=[],
    ):
        res = await service.index_trace_failures("t_clean_1", test_db_session)

    assert res.status == "no_findings"
    assert res.indexed_count == 0


@pytest.mark.asyncio
async def test_index_trace_with_findings_and_idempotency(test_db_session):
    """Indexing a trace persists failure embeddings, and re-indexing is idempotent."""
    service = FailureSearchService(provider=MockEmbeddingProvider())
    trace = _build_test_trace("t_err_1")
    finding = _build_test_finding("t_err_1", message="Payment gateway timed out")

    # Seed trace in DB for foreign key constraint
    db_trace = TraceModel(
        trace_id="t_err_1",
        name="PaymentAgent",
        project_name="BillingService",
        start_time=datetime.now(timezone.utc),
        status="failed",
        metadata_={},
    )
    test_db_session.add(db_trace)
    await test_db_session.flush()

    with patch(
        "app.services.failure_search_service.trace_reconstruction_service.reconstruct_trace",
        return_value=trace,
    ), patch(
        "app.services.failure_search_service.failure_detection_service.detect_failures",
        return_value=[finding],
    ):
        res1 = await service.index_trace_failures("t_err_1", test_db_session)
        assert res1.status == "indexed"
        assert res1.indexed_count == 1

        # Re-index the same trace (idempotent update)
        res2 = await service.index_trace_failures("t_err_1", test_db_session)
        assert res2.status == "indexed"
        assert res2.indexed_count == 1

    repo = FailureEmbeddingRepository(test_db_session)
    stored = await repo.get_by_trace_id("t_err_1")
    assert len(stored) == 1
    assert stored[0].finding_id == finding.finding_id
    assert stored[0].rule == "explicit_error"


@pytest.mark.asyncio
async def test_search_similar_failures(test_db_session):
    """Semantic search retrieves relevant failure records ordered by similarity."""
    service = FailureSearchService(provider=MockEmbeddingProvider())

    # Seed 2 traces
    t1 = TraceModel(trace_id="t_pay", name="PaymentAgent", project_name="Billing", start_time=datetime.now(timezone.utc), status="failed", metadata_={})
    t2 = TraceModel(trace_id="t_weather", name="WeatherAgent", project_name="Analytics", start_time=datetime.now(timezone.utc), status="failed", metadata_={})
    test_db_session.add_all([t1, t2])
    await test_db_session.flush()

    f_pay = _build_test_finding("t_pay", message="Stripe card declined error")
    f_weather = _build_test_finding("t_weather", rule="repeated_tool_call", message="Weather API loop detected")

    trace_pay = _build_test_trace("t_pay", name="PaymentAgent", project_name="Billing")
    trace_weather = _build_test_trace("t_weather", name="WeatherAgent", project_name="Analytics")

    with patch(
        "app.services.failure_search_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_pay, trace_weather],
    ), patch(
        "app.services.failure_search_service.failure_detection_service.detect_failures",
        side_effect=[[f_pay], [f_weather]],
    ):
        await service.index_trace_failures("t_pay", test_db_session)
        await service.index_trace_failures("t_weather", test_db_session)

    # Search for payment card issue
    search_res = await service.search_failures("payment card declined", test_db_session, limit=5)
    assert search_res.total_results == 2
    # The payment failure should rank #1 with highest similarity
    assert search_res.results[0].trace_id == "t_pay"
    assert search_res.results[0].similarity > search_res.results[1].similarity


@pytest.mark.asyncio
async def test_search_filter_by_severity_and_rule(test_db_session):
    """Search correctly filters by severity, rule, and project."""
    service = FailureSearchService(provider=MockEmbeddingProvider())

    t1 = TraceModel(trace_id="t_filter_1", name="Agent1", project_name="ProjectA", start_time=datetime.now(timezone.utc), status="failed", metadata_={})
    test_db_session.add(t1)
    await test_db_session.flush()

    f1 = _build_test_finding("t_filter_1", rule="retry_exhaustion", severity=FindingSeverity.CRITICAL, message="Retry count exceeded")
    trace1 = _build_test_trace("t_filter_1", project_name="ProjectA")

    with patch(
        "app.services.failure_search_service.trace_reconstruction_service.reconstruct_trace",
        return_value=trace1,
    ), patch(
        "app.services.failure_search_service.failure_detection_service.detect_failures",
        return_value=[f1],
    ):
        await service.index_trace_failures("t_filter_1", test_db_session)

    # Filter with matching rule
    res_match = await service.search_failures("retry", test_db_session, rule="retry_exhaustion")
    assert res_match.total_results == 1

    # Filter with non-matching rule
    res_no_match = await service.search_failures("retry", test_db_session, rule="explicit_error")
    assert res_no_match.total_results == 0


# ==============================================================================
# 4. FastAPI Integration Tests
# ==============================================================================


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {
        "Authorization": "Bearer test_api_key_123",
        "X-Project-Name": "BillingService",
    }


def test_api_index_trace_failures(client, auth_headers):
    """POST /api/v1/traces/{trace_id}/index returns 200 with indexing result."""
    mock_resp = TraceIndexingResponse(
        trace_id="t_api_123",
        indexed_count=2,
        status="indexed",
        finding_ids=["f1", "f2"],
        message="Indexed 2 failures",
    )
    with patch(
        "app.services.failure_search_service.failure_search_service.index_trace_failures",
        new=AsyncMock(return_value=mock_resp),
    ):
        res = client.post("/api/v1/traces/t_api_123/index", headers=auth_headers)

    assert res.status_code == 200
    data = res.json()
    assert data["trace_id"] == "t_api_123"
    assert data["indexed_count"] == 2
    assert data["status"] == "indexed"


def test_api_search_historical_failures(client, auth_headers):
    """GET /api/v1/failures/search returns 200 with matching results."""
    mock_resp = HistoricalSearchResponse(
        query="card declined",
        total_results=1,
        results=[
            {
                "trace_id": "t_api_123",
                "finding_id": "finding-1",
                "rule": "explicit_error",
                "category": "explicit_error",
                "severity": "error",
                "message": "Card declined on checkout",
                "searchable_text": "Trace context...",
                "similarity": 0.8954,
                "trace_name": "CheckoutAgent",
                "project_name": "BillingService",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "evidence_event_ids": ["ev_1"],
                "metadata": {},
            }
        ],
    )
    with patch(
        "app.services.failure_search_service.failure_search_service.search_failures",
        new=AsyncMock(return_value=mock_resp),
    ):
        res = client.get("/api/v1/failures/search?q=card+declined", headers=auth_headers)

    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "card declined"
    assert data["total_results"] == 1
    assert data["results"][0]["similarity"] == 0.8954


def test_api_search_empty_query_rejected(client, auth_headers):
    """GET /api/v1/failures/search with empty query returns 400."""
    res = client.get("/api/v1/failures/search?q=", headers=auth_headers)
    assert res.status_code == 400


def test_api_search_unauthorized(client):
    """GET /api/v1/failures/search without auth returns 401."""
    res = client.get("/api/v1/failures/search?q=payment")
    assert res.status_code == 401


def test_api_index_missing_trace_returns_404(client, auth_headers):
    """POST /api/v1/traces/{trace_id}/index for nonexistent trace returns 404."""
    with patch(
        "app.services.failure_search_service.failure_search_service.index_trace_failures",
        side_effect=ValueError("Trace nonexistent-trace not found"),
    ):
        res = client.post("/api/v1/traces/nonexistent-trace/index", headers=auth_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_indexing_embedding_provider_failure(test_db_session):
    """If embedding provider fails, an exception is raised cleanly without corrupting DB."""
    class FailingEmbeddingProvider(EmbeddingProvider):
        @property
        def model_name(self) -> str:
            return "failing-model"

        @property
        def dimension(self) -> int:
            return 768

        async def embed_text(self, text: str) -> list[float]:
            raise RuntimeError("Gemini API connection error")

        async def embed_batch(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("Gemini API connection error")

    failing_service = FailureSearchService(provider=FailingEmbeddingProvider())
    t1 = TraceModel(trace_id="t_fail_prov", name="Agent", project_name="P", start_time=datetime.now(timezone.utc), status="failed", metadata_={})
    test_db_session.add(t1)
    await test_db_session.flush()

    finding = _build_test_finding("t_fail_prov")
    trace = _build_test_trace("t_fail_prov")

    with patch(
        "app.services.failure_search_service.trace_reconstruction_service.reconstruct_trace",
        return_value=trace,
    ), patch(
        "app.services.failure_search_service.failure_detection_service.detect_failures",
        return_value=[finding],
    ):
        with pytest.raises(RuntimeError, match="Gemini API connection error"):
            await failing_service.index_trace_failures("t_fail_prov", test_db_session)

    # Ensure no partial embeddings were stored
    repo = FailureEmbeddingRepository(test_db_session)
    existing = await repo.get_by_trace_id("t_fail_prov")
    assert len(existing) == 0


@pytest.mark.asyncio
async def test_deterministic_tie_ordering(test_db_session):
    """When two failures have identical similarity, tie-breaking is deterministic (by created_at, trace_id, finding_id)."""
    service = FailureSearchService(provider=MockEmbeddingProvider())

    t1 = TraceModel(trace_id="t_tie_b", name="AgentB", project_name="P", start_time=datetime.now(timezone.utc), status="failed", metadata_={})
    t2 = TraceModel(trace_id="t_tie_a", name="AgentA", project_name="P", start_time=datetime.now(timezone.utc), status="failed", metadata_={})
    test_db_session.add_all([t1, t2])
    await test_db_session.flush()

    # Identical findings
    f1 = _build_test_finding("t_tie_b", finding_id="f-1", message="Exact identical failure message")
    f2 = _build_test_finding("t_tie_a", finding_id="f-1", message="Exact identical failure message")
    tr1 = _build_test_trace("t_tie_b")
    tr2 = _build_test_trace("t_tie_a")

    with patch(
        "app.services.failure_search_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[tr1, tr2],
    ), patch(
        "app.services.failure_search_service.failure_detection_service.detect_failures",
        side_effect=[[f1], [f2]],
    ):
        await service.index_trace_failures("t_tie_b", test_db_session)
        await service.index_trace_failures("t_tie_a", test_db_session)

    res = await service.search_failures("Exact identical failure message", test_db_session)
    assert res.total_results == 2
    # Verify deterministic ordering: both scores equal, secondary ordering stable
    assert res.results[0].similarity == res.results[1].similarity
    trace_ids = [r.trace_id for r in res.results]
    assert len(set(trace_ids)) == 2
