"""Tests for Phase 7 — Trace Reconstruction Engine.

Verifies:
1. Empty trace (zero events)
2. Single-event trace
3. Normal ordered trace
4. Out-of-order events
5. Equal timestamps deterministic ordering
6. Parent-child relationships & hierarchy depths
7. Missing parent event (broken reference)
8. Error event
9. Retry event
10. Complete trace lifecycle
11. Incomplete trace (missing AGENT_END or running)
12. Duration calculation (trace times and event times fallback)
13. Event counts and event_type_counts dictionary
14. LLM call & response count
15. Tool call & response count
16. Trace-not-found service exception
17. API endpoint GET /api/v1/traces/{trace_id} success
18. API endpoint GET /api/v1/traces/{trace_id} 404 when not found
19. API endpoint GET /api/v1/traces/{trace_id} 401 when unauthenticated
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import EventModel, TraceModel
from app.main import app
from app.models.event import EventType
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)


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
        "X-AgentLens-Project": "test-project",
    }


def make_dt(seconds_offset: float = 0.0) -> datetime:
    """Helper to create timezone-aware UTC datetime."""
    base = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds_offset)


# ==============================================================================
# Unit & Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_empty_trace(test_db_session):
    """1. Test reconstructing a trace with zero events."""
    trace = TraceModel(
        trace_id="trace-empty-001",
        name="empty-agent",
        project_name="test-project",
        start_time=make_dt(0),
        end_time=make_dt(10),
        status="completed",
        metadata_={"run": 1},
    )
    test_db_session.add(trace)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-empty-001", test_db_session
    )

    assert reconstructed.trace_id == "trace-empty-001"
    assert reconstructed.event_count == 0
    assert reconstructed.events == []
    assert reconstructed.root_event_ids == []
    assert reconstructed.duration_ms == 10000.0  # 10s difference
    assert reconstructed.metadata.total_event_count == 0
    assert reconstructed.metadata.llm_call_count == 0
    assert reconstructed.metadata.tool_call_count == 0
    assert reconstructed.metadata.first_event_timestamp is None
    assert reconstructed.metadata.last_event_timestamp is None
    assert reconstructed.metadata.is_complete is False


@pytest.mark.asyncio
async def test_single_event_trace(test_db_session):
    """2. Test reconstructing a trace with exactly one event."""
    t0 = make_dt(0)
    trace = TraceModel(
        trace_id="trace-single-001",
        name="single-agent",
        project_name="test-project",
        start_time=t0,
        end_time=None,
        status="running",
        metadata_={},
    )
    ev = EventModel(
        event_id="ev-1",
        trace_id="trace-single-001",
        parent_event_id=None,
        event_type=EventType.AGENT_START.value,
        timestamp=t0,
        data={"query": "hello"},
        metadata_={},
    )
    test_db_session.add_all([trace, ev])
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-single-001", test_db_session
    )

    assert reconstructed.event_count == 1
    assert len(reconstructed.events) == 1
    assert reconstructed.events[0].event_id == "ev-1"
    assert reconstructed.events[0].depth == 0
    assert reconstructed.metadata.has_agent_start is True
    assert reconstructed.metadata.has_agent_end is False
    assert reconstructed.metadata.is_complete is False


@pytest.mark.asyncio
async def test_normal_ordered_trace(test_db_session):
    """3. Test reconstructing a normal, cleanly ordered full trace."""
    t0 = make_dt(0)
    trace = TraceModel(
        trace_id="trace-normal-001",
        name="support-agent",
        project_name="test-project",
        start_time=t0,
        end_time=make_dt(5),
        status="completed",
        metadata_={},
    )
    events = [
        EventModel(event_id="e1", trace_id="trace-normal-001", parent_event_id=None, event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="e2", trace_id="trace-normal-001", parent_event_id="e1", event_type=EventType.LLM_CALL.value, timestamp=make_dt(1)),
        EventModel(event_id="e3", trace_id="trace-normal-001", parent_event_id="e2", event_type=EventType.LLM_RESPONSE.value, timestamp=make_dt(2)),
        EventModel(event_id="e4", trace_id="trace-normal-001", parent_event_id="e1", event_type=EventType.TOOL_CALL.value, timestamp=make_dt(3)),
        EventModel(event_id="e5", trace_id="trace-normal-001", parent_event_id="e4", event_type=EventType.TOOL_RESPONSE.value, timestamp=make_dt(4)),
        EventModel(event_id="e6", trace_id="trace-normal-001", parent_event_id=None, event_type=EventType.AGENT_END.value, timestamp=make_dt(5)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-normal-001", test_db_session
    )

    assert reconstructed.event_count == 6
    assert [e.event_id for e in reconstructed.events] == ["e1", "e2", "e3", "e4", "e5", "e6"]
    assert reconstructed.metadata.is_complete is True
    assert reconstructed.metadata.llm_call_count == 1
    assert reconstructed.metadata.llm_response_count == 1
    assert reconstructed.metadata.tool_call_count == 1
    assert reconstructed.metadata.tool_response_count == 1


@pytest.mark.asyncio
async def test_out_of_order_events(test_db_session):
    """4. Test that events inserted in shuffled order are sorted chronologically."""
    trace = TraceModel(
        trace_id="trace-shuffle-001",
        name="shuffle-agent",
        start_time=make_dt(0),
        status="completed",
        metadata_={},
    )
    # Insert in reverse order
    events = [
        EventModel(event_id="ev-end", trace_id="trace-shuffle-001", event_type=EventType.AGENT_END.value, timestamp=make_dt(10)),
        EventModel(event_id="ev-tool", trace_id="trace-shuffle-001", event_type=EventType.TOOL_CALL.value, timestamp=make_dt(5)),
        EventModel(event_id="ev-start", trace_id="trace-shuffle-001", event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-shuffle-001", test_db_session
    )

    ordered_ids = [e.event_id for e in reconstructed.events]
    assert ordered_ids == ["ev-start", "ev-tool", "ev-end"]


@pytest.mark.asyncio
async def test_equal_timestamps_deterministic(test_db_session):
    """5. Test that events with identical timestamps are ordered deterministically."""
    same_time = make_dt(1.5)
    trace = TraceModel(
        trace_id="trace-equal-ts-001",
        name="equal-agent",
        start_time=make_dt(0),
        status="running",
        metadata_={},
    )
    # Add multiple events at the exact same timestamp
    events = [
        EventModel(event_id="ev-b", trace_id="trace-equal-ts-001", event_type=EventType.LLM_CALL.value, timestamp=same_time),
        EventModel(event_id="ev-a", trace_id="trace-equal-ts-001", event_type=EventType.AGENT_START.value, timestamp=same_time),
        EventModel(event_id="ev-c", trace_id="trace-equal-ts-001", event_type=EventType.LLM_RESPONSE.value, timestamp=same_time),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-equal-ts-001", test_db_session
    )

    # AGENT_START (priority 0) -> LLM_CALL (priority 1) -> LLM_RESPONSE (priority 2)
    types_in_order = [e.event_type for e in reconstructed.events]
    assert types_in_order == [
        EventType.AGENT_START.value,
        EventType.LLM_CALL.value,
        EventType.LLM_RESPONSE.value,
    ]


@pytest.mark.asyncio
async def test_parent_child_relationships(test_db_session):
    """6. Test parent-child hierarchy, depth calculation, and children_ids."""
    trace = TraceModel(
        trace_id="trace-tree-001",
        name="tree-agent",
        start_time=make_dt(0),
        status="completed",
        metadata_={},
    )
    # root -> child1 -> grandchild
    #      -> child2
    events = [
        EventModel(event_id="root", trace_id="trace-tree-001", parent_event_id=None, event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="child1", trace_id="trace-tree-001", parent_event_id="root", event_type=EventType.LLM_CALL.value, timestamp=make_dt(1)),
        EventModel(event_id="grandchild", trace_id="trace-tree-001", parent_event_id="child1", event_type=EventType.LLM_RESPONSE.value, timestamp=make_dt(2)),
        EventModel(event_id="child2", trace_id="trace-tree-001", parent_event_id="root", event_type=EventType.TOOL_CALL.value, timestamp=make_dt(3)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-tree-001", test_db_session
    )

    event_by_id = {e.event_id: e for e in reconstructed.events}

    assert event_by_id["root"].depth == 0
    assert set(event_by_id["root"].children_ids) == {"child1", "child2"}
    assert reconstructed.root_event_ids == ["root"]

    assert event_by_id["child1"].depth == 1
    assert event_by_id["child1"].children_ids == ["grandchild"]

    assert event_by_id["grandchild"].depth == 2
    assert event_by_id["grandchild"].children_ids == []

    assert event_by_id["child2"].depth == 1


@pytest.mark.asyncio
async def test_missing_parent_event(test_db_session):
    """7. Test that an event referencing a nonexistent parent does not crash."""
    trace = TraceModel(
        trace_id="trace-orphan-001",
        name="orphan-agent",
        start_time=make_dt(0),
        status="completed",
        metadata_={},
    )
    events = [
        EventModel(event_id="valid-root", trace_id="trace-orphan-001", parent_event_id=None, event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="broken-child", trace_id="trace-orphan-001", parent_event_id="ghost-parent-999", event_type=EventType.TOOL_CALL.value, timestamp=make_dt(1)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    # Must not raise KeyError or exception
    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-orphan-001", test_db_session
    )

    assert reconstructed.event_count == 2
    broken = next(e for e in reconstructed.events if e.event_id == "broken-child")
    # Gracefully treated as root or depth 0
    assert broken.depth == 0
    assert broken.parent_event_id == "ghost-parent-999"
    assert "broken-child" in reconstructed.root_event_ids


@pytest.mark.asyncio
async def test_error_event(test_db_session):
    """8. Test error event counting and inclusion in reconstructed trace."""
    trace = TraceModel(
        trace_id="trace-error-001",
        name="failing-agent",
        start_time=make_dt(0),
        status="failed",
        metadata_={},
    )
    events = [
        EventModel(event_id="e1", trace_id="trace-error-001", event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="e2", trace_id="trace-error-001", event_type=EventType.ERROR.value, timestamp=make_dt(1), data={"error": "Connection timeout"}),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-error-001", test_db_session
    )

    assert reconstructed.metadata.error_count == 1
    assert reconstructed.status == "failed"


@pytest.mark.asyncio
async def test_retry_event(test_db_session):
    """9. Test retry event counting in reconstructed trace."""
    trace = TraceModel(
        trace_id="trace-retry-001",
        name="retry-agent",
        start_time=make_dt(0),
        status="running",
        metadata_={},
    )
    events = [
        EventModel(event_id="e1", trace_id="trace-retry-001", event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="e2", trace_id="trace-retry-001", event_type=EventType.RETRY.value, timestamp=make_dt(1), data={"attempt": 1}),
        EventModel(event_id="e3", trace_id="trace-retry-001", event_type=EventType.RETRY.value, timestamp=make_dt(2), data={"attempt": 2}),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-retry-001", test_db_session
    )

    assert reconstructed.metadata.retry_count == 2


@pytest.mark.asyncio
async def test_complete_trace_lifecycle(test_db_session):
    """10. Test complete trace lifecycle: AGENT_START + AGENT_END + status=completed."""
    trace = TraceModel(
        trace_id="trace-complete-001",
        name="complete-agent",
        start_time=make_dt(0),
        end_time=make_dt(4),
        status="completed",
        metadata_={},
    )
    events = [
        EventModel(event_id="e1", trace_id="trace-complete-001", event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="e2", trace_id="trace-complete-001", event_type=EventType.AGENT_END.value, timestamp=make_dt(4)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-complete-001", test_db_session
    )

    assert reconstructed.metadata.has_agent_start is True
    assert reconstructed.metadata.has_agent_end is True
    assert reconstructed.metadata.is_complete is True


@pytest.mark.asyncio
async def test_incomplete_trace(test_db_session):
    """11. Test incomplete trace: AGENT_START without AGENT_END and status=running."""
    trace = TraceModel(
        trace_id="trace-incomp-001",
        name="incomp-agent",
        start_time=make_dt(0),
        end_time=None,
        status="running",
        metadata_={},
    )
    events = [
        EventModel(event_id="e1", trace_id="trace-incomp-001", event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="e2", trace_id="trace-incomp-001", event_type=EventType.LLM_CALL.value, timestamp=make_dt(1)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-incomp-001", test_db_session
    )

    assert reconstructed.metadata.has_agent_start is True
    assert reconstructed.metadata.has_agent_end is False
    assert reconstructed.metadata.is_complete is False


@pytest.mark.asyncio
async def test_duration_calculation(test_db_session):
    """12. Test duration calculation (from trace end_time and event timestamp fallback)."""
    # Case A: trace has start_time and end_time
    trace_a = TraceModel(
        trace_id="trace-dur-a",
        name="agent-a",
        start_time=make_dt(0),
        end_time=make_dt(2.5),
        status="completed",
        metadata_={},
    )
    test_db_session.add(trace_a)
    await test_db_session.commit()

    rec_a = await trace_reconstruction_service.reconstruct_trace("trace-dur-a", test_db_session)
    assert rec_a.duration_ms == 2500.0

    # Case B: trace has end_time=None, duration calculated from first & last events
    trace_b = TraceModel(
        trace_id="trace-dur-b",
        name="agent-b",
        start_time=make_dt(0),
        end_time=None,
        status="running",
        metadata_={},
    )
    events_b = [
        EventModel(event_id="b1", trace_id="trace-dur-b", event_type=EventType.AGENT_START.value, timestamp=make_dt(1)),
        EventModel(event_id="b2", trace_id="trace-dur-b", event_type=EventType.AGENT_END.value, timestamp=make_dt(4)),
    ]
    test_db_session.add(trace_b)
    test_db_session.add_all(events_b)
    await test_db_session.commit()

    rec_b = await trace_reconstruction_service.reconstruct_trace("trace-dur-b", test_db_session)
    assert rec_b.duration_ms == 3000.0  # 4s - 1s = 3000ms


@pytest.mark.asyncio
async def test_event_counts_and_dict(test_db_session):
    """13. Test event counts dictionary."""
    trace = TraceModel(
        trace_id="trace-counts-001",
        name="counts-agent",
        start_time=make_dt(0),
        status="running",
        metadata_={},
    )
    events = [
        EventModel(event_id="c1", trace_id="trace-counts-001", event_type=EventType.AGENT_START.value, timestamp=make_dt(0)),
        EventModel(event_id="c2", trace_id="trace-counts-001", event_type=EventType.STATE_CHANGE.value, timestamp=make_dt(1)),
        EventModel(event_id="c3", trace_id="trace-counts-001", event_type=EventType.STATE_CHANGE.value, timestamp=make_dt(2)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-counts-001", test_db_session
    )

    assert reconstructed.metadata.total_event_count == 3
    assert reconstructed.metadata.state_change_count == 2
    assert reconstructed.metadata.event_type_counts == {
        EventType.AGENT_START.value: 1,
        EventType.STATE_CHANGE.value: 2,
    }


@pytest.mark.asyncio
async def test_llm_call_count(test_db_session):
    """14. Test LLM call and response counting."""
    trace = TraceModel(
        trace_id="trace-llm-001",
        name="llm-agent",
        start_time=make_dt(0),
        status="running",
        metadata_={},
    )
    events = [
        EventModel(event_id="l1", trace_id="trace-llm-001", event_type=EventType.LLM_CALL.value, timestamp=make_dt(1)),
        EventModel(event_id="l2", trace_id="trace-llm-001", event_type=EventType.LLM_RESPONSE.value, timestamp=make_dt(2)),
        EventModel(event_id="l3", trace_id="trace-llm-001", event_type=EventType.LLM_CALL.value, timestamp=make_dt(3)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-llm-001", test_db_session
    )

    assert reconstructed.metadata.llm_call_count == 2
    assert reconstructed.metadata.llm_response_count == 1


@pytest.mark.asyncio
async def test_tool_call_count(test_db_session):
    """15. Test tool call and response counting."""
    trace = TraceModel(
        trace_id="trace-tool-001",
        name="tool-agent",
        start_time=make_dt(0),
        status="running",
        metadata_={},
    )
    events = [
        EventModel(event_id="t1", trace_id="trace-tool-001", event_type=EventType.TOOL_CALL.value, timestamp=make_dt(1)),
        EventModel(event_id="t2", trace_id="trace-tool-001", event_type=EventType.TOOL_RESPONSE.value, timestamp=make_dt(2)),
        EventModel(event_id="t3", trace_id="trace-tool-001", event_type=EventType.TOOL_CALL.value, timestamp=make_dt(3)),
        EventModel(event_id="t4", trace_id="trace-tool-001", event_type=EventType.TOOL_RESPONSE.value, timestamp=make_dt(4)),
    ]
    test_db_session.add(trace)
    test_db_session.add_all(events)
    await test_db_session.commit()

    reconstructed = await trace_reconstruction_service.reconstruct_trace(
        "trace-tool-001", test_db_session
    )

    assert reconstructed.metadata.tool_call_count == 2
    assert reconstructed.metadata.tool_response_count == 2


@pytest.mark.asyncio
async def test_trace_not_found(test_db_session):
    """16. Test that non-existent trace raises TraceNotFoundError."""
    with pytest.raises(TraceNotFoundError) as exc_info:
        await trace_reconstruction_service.reconstruct_trace(
            "nonexistent-trace-id", test_db_session
        )
    assert exc_info.value.trace_id == "nonexistent-trace-id"


# ==============================================================================
# API Endpoint Tests: GET /api/v1/traces/{trace_id}
# ==============================================================================


def test_api_get_reconstructed_trace(client, auth_headers):
    """17. Test API returns reconstructed trace successfully with 200 OK."""
    # Create trace
    trace_payload = {
        "trace_id": "api-trace-001",
        "name": "api-agent",
        "start_time": make_dt(0).isoformat(),
        "status": "running",
        "metadata": {"env": "test"},
    }
    client.post("/api/v1/traces", json=trace_payload, headers=auth_headers)

    # Ingest event
    event_payload = [
        {
            "event_id": "api-ev-1",
            "trace_id": "api-trace-001",
            "event_type": "AGENT_START",
            "timestamp": make_dt(0.5).isoformat(),
            "data": {"task": "test"},
            "metadata": {},
        }
    ]
    client.post("/api/v1/events", json=event_payload, headers=auth_headers)

    # GET /api/v1/traces/{trace_id}
    res = client.get("/api/v1/traces/api-trace-001", headers=auth_headers)
    assert res.status_code == 200

    data = res.json()
    assert data["trace_id"] == "api-trace-001"
    assert data["name"] == "api-agent"
    assert data["event_count"] == 1
    assert len(data["events"]) == 1
    assert data["events"][0]["event_id"] == "api-ev-1"
    assert data["metadata"]["has_agent_start"] is True


def test_api_get_reconstructed_trace_not_found(client, auth_headers):
    """18. Test API returns 404 when trace does not exist."""
    res = client.get("/api/v1/traces/nonexistent-xyz-999", headers=auth_headers)
    assert res.status_code == 404
    data = res.json()
    assert "not found" in data["detail"].lower()


def test_api_get_reconstructed_trace_unauthorized(client):
    """19. Test API returns 401 when unauthenticated."""
    res = client.get("/api/v1/traces/any-trace-id")
    assert res.status_code == 401
