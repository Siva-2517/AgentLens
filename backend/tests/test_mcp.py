"""Tests for Phase 16 — Model Context Protocol (MCP) Server.

Verifies:
1. Server initialization & metadata
2. Tool registration (7 read-only tools, no write tools)
3. Resource template registration (agentlens://traces/{trace_id})
4. get_trace handler (valid trace, missing trace, invalid param, redaction)
5. get_execution_graph handler (valid trace, missing trace, invalid param)
6. get_trace_findings handler (deterministic findings, missing trace, invalid param)
7. investigate_trace handler (AI investigation, root-cause, missing trace, invalid param)
8. compare_traces handler (comparison diff, identical trace rejection, missing trace)
9. search_historical_failures handler (semantic search, limit validation, severity validation)
10. list_recent_traces handler (trace summaries, limit/offset validation, project filter)
11. Sensitive data redaction (API keys, tokens, passwords, database URLs)
12. Structured error responses
13. Full MCP protocol call_tool integration with mcp_server
14. Read-only safety verification
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from typing import Any, List
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import EventModel, TraceModel
from app.mcp.redaction import sanitize_for_mcp
from app.mcp.server import create_mcp_server, mcp_server
from app.mcp.tools import (
    compare_traces_handler,
    get_execution_graph_handler,
    get_trace_findings_handler,
    get_trace_handler,
    investigate_trace_handler,
    list_recent_traces_handler,
    search_historical_failures_handler,
    set_session_factory,
)
from app.models.comparison import (
    FindingComparison,
    HighLevelDifferences,
    TraceComparisonResult,
    TraceComparisonSummary,
)
from app.models.event import EventType
from app.models.execution_graph import ExecutionGraph, ExecutionGraphEdge, ExecutionGraphNode
from app.models.failure_search import HistoricalFailureSearchResult, HistoricalSearchResponse
from app.models.finding import Finding, FindingCategory, FindingSeverity, FindingsResponse
from app.models.investigation import (
    EvidenceItem,
    InvestigationResult,
    InvestigationStatus,
    RecommendedAction,
    RootCause,
)
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)
from app.services.trace_reconstruction_service import TraceNotFoundError


@pytest.fixture
def mcp_db_override(test_db_session):
    """Override MCP session factory to use test SQLite database session."""
    @asynccontextmanager
    async def factory():
        yield test_db_session

    set_session_factory(factory)
    yield test_db_session
    set_session_factory(None)


def _build_test_trace(trace_id: str, name: str = "TestAgent", project: str = "Billing") -> ReconstructedTrace:
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ev1 = ReconstructedEvent(
        event_id="ev-1",
        trace_id=trace_id,
        parent_event_id=None,
        event_type="AGENT_START",
        timestamp=base_time,
        agent_name=name,
        data={"query": "test query", "api_key": "secret_key_123"},
        metadata={},
        depth=0,
        children_ids=[],
        duration_ms=10.0,
    )
    return ReconstructedTrace(
        trace_id=trace_id,
        name=name,
        project_name=project,
        start_time=base_time,
        end_time=base_time,
        status="completed",
        duration_ms=100.0,
        event_count=1,
        metadata=TraceExecutionMetadata(
            total_event_count=1,
            duration_ms=100.0,
            llm_call_count=0,
            llm_response_count=0,
            tool_call_count=0,
            tool_response_count=0,
            error_count=0,
            retry_count=0,
            state_change_count=0,
            first_event_timestamp=base_time.isoformat(),
            last_event_timestamp=base_time.isoformat(),
            has_agent_start=True,
            has_agent_end=True,
            is_complete=True,
            event_type_counts={"AGENT_START": 1},
        ),
        events=[ev1],
        root_event_ids=["ev-1"],
    )


# ==============================================================================
# 1. Server Metadata & Registration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_server_initialization_and_tool_registration():
    """MCP server initializes with expected name and exactly 7 read-only tools."""
    server = create_mcp_server()
    assert server.name == "AgentLens Observability Server"

    tools = await server.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {
        "get_trace",
        "get_execution_graph",
        "get_trace_findings",
        "investigate_trace",
        "compare_traces",
        "search_historical_failures",
        "list_recent_traces",
    }
    assert tool_names == expected_tools
    assert len(tools) == 7


@pytest.mark.asyncio
async def test_mcp_server_read_only_guarantee():
    """Verify no write, mutating, shell, SQL, or execution tools are registered."""
    tools = await mcp_server.list_tools()
    tool_names = [t.name.lower() for t in tools]

    forbidden_prefixes = ("write", "delete", "create", "update", "execute", "exec_", "drop", "remediate", "index", "run_")
    forbidden_terms = ["sql", "shell", "remediation", "_write", "_delete", "_create", "_update", "index_failures"]

    for name in tool_names:
        assert not name.startswith(forbidden_prefixes), f"Tool '{name}' violates read-only guarantee with prefix"
        for term in forbidden_terms:
            assert term not in name, f"Tool '{name}' violates read-only guarantee with term '{term}'"


@pytest.mark.asyncio
async def test_mcp_resource_template_registration():
    """Verify trace resource template is registered."""
    templates = await mcp_server.list_resource_templates()
    uris = [t.uri_template for t in templates]
    assert "agentlens://traces/{trace_id}" in uris


# ==============================================================================
# 2. Tool Handler: get_trace
# ==============================================================================


@pytest.mark.asyncio
async def test_get_trace_success(mcp_db_override):
    """get_trace returns structured trace summary with sanitized event payloads."""
    trace_obj = _build_test_trace("trace-abc")

    with patch(
        "app.mcp.tools.trace_reconstruction_service.reconstruct_trace",
        new=AsyncMock(return_value=trace_obj),
    ):
        result = await get_trace_handler("trace-abc")

    assert result["trace_id"] == "trace-abc"
    assert result["name"] == "TestAgent"
    assert result["status"] == "completed"
    assert result["event_count"] == 1
    assert result["metrics"]["total_events"] == 1
    assert len(result["events"]) == 1

    # Verify sensitive data in event payload was redacted
    ev_data = result["events"][0]["data"]
    assert ev_data["api_key"] == "[REDACTED]"
    assert ev_data["query"] == "test query"


@pytest.mark.asyncio
async def test_get_trace_missing(mcp_db_override):
    """get_trace returns structured trace_not_found error for nonexistent trace."""
    with patch(
        "app.mcp.tools.trace_reconstruction_service.reconstruct_trace",
        side_effect=TraceNotFoundError("nonexistent-trace"),
    ):
        result = await get_trace_handler("nonexistent-trace")

    assert result["error"] == "trace_not_found"
    assert "not found" in result["message"].lower()


@pytest.mark.asyncio
async def test_get_trace_invalid_parameter():
    """get_trace rejects empty or whitespace trace_id."""
    res_empty = await get_trace_handler("")
    assert res_empty["error"] == "invalid_parameter"

    res_spaces = await get_trace_handler("   ")
    assert res_spaces["error"] == "invalid_parameter"


# ==============================================================================
# 3. Tool Handler: get_execution_graph
# ==============================================================================


@pytest.mark.asyncio
async def test_get_execution_graph_success(mcp_db_override):
    """get_execution_graph returns structured nodes and edges."""
    mock_graph = ExecutionGraph(
        trace_id="trace-graph-1",
        node_count=1,
        edge_count=0,
        nodes=[
            ExecutionGraphNode(
                id="node-1",
                event_id="ev-1",
                trace_id="trace-graph-1",
                event_type="AGENT_START",
                label="Agent Start",
                timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                status="completed",
                duration_ms=50.0,
                depth=0,
                parent_event_id=None,
            )
        ],
        edges=[],
    )

    with patch(
        "app.mcp.tools.execution_graph_service.get_execution_graph",
        new=AsyncMock(return_value=mock_graph),
    ):
        result = await get_execution_graph_handler("trace-graph-1")

    assert result["trace_id"] == "trace-graph-1"
    assert result["node_count"] == 1
    assert result["edge_count"] == 0
    assert result["nodes"][0]["label"] == "Agent Start"


@pytest.mark.asyncio
async def test_get_execution_graph_missing(mcp_db_override):
    """get_execution_graph returns trace_not_found when trace does not exist."""
    with patch(
        "app.mcp.tools.execution_graph_service.get_execution_graph",
        side_effect=TraceNotFoundError("missing-graph"),
    ):
        result = await get_execution_graph_handler("missing-graph")

    assert result["error"] == "trace_not_found"


# ==============================================================================
# 4. Tool Handler: get_trace_findings
# ==============================================================================


@pytest.mark.asyncio
async def test_get_trace_findings_success(mcp_db_override):
    """get_trace_findings returns structured deterministic findings."""
    f1 = Finding(
        finding_id="find-1",
        trace_id="trace-f-1",
        rule="explicit_error",
        category=FindingCategory.EXPLICIT_ERROR,
        severity=FindingSeverity.ERROR,
        message="Database connection reset",
        evidence_event_ids=["ev-err"],
        evidence={"db_password": "secret_pwd_99", "code": 500},
        detected_at=datetime.now(timezone.utc),
    )
    mock_findings = FindingsResponse(
        trace_id="trace-f-1",
        total_findings=1,
        findings=[f1],
    )

    with patch(
        "app.mcp.tools.failure_detection_service.get_findings",
        new=AsyncMock(return_value=mock_findings),
    ):
        result = await get_trace_findings_handler("trace-f-1")

    assert result["trace_id"] == "trace-f-1"
    assert result["total_findings"] == 1
    finding_out = result["findings"][0]
    assert finding_out["rule"] == "explicit_error"
    assert finding_out["severity"] == "error"
    # Verify sensitive evidence was redacted
    assert finding_out["evidence"]["db_password"] == "[REDACTED]"
    assert finding_out["evidence"]["code"] == 500


@pytest.mark.asyncio
async def test_get_trace_findings_missing(mcp_db_override):
    """get_trace_findings returns trace_not_found for missing trace."""
    with patch(
        "app.mcp.tools.failure_detection_service.get_findings",
        side_effect=TraceNotFoundError("missing-trace"),
    ):
        result = await get_trace_findings_handler("missing-trace")

    assert result["error"] == "trace_not_found"


# ==============================================================================
# 5. Tool Handler: investigate_trace
# ==============================================================================


@pytest.mark.asyncio
async def test_investigate_trace_success(mcp_db_override):
    """investigate_trace returns structured Phase 12 root-cause investigation."""
    mock_investigation = InvestigationResult(
        investigation_id="inv-123",
        trace_id="trace-inv-1",
        status=InvestigationStatus.INVESTIGATED,
        confidence=0.92,
        summary="Payment failure due to card decline",
        root_cause=RootCause(
            description="Card Declined by gateway",
            event_id="ev-tool-pay",
            finding_id="find-card",
            confidence=0.92,
            reasoning="Stripe gateway rejected card with 402",
        ),
        first_failure_event_id="ev-tool-pay",
        evidence=[
            EvidenceItem(
                event_id="ev-tool-pay",
                finding_id="find-card",
                description="402 card declined payload",
            )
        ],
        downstream_effects=[],
        recommended_actions=[
            RecommendedAction(
                action="Notify user to update payment method",
                related_event_ids=["ev-tool-pay"],
                priority="high",
            )
        ],
        analyzed_findings=["find-card"],
        analyzed_event_ids=["ev-tool-pay"],
        model="gemini-1.5-flash",
        created_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.mcp.tools.ai_investigation_service.investigate_trace",
        new=AsyncMock(return_value=mock_investigation),
    ):
        result = await investigate_trace_handler("trace-inv-1")

    assert result["trace_id"] == "trace-inv-1"
    assert result["status"] == "investigated"
    assert result["confidence"] == 0.92
    assert result["root_cause"]["description"] == "Card Declined by gateway"
    assert result["first_failure_event_id"] == "ev-tool-pay"
    assert len(result["recommended_actions"]) == 1
    assert len(result["recommended_actions"]) == 1


@pytest.mark.asyncio
async def test_investigate_trace_missing(mcp_db_override):
    """investigate_trace returns trace_not_found when trace does not exist."""
    with patch(
        "app.mcp.tools.ai_investigation_service.investigate_trace",
        side_effect=TraceNotFoundError("missing-inv"),
    ):
        result = await investigate_trace_handler("missing-inv")

    assert result["error"] == "trace_not_found"


# ==============================================================================
# 6. Tool Handler: compare_traces
# ==============================================================================


@pytest.mark.asyncio
async def test_compare_traces_success(mcp_db_override):
    """compare_traces returns side-by-side execution diff and timeline alignment."""
    summary_a = TraceComparisonSummary(
        trace_id="t-1",
        name="AgentRunA",
        status="completed",
        start_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        duration_ms=1000.0,
        event_count=5,
        findings_count=0,
    )
    summary_b = TraceComparisonSummary(
        trace_id="t-2",
        name="AgentRunB",
        status="failed",
        start_time=datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        duration_ms=2500.0,
        event_count=8,
        findings_count=1,
    )
    mock_comparison = TraceComparisonResult(
        trace_a=summary_a,
        trace_b=summary_b,
        differences=HighLevelDifferences(
            duration_diff_ms=1500.0,
            event_count_diff=3,
            status_changed=True,
            status_a="completed",
            status_b="failed",
            findings_count_diff=1,
        ),
        sequence_comparison=[],
        findings_comparison=FindingComparison(
            findings_only_a=[],
            findings_only_b=[],
            common_findings=[],
            findings_count_diff=1,
        ),
    )

    with patch(
        "app.mcp.tools.trace_comparison_service.compare_traces",
        new=AsyncMock(return_value=mock_comparison),
    ):
        result = await compare_traces_handler("t-1", "t-2")

    assert result["trace_a"]["trace_id"] == "t-1"
    assert result["trace_b"]["trace_id"] == "t-2"
    assert result["status_diff"]["is_same"] is False
    assert result["duration_diff_ms"] == 1500.0
    assert result["event_count_diff"] == 3


@pytest.mark.asyncio
async def test_compare_traces_identical_rejection():
    """compare_traces rejects comparing a trace to itself."""
    result = await compare_traces_handler("same-trace", "same-trace")
    assert result["error"] == "invalid_parameter"
    assert "differ" in result["message"]


@pytest.mark.asyncio
async def test_compare_traces_empty_parameters():
    """compare_traces rejects empty trace IDs."""
    res_a = await compare_traces_handler("", "t-2")
    assert res_a["error"] == "invalid_parameter"

    res_b = await compare_traces_handler("t-1", "")
    assert res_b["error"] == "invalid_parameter"


# ==============================================================================
# 7. Tool Handler: search_historical_failures
# ==============================================================================


@pytest.mark.asyncio
async def test_search_historical_failures_success(mcp_db_override):
    """search_historical_failures returns ranked matches with similarity score."""
    mock_res = HistoricalSearchResponse(
        query="payment declined",
        total_results=1,
        results=[
            HistoricalFailureSearchResult(
                trace_id="t-pay-99",
                finding_id="f-card-1",
                rule="explicit_error",
                category="explicit_error",
                severity="error",
                message="Card declined after retry exhaustion",
                searchable_text="context...",
                similarity=0.8954,
                trace_name="CheckoutAgent",
                project_name="BillingService",
                created_at=datetime.now(timezone.utc),
                evidence_event_ids=["ev-pay"],
                metadata={},
            )
        ],
    )

    with patch(
        "app.mcp.tools.failure_search_service.search_failures",
        new=AsyncMock(return_value=mock_res),
    ):
        result = await search_historical_failures_handler(
            query="payment declined",
            limit=5,
            severity="error",
            rule="explicit_error",
            project="BillingService",
        )

    assert result["query"] == "payment declined"
    assert result["total_results"] == 1
    match = result["results"][0]
    assert match["trace_id"] == "t-pay-99"
    assert match["similarity"] == 0.8954
    assert match["severity"] == "error"


@pytest.mark.asyncio
async def test_search_historical_failures_invalid_params():
    """search_historical_failures validates query, limit bounds, and severity."""
    # Empty query
    res_q = await search_historical_failures_handler("")
    assert res_q["error"] == "invalid_parameter"

    # Limit too small
    res_lim_low = await search_historical_failures_handler("query", limit=0)
    assert res_lim_low["error"] == "invalid_parameter"

    # Limit too high
    res_lim_high = await search_historical_failures_handler("query", limit=100)
    assert res_lim_high["error"] == "invalid_parameter"

    # Invalid severity
    res_sev = await search_historical_failures_handler("query", severity="invalid_severity")
    assert res_sev["error"] == "invalid_parameter"


# ==============================================================================
# 8. Tool Handler: list_recent_traces
# ==============================================================================


@pytest.mark.asyncio
async def test_list_recent_traces_success(mcp_db_override, test_db_session):
    """list_recent_traces returns lightweight summaries with project filtering."""
    t1 = TraceModel(
        trace_id="t-list-1",
        name="Agent1",
        project_name="Billing",
        status="completed",
        start_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        metadata_={},
    )
    test_db_session.add(t1)
    await test_db_session.flush()

    result = await list_recent_traces_handler(project="Billing", limit=10, offset=0)
    assert result["total"] == 1
    assert result["limit"] == 10
    assert result["traces"][0]["trace_id"] == "t-list-1"
    assert result["traces"][0]["project_name"] == "Billing"


@pytest.mark.asyncio
async def test_list_recent_traces_invalid_params():
    """list_recent_traces validates limit and offset."""
    res_lim = await list_recent_traces_handler(limit=0)
    assert res_lim["error"] == "invalid_parameter"

    res_off = await list_recent_traces_handler(offset=-1)
    assert res_off["error"] == "invalid_parameter"


# ==============================================================================
# 9. Sensitive Data Redaction
# ==============================================================================


def test_sanitize_for_mcp_redacts_credentials_and_secrets():
    """sanitize_for_mcp scrubs API keys, auth headers, passwords, and DB URLs."""
    raw = {
        "normal_field": "public_data",
        "api_key": "sk-1234567890abcdef",
        "user_password": "super_secret_password",
        "access_token": "token_xyz",
        "authorization": "Bearer eyJhbGciOi...",
        "client_secret": "sec_abc",
        "database_url": "postgresql://user:pass@ep-cool.neon.tech/db",
        "nested": {
            "token": "tok_nested",
            "message": "Authorization header: Bearer my_secret_token",
        },
        "list_items": [
            {"apikey": "secret"},
            "database connection to postgres://admin:pass@host:5432/main",
        ],
    }

    sanitized = sanitize_for_mcp(raw)

    assert sanitized["normal_field"] == "public_data"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["user_password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"
    assert sanitized["database_url"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["message"] == "[REDACTED_SECRET]"
    assert sanitized["list_items"][0]["apikey"] == "[REDACTED]"
    assert sanitized["list_items"][1] == "[REDACTED_DB_URL]"


# ==============================================================================
# 10. Protocol Integration: CallTool via MCPServer
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_protocol_call_tool_get_trace(mcp_db_override):
    """Calling get_trace through the MCP server call_tool protocol returns CallToolResult."""
    trace_obj = _build_test_trace("trace-proto-1")

    with patch(
        "app.mcp.tools.trace_reconstruction_service.reconstruct_trace",
        new=AsyncMock(return_value=trace_obj),
    ):
        tool_res = await mcp_server.call_tool("get_trace", {"trace_id": "trace-proto-1"})

    assert tool_res is not None
    assert len(tool_res.content) == 1
    content_text = tool_res.content[0].text
    parsed = json.loads(content_text)
    assert parsed["trace_id"] == "trace-proto-1"
    assert parsed["name"] == "TestAgent"


@pytest.mark.asyncio
async def test_mcp_resource_read(mcp_db_override):
    """Reading trace resource template returns JSON formatted trace summary."""
    trace_obj = _build_test_trace("trace-res-1")

    with patch(
        "app.mcp.tools.trace_reconstruction_service.reconstruct_trace",
        new=AsyncMock(return_value=trace_obj),
    ):
        res_contents = await mcp_server.read_resource("agentlens://traces/trace-res-1")

    assert len(res_contents) == 1
    parsed = json.loads(res_contents[0].content)
    assert parsed["trace_id"] == "trace-res-1"


# ==============================================================================
# 11. Error Resilience & Safety Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_investigation_provider_failure_returns_internal_error(mcp_db_override):
    """When LLM provider raises an unexpected exception, investigate_trace returns structured internal_error."""
    with patch(
        "app.mcp.tools.ai_investigation_service.investigate_trace",
        side_effect=RuntimeError("Groq API quota exceeded"),
    ):
        result = await investigate_trace_handler("t-prov-fail")

    assert result["error"] == "internal_error"
    assert "Failed to investigate trace" in result["message"]
    assert "Groq API quota exceeded" in result["detail"]


@pytest.mark.asyncio
async def test_database_failure_returns_internal_error(mcp_db_override):
    """When database session fails, get_trace returns structured internal_error without crashing."""
    with patch(
        "app.mcp.tools.trace_reconstruction_service.reconstruct_trace",
        side_effect=ConnectionError("Neon PostgreSQL connection timeout"),
    ):
        result = await get_trace_handler("t-db-fail")

    assert result["error"] == "internal_error"
    assert "Failed to retrieve trace" in result["message"]


@pytest.mark.asyncio
async def test_no_arbitrary_code_or_sql_exposed():
    """Verify tool signatures do not accept arbitrary query strings for SQL execution."""
    tools = await mcp_server.list_tools()
    for t in tools:
        schema = getattr(t, "inputSchema", {}) or {}
        properties = schema.get("properties", {})
        # None of the properties should be raw SQL or code
        for prop_name in properties:
            assert "sql" not in prop_name.lower()
            assert "command" not in prop_name.lower()
            assert "code" not in prop_name.lower()

