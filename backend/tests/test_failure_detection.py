"""Tests for Phase 11 — Deterministic Failure & Anomaly Detection.

Verifies:
1. Rule 1: Explicit ERROR event (positive, negative, critical on failed status)
2. Rule 2: Unresolved retry (positive with failed trace/terminal error, negative with clean recovery)
3. Rule 3: Repeated tool calls (positive >= threshold, negative < threshold, different inputs negative, boundary)
4. Rule 4: Missing tool response (positive, negative with child/parent response)
5. Rule 5: Missing LLM response (positive, negative with child/parent response)
6. Rule 6: Invalid event lifecycle (missing start, missing end on completed, reversed order, clean lifecycle)
7. Rule 7: Potential execution loop (positive repeated pattern, negative varied sequence)
8. Rule 8: Abnormally high retry count (positive, negative)
9. Multiple simultaneous findings in complex trace
10. Empty trace handling
11. Incomplete/running trace handling
12. Missing parent event resilience
13. Deterministic finding IDs and ordering
14. Custom detection thresholds override
15. API: Valid trace with findings (200)
16. API: Clean trace with empty findings (200)
17. API: Nonexistent trace (404)
18. API: Missing/invalid authentication (401)
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import EventModel, TraceModel
from app.db.repositories import EventRepository, TraceRepository
from app.main import app
from app.models.event import EventType
from app.models.finding import (
    DetectionConfig,
    FindingCategory,
    FindingSeverity,
    generate_finding_id,
)
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)
from app.services.failure_detection_service import failure_detection_service


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


def make_trace(
    trace_id: str = "tr-test",
    status: str = "completed",
    events: list[ReconstructedEvent] = None,
    has_start: bool = True,
    has_end: bool = True,
) -> ReconstructedTrace:
    """Helper to construct ReconstructedTrace with default valid metadata."""
    ev_list = events or []
    counts: dict[str, int] = {}
    for ev in ev_list:
        counts[ev.event_type] = counts.get(ev.event_type, 0) + 1

    return ReconstructedTrace(
        trace_id=trace_id,
        name="test-agent",
        project_name="test-project",
        start_time=make_dt(0),
        end_time=make_dt(10) if status != "running" else None,
        status=status,
        event_count=len(ev_list),
        metadata=TraceExecutionMetadata(
            total_event_count=len(ev_list),
            has_agent_start=has_start or ("AGENT_START" in counts),
            has_agent_end=has_end or ("AGENT_END" in counts),
            error_count=counts.get("ERROR", 0),
            retry_count=counts.get("RETRY", 0),
            tool_call_count=counts.get("TOOL_CALL", 0),
            tool_response_count=counts.get("TOOL_RESPONSE", 0),
            llm_call_count=counts.get("LLM_CALL", 0),
            llm_response_count=counts.get("LLM_RESPONSE", 0),
            event_type_counts=counts,
        ),
        events=ev_list,
        root_event_ids=[e.event_id for e in ev_list if not e.parent_event_id],
    )


# ==============================================================================
# Rule 1: Explicit ERROR event
# ==============================================================================


def test_rule1_explicit_error_positive():
    """Detects explicit ERROR event with message and evidence ID."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t1", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(
            event_id="e2",
            trace_id="t1",
            event_type="ERROR",
            timestamp=make_dt(1),
            data={"message": "Connection to payment gateway timed out"},
        ),
        ReconstructedEvent(event_id="e3", trace_id="t1", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t1", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)

    error_findings = [f for f in findings if f.category == FindingCategory.EXPLICIT_ERROR]
    assert len(error_findings) == 1
    assert error_findings[0].rule == "explicit_error"
    assert error_findings[0].severity == FindingSeverity.CRITICAL  # trace status failed
    assert "Connection to payment gateway timed out" in error_findings[0].message
    assert error_findings[0].evidence_event_ids == ["e2"]


def test_rule1_explicit_error_negative():
    """No findings generated when no ERROR events exist."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t1", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="e2", trace_id="t1", event_type="AGENT_END", timestamp=make_dt(1)),
    ]
    trace = make_trace("t1", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.category == FindingCategory.EXPLICIT_ERROR for f in findings)


# ==============================================================================
# Rule 2: Unresolved retry
# ==============================================================================


def test_rule2_unresolved_retry_positive():
    """Detects retry activity that ends in failure or terminates without success."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t2", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="e2", trace_id="t2", event_type="RETRY", timestamp=make_dt(1), data={"attempt": 1}),
        ReconstructedEvent(event_id="e3", trace_id="t2", event_type="RETRY", timestamp=make_dt(2), data={"attempt": 2}),
        ReconstructedEvent(event_id="e4", trace_id="t2", event_type="ERROR", timestamp=make_dt(3), data={"message": "All retries exhausted"}),
        ReconstructedEvent(event_id="e5", trace_id="t2", event_type="AGENT_END", timestamp=make_dt(4)),
    ]
    trace = make_trace("t2", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)

    retry_findings = [f for f in findings if f.rule == "unresolved_retry"]
    assert len(retry_findings) == 1
    assert retry_findings[0].category == FindingCategory.RETRY_EXHAUSTION
    assert "e2" in retry_findings[0].evidence_event_ids
    assert "e3" in retry_findings[0].evidence_event_ids


def test_rule2_unresolved_retry_negative_on_success():
    """Retries that cleanly resolve into successful tool response do not trigger unresolved_retry."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t2", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="e2", trace_id="t2", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "fetch"}),
        ReconstructedEvent(event_id="e3", trace_id="t2", event_type="RETRY", timestamp=make_dt(2), parent_event_id="e2"),
        ReconstructedEvent(event_id="e4", trace_id="t2", event_type="TOOL_RESPONSE", timestamp=make_dt(3), parent_event_id="e2", data={"result": "ok"}),
        ReconstructedEvent(event_id="e5", trace_id="t2", event_type="AGENT_END", timestamp=make_dt(4)),
    ]
    trace = make_trace("t2", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.rule == "unresolved_retry" for f in findings)


# ==============================================================================
# Rule 3: Repeated tool calls
# ==============================================================================


def test_rule3_repeated_tool_calls_positive():
    """Detects repeated tool calls with identical inputs exceeding threshold."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t3", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="t_1", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "search", "inputs": {"q": "weather"}}),
        ReconstructedEvent(event_id="t_2", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(2), data={"name": "search", "inputs": {"q": "weather"}}),
        ReconstructedEvent(event_id="t_3", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(3), data={"name": "search", "inputs": {"q": "weather"}}),
        ReconstructedEvent(event_id="e5", trace_id="t3", event_type="AGENT_END", timestamp=make_dt(4)),
    ]
    trace = make_trace("t3", status="completed", events=events)
    cfg = DetectionConfig(repeated_tool_call_threshold=3)
    findings = failure_detection_service.detect_failures(trace, config=cfg)

    repeated = [f for f in findings if f.category == FindingCategory.REPEATED_TOOL_CALL]
    assert len(repeated) == 1
    assert repeated[0].rule == "repeated_tool_call"
    assert repeated[0].evidence_event_ids == ["t_1", "t_2", "t_3"]
    assert "3 times" in repeated[0].message


def test_rule3_repeated_tool_calls_negative_different_inputs():
    """Does not flag repeated calls if inputs are different."""
    events = [
        ReconstructedEvent(event_id="t_1", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "search", "inputs": {"q": "weather"}}),
        ReconstructedEvent(event_id="t_2", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(2), data={"name": "search", "inputs": {"q": "news"}}),
        ReconstructedEvent(event_id="t_3", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(3), data={"name": "search", "inputs": {"q": "stocks"}}),
    ]
    trace = make_trace("t3", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.category == FindingCategory.REPEATED_TOOL_CALL for f in findings)


def test_rule3_repeated_tool_calls_below_threshold():
    """Does not flag repeated calls when below threshold."""
    events = [
        ReconstructedEvent(event_id="t_1", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "search", "inputs": {"q": "weather"}}),
        ReconstructedEvent(event_id="t_2", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(2), data={"name": "search", "inputs": {"q": "weather"}}),
    ]
    trace = make_trace("t3", status="completed", events=events)
    cfg = DetectionConfig(repeated_tool_call_threshold=3)
    findings = failure_detection_service.detect_failures(trace, config=cfg)
    assert not any(f.category == FindingCategory.REPEATED_TOOL_CALL for f in findings)


# ==============================================================================
# Rule 4: Tool call without response
# ==============================================================================


def test_rule4_tool_call_without_response():
    """Detects TOOL_CALL with no corresponding response."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t4", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="tc1", trace_id="t4", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "order_lookup"}),
        ReconstructedEvent(event_id="e3", trace_id="t4", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t4", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)

    missing = [f for f in findings if f.rule == "missing_tool_response"]
    assert len(missing) == 1
    assert missing[0].category == FindingCategory.MISSING_RESPONSE
    assert missing[0].evidence_event_ids == ["tc1"]
    assert "order_lookup" in missing[0].message


def test_rule4_tool_call_with_response_negative():
    """Does not flag TOOL_CALL when corresponding response exists."""
    events = [
        ReconstructedEvent(event_id="tc1", trace_id="t4", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "order_lookup"}, children_ids=["tr1"]),
        ReconstructedEvent(event_id="tr1", trace_id="t4", event_type="TOOL_RESPONSE", timestamp=make_dt(2), parent_event_id="tc1"),
    ]
    trace = make_trace("t4", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.rule == "missing_tool_response" for f in findings)


# ==============================================================================
# Rule 5: LLM call without response
# ==============================================================================


def test_rule5_llm_call_without_response():
    """Detects LLM_CALL with no corresponding response."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t5", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="llm1", trace_id="t5", event_type="LLM_CALL", timestamp=make_dt(1), data={"model": "gemini-pro"}),
        ReconstructedEvent(event_id="e3", trace_id="t5", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t5", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)

    missing = [f for f in findings if f.rule == "missing_llm_response"]
    assert len(missing) == 1
    assert missing[0].category == FindingCategory.MISSING_RESPONSE
    assert missing[0].evidence_event_ids == ["llm1"]


def test_rule5_llm_call_with_response_negative():
    """Does not flag LLM_CALL when corresponding response exists."""
    events = [
        ReconstructedEvent(event_id="llm1", trace_id="t5", event_type="LLM_CALL", timestamp=make_dt(1), children_ids=["resp1"]),
        ReconstructedEvent(event_id="resp1", trace_id="t5", event_type="LLM_RESPONSE", timestamp=make_dt(2), parent_event_id="llm1"),
    ]
    trace = make_trace("t5", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.rule == "missing_llm_response" for f in findings)


# ==============================================================================
# Rule 6: Invalid event lifecycle
# ==============================================================================


def test_rule6_missing_agent_start():
    """Detects missing AGENT_START in trace."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t6", event_type="TOOL_CALL", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="e2", trace_id="t6", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t6", status="completed", events=events, has_start=False)
    findings = failure_detection_service.detect_failures(trace)

    lifecycle = [f for f in findings if f.rule == "missing_agent_start"]
    assert len(lifecycle) == 1
    assert lifecycle[0].category == FindingCategory.INVALID_LIFECYCLE


def test_rule6_missing_agent_end_on_completed():
    """Detects missing AGENT_END on completed or failed trace."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t6", event_type="AGENT_START", timestamp=make_dt(1)),
    ]
    trace = make_trace("t6", status="completed", events=events, has_start=True, has_end=False)
    findings = failure_detection_service.detect_failures(trace)

    lifecycle = [f for f in findings if f.rule == "missing_agent_end"]
    assert len(lifecycle) == 1
    assert lifecycle[0].category == FindingCategory.INVALID_LIFECYCLE


def test_rule6_running_trace_does_not_flag_missing_end():
    """Trace in 'running' state does not flag missing AGENT_END."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t6", event_type="AGENT_START", timestamp=make_dt(1)),
    ]
    trace = make_trace("t6", status="running", events=events, has_start=True, has_end=False)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.rule == "missing_agent_end" for f in findings)


def test_rule6_invalid_lifecycle_order():
    """Detects AGENT_END occurring before AGENT_START."""
    events = [
        ReconstructedEvent(event_id="e_end", trace_id="t6", event_type="AGENT_END", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="e_start", trace_id="t6", event_type="AGENT_START", timestamp=make_dt(5)),
    ]
    trace = make_trace("t6", status="completed", events=events, has_start=True, has_end=True)
    findings = failure_detection_service.detect_failures(trace)

    ordering = [f for f in findings if f.rule == "invalid_lifecycle_order"]
    assert len(ordering) == 1
    assert ordering[0].evidence_event_ids == ["e_start", "e_end"]


# ==============================================================================
# Rule 7: Potential execution loop
# ==============================================================================


def test_rule7_execution_loop_detected():
    """Detects repeated sequences of actions exceeding loop threshold."""
    events = [
        ReconstructedEvent(event_id="e0", trace_id="t7", event_type="AGENT_START", timestamp=make_dt(0)),
        # Sequence A -> B repeating 3 times
        ReconstructedEvent(event_id="e1", trace_id="t7", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "check_stock"}),
        ReconstructedEvent(event_id="e2", trace_id="t7", event_type="STATE_CHANGE", timestamp=make_dt(2), metadata={"state_type": "eval"}),
        ReconstructedEvent(event_id="e3", trace_id="t7", event_type="TOOL_CALL", timestamp=make_dt(3), data={"name": "check_stock"}),
        ReconstructedEvent(event_id="e4", trace_id="t7", event_type="STATE_CHANGE", timestamp=make_dt(4), metadata={"state_type": "eval"}),
        ReconstructedEvent(event_id="e5", trace_id="t7", event_type="TOOL_CALL", timestamp=make_dt(5), data={"name": "check_stock"}),
        ReconstructedEvent(event_id="e6", trace_id="t7", event_type="STATE_CHANGE", timestamp=make_dt(6), metadata={"state_type": "eval"}),
        ReconstructedEvent(event_id="e7", trace_id="t7", event_type="AGENT_END", timestamp=make_dt(7)),
    ]
    trace = make_trace("t7", status="completed", events=events)
    cfg = DetectionConfig(loop_threshold=3)
    findings = failure_detection_service.detect_failures(trace, config=cfg)

    loops = [f for f in findings if f.category == FindingCategory.EXECUTION_LOOP]
    assert len(loops) >= 1
    assert loops[0].rule == "execution_loop_detected"
    assert len(loops[0].evidence_event_ids) == 6


def test_rule7_execution_loop_negative():
    """Normal varied actions do not trigger execution loop."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t7", event_type="LLM_CALL", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="e2", trace_id="t7", event_type="TOOL_CALL", timestamp=make_dt(2), data={"name": "read"}),
        ReconstructedEvent(event_id="e3", trace_id="t7", event_type="STATE_CHANGE", timestamp=make_dt(3)),
        ReconstructedEvent(event_id="e4", trace_id="t7", event_type="TOOL_CALL", timestamp=make_dt(4), data={"name": "write"}),
    ]
    trace = make_trace("t7", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert not any(f.category == FindingCategory.EXECUTION_LOOP for f in findings)


# ==============================================================================
# Rule 8: Abnormally high retry count
# ==============================================================================


def test_rule8_high_retry_count():
    """Detects total retry count >= threshold."""
    events = [
        ReconstructedEvent(event_id="r1", trace_id="t8", event_type="RETRY", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="r2", trace_id="t8", event_type="RETRY", timestamp=make_dt(2)),
        ReconstructedEvent(event_id="r3", trace_id="t8", event_type="RETRY", timestamp=make_dt(3)),
    ]
    trace = make_trace("t8", status="completed", events=events)
    cfg = DetectionConfig(retry_threshold=3)
    findings = failure_detection_service.detect_failures(trace, config=cfg)

    high_retry = [f for f in findings if f.rule == "high_retry_count"]
    assert len(high_retry) == 1
    assert high_retry[0].evidence_event_ids == ["r1", "r2", "r3"]


# ==============================================================================
# General Engine & Robustness Tests
# ==============================================================================


def test_multiple_findings_simultaneous():
    """Trace with multiple distinct issues returns all findings correctly."""
    events = [
        ReconstructedEvent(event_id="e_err", trace_id="t9", event_type="ERROR", timestamp=make_dt(1), data={"message": "db error"}),
        ReconstructedEvent(event_id="e_tc", trace_id="t9", event_type="TOOL_CALL", timestamp=make_dt(2), data={"name": "fetch"}),
        # missing tool response
        ReconstructedEvent(event_id="r1", trace_id="t9", event_type="RETRY", timestamp=make_dt(3)),
        ReconstructedEvent(event_id="r2", trace_id="t9", event_type="RETRY", timestamp=make_dt(4)),
        ReconstructedEvent(event_id="r3", trace_id="t9", event_type="RETRY", timestamp=make_dt(5)),
    ]
    trace = make_trace("t9", status="failed", events=events, has_start=False)
    findings = failure_detection_service.detect_failures(trace)

    rules = {f.rule for f in findings}
    assert "explicit_error" in rules
    assert "missing_tool_response" in rules
    assert "missing_agent_start" in rules
    assert "high_retry_count" in rules


def test_empty_trace_handling():
    """Empty trace does not crash the service."""
    trace = make_trace("t_empty", status="completed", events=[], has_start=False, has_end=False)
    findings = failure_detection_service.detect_failures(trace)
    assert isinstance(findings, list)
    # Should report missing lifecycle start and end
    rules = {f.rule for f in findings}
    assert "missing_agent_start" in rules
    assert "missing_agent_end" in rules


def test_missing_parent_event_resilience():
    """Events referencing nonexistent parent IDs do not break response matching."""
    events = [
        ReconstructedEvent(event_id="tc1", trace_id="t10", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "lookup"}),
        ReconstructedEvent(event_id="tr1", trace_id="t10", event_type="TOOL_RESPONSE", timestamp=make_dt(2), parent_event_id="nonexistent-parent"),
    ]
    trace = make_trace("t10", status="running", events=events)
    findings = failure_detection_service.detect_failures(trace)
    # tc1 has no matching response because tr1 references an invalid parent
    missing = [f for f in findings if f.rule == "missing_tool_response"]
    assert len(missing) == 1
    assert missing[0].evidence_event_ids == ["tc1"]


def test_deterministic_ordering_and_ids():
    """Identical trace yields identical finding IDs and deterministic ordering."""
    events = [
        ReconstructedEvent(event_id="err1", trace_id="t_det", event_type="ERROR", timestamp=make_dt(1), data={"message": "fail"}),
        ReconstructedEvent(event_id="tc1", trace_id="t_det", event_type="TOOL_CALL", timestamp=make_dt(2)),
    ]
    trace = make_trace("t_det", status="failed", events=events)

    run1 = failure_detection_service.detect_failures(trace)
    run2 = failure_detection_service.detect_failures(trace)

    assert len(run1) == len(run2)
    for f1, f2 in zip(run1, run2):
        assert f1.finding_id == f2.finding_id
        assert f1.rule == f2.rule
        assert f1.severity == f2.severity
        assert f1.evidence_event_ids == f2.evidence_event_ids


# ==============================================================================
# API Endpoint Tests: GET /api/v1/traces/{trace_id}/findings
# ==============================================================================


async def test_api_findings_valid_trace(client, auth_headers, test_db_session):
    """API successfully returns findings for persisted trace."""
    # Persist trace
    trace = TraceModel(
        trace_id="trace-api-findings-01",
        name="test-agent",
        project_name="test-project",
        start_time=make_dt(0),
        status="failed",
        metadata_={},
    )
    test_db_session.add(trace)

    # Persist events: AGENT_START + ERROR + AGENT_END
    test_db_session.add(
        EventModel(
            event_id="ev-start",
            trace_id="trace-api-findings-01",
            event_type=EventType.AGENT_START.value,
            timestamp=make_dt(0),
            data={},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-err",
            trace_id="trace-api-findings-01",
            event_type=EventType.ERROR.value,
            timestamp=make_dt(1),
            data={"message": "Unrecoverable database failure"},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-end",
            trace_id="trace-api-findings-01",
            event_type=EventType.AGENT_END.value,
            timestamp=make_dt(2),
            data={},
            metadata_={},
        )
    )
    await test_db_session.commit()

    resp = client.get(
        "/api/v1/traces/trace-api-findings-01/findings",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == "trace-api-findings-01"
    assert data["total_findings"] >= 1
    explicit_errs = [f for f in data["findings"] if f["rule"] == "explicit_error"]
    assert len(explicit_errs) == 1
    assert explicit_errs[0]["category"] == "explicit_error"
    assert explicit_errs[0]["severity"] == "critical"
    assert explicit_errs[0]["evidence_event_ids"] == ["ev-err"]


async def test_api_findings_clean_trace(client, auth_headers, test_db_session):
    """API returns total_findings = 0 for a completely clean execution trace."""
    trace = TraceModel(
        trace_id="trace-api-findings-clean",
        name="test-agent",
        project_name="test-project",
        start_time=make_dt(0),
        end_time=make_dt(2),
        status="completed",
        metadata_={},
    )
    test_db_session.add(trace)

    test_db_session.add(
        EventModel(
            event_id="ev-clean-1",
            trace_id="trace-api-findings-clean",
            event_type=EventType.AGENT_START.value,
            timestamp=make_dt(0),
            data={},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-clean-2",
            trace_id="trace-api-findings-clean",
            event_type=EventType.AGENT_END.value,
            timestamp=make_dt(1),
            data={},
            metadata_={},
        )
    )
    await test_db_session.commit()

    resp = client.get(
        "/api/v1/traces/trace-api-findings-clean/findings",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == "trace-api-findings-clean"
    assert data["total_findings"] == 0
    assert data["findings"] == []


def test_api_findings_trace_not_found(client, auth_headers):
    """API returns 404 for nonexistent trace."""
    resp = client.get(
        "/api/v1/traces/nonexistent-trace-id-xyz/findings",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_findings_unauthenticated(client):
    """API returns 401 when API key is missing or invalid."""
    resp = client.get("/api/v1/traces/some-trace/findings")
    assert resp.status_code == 401

    resp2 = client.get(
        "/api/v1/traces/some-trace/findings",
        headers={"Authorization": "Bearer bad-key"},
    )
    assert resp2.status_code == 401
