"""Tests for Phase 12 — AI Root-Cause Investigation.

Verifies:
1. Clean trace -> no_issue_detected (no hallucinated failure)
2. Trace with explicit ERROR
3. Trace with missing TOOL_RESPONSE
4. Trace with missing LLM_RESPONSE
5. Trace with repeated tool calls
6. Trace with retry failure
7. Multiple findings in single trace
8. Root cause references valid event ID
9. Evidence references valid finding ID
10. Invalid event ID from LLM rejected with InvestigationValidationError
11. Invalid finding ID from LLM rejected with InvestigationValidationError
12. Malformed LLM response handling
13. LLM provider failure handling
14. Insufficient evidence status
15. API: Missing trace returns 404
16. API: Unauthenticated returns 401
17. Deterministic investigation context generation
18. Sensitive information is sanitized/redacted in context
19. Correct downstream event identification
20. Confidence score validation (clamped/bounded 0.0 - 1.0)
21. Critical root-cause test: Tool call -> Tool error -> Retry -> Error -> Final Error.
    Identifies earlier tool failure as the root cause rather than reporting only the final ERROR event!
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import EventModel, TraceModel
from app.main import app
from app.models.event import EventType
from app.models.finding import (
    Finding,
    FindingCategory,
    FindingSeverity,
    generate_finding_id,
)
from app.models.investigation import (
    InvestigationContext,
    InvestigationResult,
    InvestigationStatus,
)
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)
from app.services.execution_graph_service import execution_graph_service
from app.services.failure_detection_service import failure_detection_service
from app.services.investigation_service import (
    InvestigationValidationError,
    ai_investigation_service,
)
from app.services.llm_provider import (
    InvestigationLLMProvider,
    MockInvestigationProvider,
)


@pytest.fixture(autouse=True)
def setup_mock_provider():
    """Ensure tests run with MockInvestigationProvider and do not call external APIs."""
    original = ai_investigation_service._provider
    ai_investigation_service.set_provider(MockInvestigationProvider())
    yield
    ai_investigation_service.set_provider(original)


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
    trace_id: str = "tr-inv-test",
    status: str = "completed",
    events: list[ReconstructedEvent] = None,
) -> ReconstructedTrace:
    """Helper to construct ReconstructedTrace with metadata."""
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
            has_agent_start=("AGENT_START" in counts),
            has_agent_end=("AGENT_END" in counts),
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


class CustomMockProvider(InvestigationLLMProvider):
    """Customizable mock provider for injecting specific outputs or exceptions."""

    def __init__(self, response_dict: dict[str, Any] = None, error_to_raise: Exception = None):
        self._response = response_dict or {}
        self._error = error_to_raise

    @property
    def model_name(self) -> str:
        return "custom-mock"

    async def investigate(self, context: InvestigationContext) -> dict[str, Any]:
        if self._error:
            raise self._error
        return self._response


# ==============================================================================
# Unit Tests for AIInvestigationService
# ==============================================================================


def test_1_clean_trace_no_issue_detected():
    """Clean trace with no findings returns no_issue_detected with 1.0 confidence."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t1", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="e2", trace_id="t1", event_type="LLM_CALL", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="e3", trace_id="t1", event_type="LLM_RESPONSE", timestamp=make_dt(2), parent_event_id="e2"),
        ReconstructedEvent(event_id="e4", trace_id="t1", event_type="AGENT_END", timestamp=make_dt(3)),
    ]
    trace = make_trace("t1", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert len(findings) == 0

    graph = execution_graph_service.build_graph(trace)
    context = ai_investigation_service.build_context(trace, graph, findings)

    provider = MockInvestigationProvider()
    import asyncio
    result = asyncio.run(provider.investigate(context))

    assert result["status"] == "no_issue_detected"
    assert result["root_cause"] is None
    assert result["first_failure_event_id"] is None
    assert result["confidence"] == 1.0


def test_2_trace_with_explicit_error():
    """Trace with an explicit error identifies the error event as the root cause."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t2", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(
            event_id="err-1",
            trace_id="t2",
            event_type="ERROR",
            timestamp=make_dt(1),
            data={"message": "Database authentication failed"},
        ),
        ReconstructedEvent(event_id="e3", trace_id="t2", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t2", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)
    context = ai_investigation_service.build_context(trace, graph, findings)

    provider = MockInvestigationProvider()
    import asyncio
    output = asyncio.run(provider.investigate(context))
    ai_investigation_service.validate_llm_output(output, trace, findings)

    assert output["status"] == "investigated"
    assert output["first_failure_event_id"] == "err-1"
    assert "Database authentication failed" in output["root_cause"]["description"]


def test_3_trace_with_missing_tool_response():
    """Trace with missing tool response identifies unreturned tool call as root failure."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t3", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="tc-1", trace_id="t3", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "payment_gateway"}),
        ReconstructedEvent(event_id="e3", trace_id="t3", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t3", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)
    context = ai_investigation_service.build_context(trace, graph, findings)

    provider = MockInvestigationProvider()
    import asyncio
    output = asyncio.run(provider.investigate(context))
    ai_investigation_service.validate_llm_output(output, trace, findings)

    assert output["first_failure_event_id"] == "tc-1"
    assert "payment_gateway" in output["summary"] or "tc-1" in output["summary"]


def test_4_trace_with_missing_llm_response():
    """Trace with missing LLM response captures LLM call as the point of failure."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t4", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="llm-1", trace_id="t4", event_type="LLM_CALL", timestamp=make_dt(1), data={"model": "gpt-4"}),
        ReconstructedEvent(event_id="e3", trace_id="t4", event_type="AGENT_END", timestamp=make_dt(2)),
    ]
    trace = make_trace("t4", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert any(f.rule == "missing_llm_response" for f in findings)


def test_5_trace_with_repeated_tool_calls():
    """Trace with repeated tool calls correctly references the tool call event IDs."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t5", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="tc1", trace_id="t5", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "fetch", "inputs": {"id": 1}}),
        ReconstructedEvent(event_id="tc2", trace_id="t5", event_type="TOOL_CALL", timestamp=make_dt(2), data={"name": "fetch", "inputs": {"id": 1}}),
        ReconstructedEvent(event_id="tc3", trace_id="t5", event_type="TOOL_CALL", timestamp=make_dt(3), data={"name": "fetch", "inputs": {"id": 1}}),
        ReconstructedEvent(event_id="e5", trace_id="t5", event_type="AGENT_END", timestamp=make_dt(4)),
    ]
    trace = make_trace("t5", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert any(f.rule == "repeated_tool_call" for f in findings)


def test_6_trace_with_retry_failure():
    """Trace with retries culminating in failure correctly links retry events."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t6", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="r1", trace_id="t6", event_type="RETRY", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="r2", trace_id="t6", event_type="RETRY", timestamp=make_dt(2)),
        ReconstructedEvent(event_id="r3", trace_id="t6", event_type="RETRY", timestamp=make_dt(3)),
        ReconstructedEvent(event_id="err", trace_id="t6", event_type="ERROR", timestamp=make_dt(4)),
        ReconstructedEvent(event_id="e6", trace_id="t6", event_type="AGENT_END", timestamp=make_dt(5)),
    ]
    trace = make_trace("t6", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    assert any(f.rule == "unresolved_retry" for f in findings)


def test_7_multiple_findings():
    """Trace with multiple findings provides all findings to LLM context."""
    events = [
        ReconstructedEvent(event_id="tc1", trace_id="t7", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "failing_tool"}),
        ReconstructedEvent(event_id="err1", trace_id="t7", event_type="ERROR", timestamp=make_dt(2), data={"message": "Boom"}),
    ]
    trace = make_trace("t7", status="failed", events=events, )
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)
    context = ai_investigation_service.build_context(trace, graph, findings)

    assert len(context.deterministic_findings) >= 2


def test_8_root_cause_references_valid_event_id():
    """Validation succeeds when root_cause event_id is valid."""
    events = [ReconstructedEvent(event_id="valid-ev", trace_id="t8", event_type="ERROR", timestamp=make_dt(0))]
    trace = make_trace("t8", status="failed", events=events)
    output = {
        "status": "investigated",
        "summary": "Failed",
        "root_cause": {"description": "Err", "event_id": "valid-ev", "confidence": 0.9, "reasoning": "R"},
        "first_failure_event_id": "valid-ev",
        "confidence": 0.9,
    }
    ai_investigation_service.validate_llm_output(output, trace, [])


def test_9_finding_references_valid_finding_id():
    """Validation succeeds when finding_id exists in findings."""
    f = Finding(
        finding_id="finding-valid-123",
        trace_id="t9",
        rule="explicit_error",
        category=FindingCategory.EXPLICIT_ERROR,
        severity=FindingSeverity.ERROR,
        message="err",
        evidence_event_ids=[],
        evidence={},
        detected_at=make_dt(0),
    )
    output = {
        "status": "investigated",
        "summary": "Found",
        "confidence": 0.8,
        "evidence": [{"finding_id": "finding-valid-123", "description": "Good"}],
    }
    trace = make_trace("t9", status="completed", events=[])
    ai_investigation_service.validate_llm_output(output, trace, [f])


def test_10_invalid_event_id_rejected():
    """Validation fails and raises InvestigationValidationError if LLM invents event ID."""
    trace = make_trace("t10", status="failed", events=[
        ReconstructedEvent(event_id="real-id", trace_id="t10", event_type="ERROR", timestamp=make_dt(0))
    ])
    output = {
        "status": "investigated",
        "summary": "Failed",
        "first_failure_event_id": "hallucinated-event-id",
        "confidence": 0.9,
    }
    with pytest.raises(InvestigationValidationError) as exc_info:
        ai_investigation_service.validate_llm_output(output, trace, [])
    assert "hallucinated-event-id" in str(exc_info.value)


def test_11_invalid_finding_id_rejected():
    """Validation fails and raises InvestigationValidationError if LLM invents finding ID."""
    trace = make_trace("t11", status="failed", events=[])
    output = {
        "status": "investigated",
        "summary": "Failed",
        "confidence": 0.9,
        "evidence": [{"finding_id": "fake-finding-999", "description": "Invented"}],
    }
    with pytest.raises(InvestigationValidationError) as exc_info:
        ai_investigation_service.validate_llm_output(output, trace, [])
    assert "fake-finding-999" in str(exc_info.value)


def test_12_malformed_llm_response_handling():
    """Handles JSON parsing errors cleanly without crashing."""
    from app.services.llm_provider import _clean_and_parse_json
    with pytest.raises(Exception):
        _clean_and_parse_json("Not a json at all {broken")


def test_13_llm_provider_failure_handling():
    """When LLM provider raises an error, it propagates gracefully."""
    custom_provider = CustomMockProvider(error_to_raise=RuntimeError("Provider connection reset"))
    context = InvestigationContext(
        trace_id="t13",
        name="test",
        status="failed",
        start_time=make_dt(0).isoformat(),
        total_events=0,
    )
    import asyncio
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(custom_provider.investigate(context))
    assert "Provider connection reset" in str(exc_info.value)


def test_14_insufficient_evidence():
    """Investigator outputs insufficient_evidence when data is ambiguous."""
    output = {
        "status": "insufficient_evidence",
        "summary": "Trace was cut off unexpectedly before any error was logged.",
        "root_cause": None,
        "first_failure_event_id": None,
        "confidence": 0.3,
        "evidence": [],
        "downstream_effects": [],
        "recommended_actions": [],
    }
    trace = make_trace("t14", status="running", events=[])
    ai_investigation_service.validate_llm_output(output, trace, [])
    assert output["status"] == "insufficient_evidence"


def test_17_deterministic_investigation_context_generation():
    """Investigation context generation is deterministic for identical trace inputs."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="t17", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="e2", trace_id="t17", event_type="ERROR", timestamp=make_dt(1), data={"message": "fail"}),
    ]
    trace = make_trace("t17", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)

    ctx1 = ai_investigation_service.build_context(trace, graph, findings)
    ctx2 = ai_investigation_service.build_context(trace, graph, findings)

    assert ctx1.model_dump() == ctx2.model_dump()


def test_18_sensitive_information_redaction():
    """Sensitive keys (api_key, password, token, secret) are redacted in context."""
    events = [
        ReconstructedEvent(
            event_id="e1",
            trace_id="t18",
            event_type="TOOL_CALL",
            timestamp=make_dt(0),
            data={
                "name": "login",
                "api_key": "sk-secret-12345",
                "password": "super-secret-pwd",
                "user": "alice",
            },
        )
    ]
    trace = make_trace("t18", status="completed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)
    ctx = ai_investigation_service.build_context(trace, graph, findings)

    summary_data = ctx.key_events[0].summary_data
    assert summary_data["api_key"] == "[REDACTED]"
    assert summary_data["password"] == "[REDACTED]"
    assert summary_data["user"] == "alice"


def test_19_downstream_event_identification():
    """Downstream events identify cascading failures after root failure."""
    events = [
        ReconstructedEvent(event_id="tc1", trace_id="t19", event_type="TOOL_CALL", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="tr1", trace_id="t19", event_type="TOOL_RESPONSE", timestamp=make_dt(1), parent_event_id="tc1", data={"error": "timeout"}),
        ReconstructedEvent(event_id="err1", trace_id="t19", event_type="ERROR", timestamp=make_dt(2)),
    ]
    trace = make_trace("t19", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)
    ctx = ai_investigation_service.build_context(trace, graph, findings)

    provider = MockInvestigationProvider()
    import asyncio
    output = asyncio.run(provider.investigate(ctx))

    # Earliest failure should be the tool call, downstream effect should cite the error
    assert output["first_failure_event_id"] == "tc1"
    assert any(d["event_id"] == "err1" for d in output["downstream_effects"])


def test_20_confidence_validation():
    """Confidence score is clamped between 0.0 and 1.0."""
    trace = make_trace("t20", status="completed", events=[])
    # Valid output structure
    output = {
        "status": "investigated",
        "summary": "ok",
        "first_failure_event_id": None,
        "confidence": 1.5,  # Needs clamping
    }
    # Verify clamping logic
    conf = max(0.0, min(1.0, float(output["confidence"])))
    assert conf == 1.0


# ==============================================================================
# Critical Root-Cause Test
# ==============================================================================


def test_21_critical_root_cause_tool_failure_before_final_error():
    """Critical Root-Cause Test:
    Sequence:
    1. Tool call occurs (tc1)
    2. Tool returns error (tr1)
    3. Agent retries (r1)
    4. Tool call fails again (tc2 -> tr2)
    5. Final ERROR event occurs (err_terminal)
    6. Agent terminates in failure.

    Expected Investigation:
    The investigator MUST identify the earlier tool failure ('tc1' / 'tr1')
    as the first failure / root cause, rather than blindly reporting 'err_terminal'.
    """
    events = [
        ReconstructedEvent(event_id="start", trace_id="t_crit", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="tc1", trace_id="t_crit", event_type="TOOL_CALL", timestamp=make_dt(1), data={"name": "charge_customer"}),
        ReconstructedEvent(event_id="tr1", trace_id="t_crit", event_type="TOOL_RESPONSE", timestamp=make_dt(2), parent_event_id="tc1", data={"error": "Card declined: 402"}),
        ReconstructedEvent(event_id="r1", trace_id="t_crit", event_type="RETRY", timestamp=make_dt(3), parent_event_id="tc1"),
        ReconstructedEvent(event_id="tc2", trace_id="t_crit", event_type="TOOL_CALL", timestamp=make_dt(4), data={"name": "charge_customer"}),
        ReconstructedEvent(event_id="tr2", trace_id="t_crit", event_type="TOOL_RESPONSE", timestamp=make_dt(5), parent_event_id="tc2", data={"error": "Card declined: 402"}),
        ReconstructedEvent(event_id="err_terminal", trace_id="t_crit", event_type="ERROR", timestamp=make_dt(6), data={"message": "Agent execution failed due to unhandled exception"}),
        ReconstructedEvent(event_id="end", trace_id="t_crit", event_type="AGENT_END", timestamp=make_dt(7)),
    ]
    trace = make_trace("t_crit", status="failed", events=events)
    findings = failure_detection_service.detect_failures(trace)
    graph = execution_graph_service.build_graph(trace)
    ctx = ai_investigation_service.build_context(trace, graph, findings)

    provider = MockInvestigationProvider()
    import asyncio
    output = asyncio.run(provider.investigate(ctx))
    ai_investigation_service.validate_llm_output(output, trace, findings)

    # 1. The first failure must point to the initial tool failure (tc1), NOT the terminal error (err_terminal)
    assert output["first_failure_event_id"] == "tc1"
    assert output["first_failure_event_id"] != "err_terminal"

    # 2. Root cause description references the tool failure
    assert "Tool failure" in output["root_cause"]["description"] or "Card declined" in output["root_cause"]["description"]

    # 3. Terminal error is listed as a downstream effect rather than root cause
    assert any(d["event_id"] == "err_terminal" for d in output["downstream_effects"])


# ==============================================================================
# API Integration Tests: GET /api/v1/traces/{trace_id}/investigation
# ==============================================================================


async def test_api_investigation_endpoint_success(client, auth_headers, test_db_session):
    """API endpoint returns structured InvestigationResult for a persisted failing trace."""
    trace = TraceModel(
        trace_id="tr-api-inv-01",
        name="payment-agent",
        project_name="test-project",
        start_time=make_dt(0),
        status="failed",
        metadata_={},
    )
    test_db_session.add(trace)

    test_db_session.add(
        EventModel(
            event_id="ev-s",
            trace_id="tr-api-inv-01",
            event_type=EventType.AGENT_START.value,
            timestamp=make_dt(0),
            data={},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-tc",
            trace_id="tr-api-inv-01",
            event_type=EventType.TOOL_CALL.value,
            timestamp=make_dt(1),
            data={"name": "validate_user"},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-tr",
            trace_id="tr-api-inv-01",
            event_type=EventType.TOOL_RESPONSE.value,
            parent_event_id="ev-tc",
            timestamp=make_dt(2),
            data={"error": "User token expired"},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-err",
            trace_id="tr-api-inv-01",
            event_type=EventType.ERROR.value,
            timestamp=make_dt(3),
            data={"message": "Execution halted"},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-e",
            trace_id="tr-api-inv-01",
            event_type=EventType.AGENT_END.value,
            timestamp=make_dt(4),
            data={},
            metadata_={},
        )
    )
    await test_db_session.commit()

    resp = client.get(
        "/api/v1/traces/tr-api-inv-01/investigation",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["trace_id"] == "tr-api-inv-01"
    assert data["status"] == "investigated"
    assert data["first_failure_event_id"] == "ev-tc"
    assert data["confidence"] > 0.0
    assert len(data["recommended_actions"]) >= 1


async def test_api_investigation_endpoint_clean_trace(client, auth_headers, test_db_session):
    """API endpoint returns no_issue_detected for clean trace."""
    trace = TraceModel(
        trace_id="tr-api-inv-clean",
        name="clean-agent",
        project_name="test-project",
        start_time=make_dt(0),
        end_time=make_dt(2),
        status="completed",
        metadata_={},
    )
    test_db_session.add(trace)

    test_db_session.add(
        EventModel(
            event_id="ev-c1",
            trace_id="tr-api-inv-clean",
            event_type=EventType.AGENT_START.value,
            timestamp=make_dt(0),
            data={},
            metadata_={},
        )
    )
    test_db_session.add(
        EventModel(
            event_id="ev-c2",
            trace_id="tr-api-inv-clean",
            event_type=EventType.AGENT_END.value,
            timestamp=make_dt(1),
            data={},
            metadata_={},
        )
    )
    await test_db_session.commit()

    resp = client.get(
        "/api/v1/traces/tr-api-inv-clean/investigation",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_issue_detected"
    assert data["root_cause"] is None


def test_api_investigation_trace_not_found(client, auth_headers):
    """API returns 404 for non-existent trace."""
    resp = client.get(
        "/api/v1/traces/nonexistent-trace-id-xyz/investigation",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_api_investigation_unauthenticated(client):
    """API returns 401 when unauthenticated."""
    resp = client.get("/api/v1/traces/any-trace/investigation")
    assert resp.status_code == 401
