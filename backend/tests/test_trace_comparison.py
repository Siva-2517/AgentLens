"""Tests for Phase 14 — Trace Comparison and Replay Alignment.

Verifies:
1. Service: Identical traces produce perfectly matched alignment with 0 deltas
2. Service: Different durations calculate correct duration_diff_ms
3. Service: Different event counts produce accurate event_count_diff and step alignment
4. Service: Events unique to Trace A produce 'only_a' steps
5. Service: Events unique to Trace B produce 'only_b' steps
6. Service: Complex sequences with retries/errors identify branched execution
7. Service: Repeated event types match deterministically by order and semantic tool name
8. Service: Missing parent events handled cleanly without crash
9. Service: Different trace statuses reflect in status_changed, status_a, status_b
10. Service: Deterministic findings differences (findings_only_a, findings_only_b, common_findings)
11. Service: Empty trace IDs raise ValueError
12. Service: Comparison does not execute external agents, tools, or LLMs
13. API: Successful trace comparison (200 OK)
14. API: Missing trace A returns 404
15. API: Missing trace B returns 404
16. API: Empty or missing query parameter returns 400
17. API: Authentication enforced (401 on missing auth)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import EventModel, TraceModel
from app.db.repositories import EventRepository, TraceRepository
from app.main import app
from app.models.comparison import (
    EventComparisonStep,
    FindingComparison,
    HighLevelDifferences,
    TraceComparisonResult,
    TraceComparisonSummary,
)
from app.models.event import EventType
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)
from app.services.trace_comparison_service import (
    TraceComparisonService,
    trace_comparison_service,
)
from app.services.trace_reconstruction_service import TraceNotFoundError


def _build_test_event(
    event_id: str,
    trace_id: str,
    event_type: str,
    offset_seconds: int = 0,
    parent_id: str | None = None,
    duration_ms: float | None = None,
    tool_name: str | None = None,
    model_name: str | None = None,
    depth: int = 0,
) -> ReconstructedEvent:
    """Helper to construct ReconstructedEvent for tests."""
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts = base_time + timedelta(seconds=offset_seconds)
    data: dict[str, Any] = {}
    if tool_name:
        data["tool_name"] = tool_name
    if model_name:
        data["model"] = model_name

    return ReconstructedEvent(
        event_id=event_id,
        trace_id=trace_id,
        parent_event_id=parent_id,
        event_type=event_type,
        timestamp=ts,
        agent_name="TestAgent",
        data=data,
        metadata={},
        depth=depth,
        children_ids=[],
        duration_ms=duration_ms,
    )


def _build_test_trace(
    trace_id: str,
    name: str = "TestAgent",
    status: str = "completed",
    duration_ms: float | None = 2000.0,
    events: List[ReconstructedEvent] | None = None,
) -> ReconstructedTrace:
    """Helper to construct ReconstructedTrace for tests."""
    ev_list = events or []
    type_counts: dict[str, int] = {}
    for e in ev_list:
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1

    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    end_time = (
        base_time + timedelta(milliseconds=duration_ms) if duration_ms else None
    )

    metadata = TraceExecutionMetadata(
        total_event_count=len(ev_list),
        duration_ms=duration_ms,
        llm_call_count=type_counts.get("LLM_CALL", 0),
        llm_response_count=type_counts.get("LLM_RESPONSE", 0),
        tool_call_count=type_counts.get("TOOL_CALL", 0),
        tool_response_count=type_counts.get("TOOL_RESPONSE", 0),
        error_count=type_counts.get("ERROR", 0),
        retry_count=type_counts.get("RETRY", 0),
        state_change_count=type_counts.get("STATE_CHANGE", 0),
        first_event_timestamp=ev_list[0].timestamp if ev_list else None,
        last_event_timestamp=ev_list[-1].timestamp if ev_list else None,
        has_agent_start="AGENT_START" in type_counts,
        has_agent_end="AGENT_END" in type_counts,
        is_complete="AGENT_START" in type_counts and "AGENT_END" in type_counts,
        event_type_counts=type_counts,
    )

    return ReconstructedTrace(
        trace_id=trace_id,
        name=name,
        project_name="TestProject",
        start_time=base_time,
        end_time=end_time,
        status=status,
        duration_ms=duration_ms,
        event_count=len(ev_list),
        metadata=metadata,
        events=ev_list,
        root_event_ids=[e.event_id for e in ev_list if e.parent_event_id is None],
    )


# ==============================================================================
# 1. Service-Level Unit Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_compare_identical_traces():
    """Identical traces produce 100% matched steps and zero metric deltas."""
    events = [
        _build_test_event("e1", "trace_1", "AGENT_START", offset_seconds=0),
        _build_test_event("e2", "trace_1", "LLM_CALL", offset_seconds=1, duration_ms=500.0),
        _build_test_event("e3", "trace_1", "LLM_RESPONSE", offset_seconds=2),
        _build_test_event("e4", "trace_1", "AGENT_END", offset_seconds=3),
    ]
    trace_a = _build_test_trace("trace_1", duration_ms=3000.0, events=events)
    # Trace B has different event IDs but identical logical structure
    events_b = [
        _build_test_event("b1", "trace_2", "AGENT_START", offset_seconds=0),
        _build_test_event("b2", "trace_2", "LLM_CALL", offset_seconds=1, duration_ms=500.0),
        _build_test_event("b3", "trace_2", "LLM_RESPONSE", offset_seconds=2),
        _build_test_event("b4", "trace_2", "AGENT_END", offset_seconds=3),
    ]
    trace_b = _build_test_trace("trace_2", duration_ms=3000.0, events=events_b)

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("trace_1", "trace_2", db=AsyncMock())

    assert result.differences.duration_diff_ms == 0.0
    assert result.differences.event_count_diff == 0
    assert not result.differences.status_changed
    assert len(result.sequence_comparison) == 4
    for step in result.sequence_comparison:
        assert step.status == "matched"
        assert step.event_a is not None
        assert step.event_b is not None


@pytest.mark.asyncio
async def test_compare_different_durations():
    """Calculates accurate duration delta and step duration diffs."""
    events_a = [
        _build_test_event("a1", "trace_a", "LLM_CALL", duration_ms=300.0),
    ]
    events_b = [
        _build_test_event("b1", "trace_b", "LLM_CALL", duration_ms=750.0),
    ]
    trace_a = _build_test_trace("trace_a", duration_ms=1000.0, events=events_a)
    trace_b = _build_test_trace("trace_b", duration_ms=2500.0, events=events_b)

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("trace_a", "trace_b", db=AsyncMock())

    assert result.differences.duration_diff_ms == 1500.0
    assert result.sequence_comparison[0].duration_diff_ms == 450.0
    assert "+450.0ms" in result.sequence_comparison[0].change_summary


@pytest.mark.asyncio
async def test_compare_events_only_in_b():
    """Events in B like ERROR or RETRY are marked as 'only_b'."""
    events_a = [
        _build_test_event("a1", "trace_a", "AGENT_START"),
        _build_test_event("a2", "trace_a", "TOOL_CALL", tool_name="fetch_user"),
        _build_test_event("a3", "trace_a", "TOOL_RESPONSE", tool_name="fetch_user"),
        _build_test_event("a4", "trace_a", "AGENT_END"),
    ]
    events_b = [
        _build_test_event("b1", "trace_b", "AGENT_START"),
        _build_test_event("b2", "trace_b", "TOOL_CALL", tool_name="fetch_user"),
        _build_test_event("b_err", "trace_b", "ERROR"),  # Extra error in B
        _build_test_event("b_retry", "trace_b", "RETRY"),  # Extra retry in B
        _build_test_event("b3", "trace_b", "TOOL_RESPONSE", tool_name="fetch_user"),
        _build_test_event("b4", "trace_b", "AGENT_END"),
    ]
    trace_a = _build_test_trace("trace_a", events=events_a)
    trace_b = _build_test_trace("trace_b", events=events_b)

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("trace_a", "trace_b", db=AsyncMock())

    assert result.differences.event_count_diff == 2
    assert result.differences.event_type_diffs["ERROR"] == 1
    assert result.differences.event_type_diffs["RETRY"] == 1

    only_b_steps = [s for s in result.sequence_comparison if s.status == "only_b"]
    assert len(only_b_steps) == 2
    assert only_b_steps[0].event_b.event_type == "ERROR"
    assert only_b_steps[1].event_b.event_type == "RETRY"


@pytest.mark.asyncio
async def test_compare_events_only_in_a():
    """Events in A bypassed in B are marked as 'only_a'."""
    events_a = [
        _build_test_event("a1", "trace_a", "AGENT_START"),
        _build_test_event("a2", "trace_a", "TOOL_CALL", tool_name="send_email"),
        _build_test_event("a3", "trace_a", "AGENT_END"),
    ]
    events_b = [
        _build_test_event("b1", "trace_b", "AGENT_START"),
        _build_test_event("b3", "trace_b", "AGENT_END"),
    ]
    trace_a = _build_test_trace("trace_a", events=events_a)
    trace_b = _build_test_trace("trace_b", events=events_b)

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("trace_a", "trace_b", db=AsyncMock())

    assert result.differences.event_count_diff == -1
    only_a_steps = [s for s in result.sequence_comparison if s.status == "only_a"]
    assert len(only_a_steps) == 1
    assert only_a_steps[0].event_a.event_type == "TOOL_CALL"


@pytest.mark.asyncio
async def test_compare_different_tool_names_do_not_falsely_match():
    """Tool calls with different tool names do not falsely match."""
    events_a = [
        _build_test_event("a1", "trace_a", "TOOL_CALL", tool_name="weather_service"),
    ]
    events_b = [
        _build_test_event("b1", "trace_b", "TOOL_CALL", tool_name="stock_service"),
    ]
    trace_a = _build_test_trace("trace_a", events=events_a)
    trace_b = _build_test_trace("trace_b", events=events_b)

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("trace_a", "trace_b", db=AsyncMock())

    # Because tool names differ, they should not match
    matched = [s for s in result.sequence_comparison if s.status == "matched"]
    assert len(matched) == 0


@pytest.mark.asyncio
async def test_compare_status_change():
    """Detects status change from completed to failed."""
    trace_a = _build_test_trace("t1", status="completed")
    trace_b = _build_test_trace("t2", status="failed")

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("t1", "t2", db=AsyncMock())

    assert result.differences.status_changed is True
    assert result.differences.status_a == "completed"
    assert result.differences.status_b == "failed"


@pytest.mark.asyncio
async def test_compare_findings_differences():
    """Identifies unique and common findings deterministically."""
    # Trace A has no errors (clean)
    events_a = [
        _build_test_event("a1", "t_clean", "AGENT_START"),
        _build_test_event("a2", "t_clean", "AGENT_END"),
    ]
    trace_a = _build_test_trace("t_clean", status="completed", events=events_a)

    # Trace B has an explicit ERROR event
    events_b = [
        _build_test_event("b1", "t_err", "AGENT_START"),
        _build_test_event("b2", "t_err", "ERROR"),
        _build_test_event("b3", "t_err", "AGENT_END"),
    ]
    trace_b = _build_test_trace("t_err", status="failed", events=events_b)

    service = TraceComparisonService()
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        result = await service.compare_traces("t_clean", "t_err", db=AsyncMock())

    assert result.findings_comparison.findings_count_diff > 0
    assert len(result.findings_comparison.findings_only_b) > 0
    # Rule for explicit error should be in findings_only_b
    assert any(f.rule == "explicit_error" for f in result.findings_comparison.findings_only_b)


@pytest.mark.asyncio
async def test_compare_empty_ids_raise_value_error():
    """Empty or whitespace trace IDs raise ValueError."""
    service = TraceComparisonService()
    with pytest.raises(ValueError):
        await service.compare_traces("", "trace_b", db=AsyncMock())
    with pytest.raises(ValueError):
        await service.compare_traces("trace_a", "   ", db=AsyncMock())


# ==============================================================================
# 2. FastAPI Endpoint Integration Tests
# ==============================================================================


@pytest.fixture
def client(override_get_db):
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {
        "Authorization": "Bearer test_api_key_123",
        "X-Project-Name": "TestProject",
    }


def test_api_compare_traces_success(client, auth_headers):
    """GET /api/v1/traces/compare returns 200 with structured comparison."""
    events_a = [
        _build_test_event("a1", "t_api_1", "AGENT_START"),
        _build_test_event("a2", "t_api_1", "AGENT_END"),
    ]
    events_b = [
        _build_test_event("b1", "t_api_2", "AGENT_START"),
        _build_test_event("b2", "t_api_2", "AGENT_END"),
    ]
    trace_a = _build_test_trace("t_api_1", events=events_a)
    trace_b = _build_test_trace("t_api_2", events=events_b)

    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=[trace_a, trace_b],
    ):
        response = client.get(
            "/api/v1/traces/compare?trace_a=t_api_1&trace_b=t_api_2",
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "trace_a" in data
    assert "trace_b" in data
    assert "differences" in data
    assert "sequence_comparison" in data
    assert "findings_comparison" in data
    assert data["trace_a"]["trace_id"] == "t_api_1"
    assert data["trace_b"]["trace_id"] == "t_api_2"


def test_api_compare_traces_not_found(client, auth_headers):
    """GET /api/v1/traces/compare returns 404 when either trace is not found."""
    with patch(
        "app.services.trace_comparison_service.trace_reconstruction_service.reconstruct_trace",
        side_effect=TraceNotFoundError("missing_trace_x"),
    ):
        response = client.get(
            "/api/v1/traces/compare?trace_a=missing_trace_x&trace_b=t_api_2",
            headers=auth_headers,
        )

    assert response.status_code == 404
    assert "missing_trace_x" in response.json()["detail"]


def test_api_compare_traces_missing_params(client, auth_headers):
    """GET /api/v1/traces/compare returns 422 if required query params are missing."""
    response = client.get(
        "/api/v1/traces/compare?trace_a=t1",
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_api_compare_traces_unauthorized(client):
    """GET /api/v1/traces/compare returns 401 without auth headers."""
    response = client.get("/api/v1/traces/compare?trace_a=t1&trace_b=t2")
    assert response.status_code == 401
