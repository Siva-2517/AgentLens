"""Tests for Phase 8 — Execution Graph.

Verifies:
1. Empty trace
2. Single event
3. Multiple events
4. Chronological node ordering
5. Parent-child edge creation
6. Multiple root events
7. Missing parent reference
8. No fake parent node
9. Deterministic node IDs
10. Deterministic edge IDs
11. No duplicate nodes
12. No duplicate edges
13. All supported event types
14. Unknown event type
15. Event duration propagation
16. Trace ID propagation
17. Correct node count
18. Correct edge count
19. API success
20. API authentication failure
21. API trace not found
22. Existing Phase 7 endpoint still works
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)
from app.services.execution_graph_service import execution_graph_service


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
# Unit Tests for ExecutionGraphService
# ==============================================================================


def test_empty_trace():
    """1. Test graph construction with an empty trace."""
    trace = ReconstructedTrace(
        trace_id="tr-empty",
        name="empty-agent",
        start_time=make_dt(0),
        status="completed",
        event_count=0,
        metadata=TraceExecutionMetadata(total_event_count=0),
        events=[],
        root_event_ids=[],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.trace_id == "tr-empty"
    assert graph.nodes == []
    assert graph.edges == []
    assert graph.node_count == 0
    assert graph.edge_count == 0


def test_single_event():
    """2. Test graph construction with a single event."""
    ev = ReconstructedEvent(
        event_id="e-start",
        trace_id="tr-single",
        parent_event_id=None,
        event_type="AGENT_START",
        timestamp=make_dt(0),
    )
    trace = ReconstructedTrace(
        trace_id="tr-single",
        name="single-agent",
        start_time=make_dt(0),
        status="running",
        event_count=1,
        metadata=TraceExecutionMetadata(total_event_count=1),
        events=[ev],
        root_event_ids=["e-start"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.node_count == 1
    assert graph.edge_count == 0
    assert graph.nodes[0].id == "e-start"
    assert graph.nodes[0].label == "Agent Start"


def test_multiple_events():
    """3. Test graph construction with multiple events."""
    events = [
        ReconstructedEvent(event_id="e1", trace_id="tr-multi", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="e2", trace_id="tr-multi", parent_event_id="e1", event_type="LLM_CALL", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="e3", trace_id="tr-multi", parent_event_id="e2", event_type="LLM_RESPONSE", timestamp=make_dt(2)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-multi",
        name="multi-agent",
        start_time=make_dt(0),
        status="running",
        event_count=3,
        metadata=TraceExecutionMetadata(total_event_count=3),
        events=events,
        root_event_ids=["e1"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.node_count == 3
    assert len(graph.nodes) == 3


def test_chronological_node_ordering():
    """4. Test that nodes preserve chronological reconstructed event ordering."""
    events = [
        ReconstructedEvent(event_id="first", trace_id="tr-order", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="middle", trace_id="tr-order", event_type="TOOL_CALL", timestamp=make_dt(5)),
        ReconstructedEvent(event_id="last", trace_id="tr-order", event_type="AGENT_END", timestamp=make_dt(10)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-order",
        name="order-agent",
        start_time=make_dt(0),
        status="completed",
        event_count=3,
        metadata=TraceExecutionMetadata(total_event_count=3),
        events=events,
        root_event_ids=["first"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert [node.id for node in graph.nodes] == ["first", "middle", "last"]


def test_parent_child_edge_creation():
    """5. Test that parent-child edges are correctly created."""
    events = [
        ReconstructedEvent(event_id="p", trace_id="tr-edge", parent_event_id=None, event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="c", trace_id="tr-edge", parent_event_id="p", event_type="LLM_CALL", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-edge",
        name="edge-agent",
        start_time=make_dt(0),
        status="running",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["p"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.edge_count == 1
    edge = graph.edges[0]
    assert edge.source == "p"
    assert edge.target == "c"
    assert edge.relationship == "parent-child"


def test_multiple_root_events():
    """6. Test graph handling multiple root events without parent links."""
    events = [
        ReconstructedEvent(event_id="root_a", trace_id="tr-roots", parent_event_id=None, event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="root_b", trace_id="tr-roots", parent_event_id=None, event_type="STATE_CHANGE", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-roots",
        name="roots-agent",
        start_time=make_dt(0),
        status="running",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["root_a", "root_b"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.node_count == 2
    assert graph.edge_count == 0


def test_missing_parent_reference():
    """7. Test event with a missing parent reference does not crash and preserves node."""
    events = [
        ReconstructedEvent(event_id="orphan", trace_id="tr-missing", parent_event_id="nonexistent-parent", event_type="TOOL_CALL", timestamp=make_dt(0)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-missing",
        name="missing-agent",
        start_time=make_dt(0),
        status="running",
        event_count=1,
        metadata=TraceExecutionMetadata(total_event_count=1),
        events=events,
        root_event_ids=["orphan"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.node_count == 1
    assert graph.nodes[0].id == "orphan"
    assert graph.nodes[0].parent_event_id == "nonexistent-parent"


def test_no_fake_parent_node():
    """8. Test that no fake parent node is fabricated for missing parent reference."""
    events = [
        ReconstructedEvent(event_id="orphan", trace_id="tr-nofake", parent_event_id="missing-parent-id", event_type="TOOL_CALL", timestamp=make_dt(0)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-nofake",
        name="nofake-agent",
        start_time=make_dt(0),
        status="running",
        event_count=1,
        metadata=TraceExecutionMetadata(total_event_count=1),
        events=events,
        root_event_ids=["orphan"],
    )
    graph = execution_graph_service.build_graph(trace)
    node_ids = {n.id for n in graph.nodes}
    assert "missing-parent-id" not in node_ids
    assert graph.edge_count == 0


def test_deterministic_node_ids():
    """9. Test that node IDs deterministically equal event_id without random generation."""
    events = [
        ReconstructedEvent(event_id="fixed-evt-100", trace_id="tr-id", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="fixed-evt-200", trace_id="tr-id", event_type="AGENT_END", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-id",
        name="id-agent",
        start_time=make_dt(0),
        status="completed",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["fixed-evt-100"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.nodes[0].id == "fixed-evt-100"
    assert graph.nodes[1].id == "fixed-evt-200"


def test_deterministic_edge_ids():
    """10. Test that edge IDs follow the deterministic format edge_{source}_{target}."""
    events = [
        ReconstructedEvent(event_id="src_node", trace_id="tr-edge-id", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="tgt_node", trace_id="tr-edge-id", parent_event_id="src_node", event_type="LLM_CALL", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-edge-id",
        name="edge-id-agent",
        start_time=make_dt(0),
        status="running",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["src_node"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.edges[0].id == "edge_src_node_tgt_node"


def test_no_duplicate_nodes():
    """11. Test that no duplicate nodes are created."""
    events = [
        ReconstructedEvent(event_id="n1", trace_id="tr-unique", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="n2", trace_id="tr-unique", event_type="AGENT_END", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-unique",
        name="unique-agent",
        start_time=make_dt(0),
        status="completed",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["n1"],
    )
    graph = execution_graph_service.build_graph(trace)
    node_ids = [n.id for n in graph.nodes]
    assert len(node_ids) == len(set(node_ids))


def test_no_duplicate_edges():
    """12. Test that no duplicate edges are produced."""
    events = [
        ReconstructedEvent(event_id="p1", trace_id="tr-edge-dup", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="c1", trace_id="tr-edge-dup", parent_event_id="p1", event_type="LLM_CALL", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-edge-dup",
        name="dup-edge-agent",
        start_time=make_dt(0),
        status="running",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["p1"],
    )
    graph = execution_graph_service.build_graph(trace)
    edge_ids = [e.id for e in graph.edges]
    assert len(edge_ids) == len(set(edge_ids))


def test_all_supported_event_types():
    """13. Test that all canonical event types produce appropriate human-readable labels."""
    types_and_labels = [
        ("AGENT_START", "Agent Start"),
        ("LLM_CALL", "LLM Call"),
        ("LLM_RESPONSE", "LLM Response"),
        ("TOOL_CALL", "Tool Call"),
        ("TOOL_RESPONSE", "Tool Response"),
        ("STATE_CHANGE", "State Change"),
        ("RETRY", "Retry"),
        ("ERROR", "Error"),
        ("AGENT_END", "Agent End"),
    ]
    events = [
        ReconstructedEvent(
            event_id=f"e-{idx}",
            trace_id="tr-all-types",
            event_type=etype,
            timestamp=make_dt(idx),
        )
        for idx, (etype, _) in enumerate(types_and_labels)
    ]
    trace = ReconstructedTrace(
        trace_id="tr-all-types",
        name="all-types-agent",
        start_time=make_dt(0),
        status="completed",
        event_count=len(events),
        metadata=TraceExecutionMetadata(total_event_count=len(events)),
        events=events,
        root_event_ids=["e-0"],
    )
    graph = execution_graph_service.build_graph(trace)
    for idx, (_, expected_label) in enumerate(types_and_labels):
        assert graph.nodes[idx].label == expected_label


def test_unknown_event_type():
    """14. Test unknown future event types gracefully produce title-formatted labels without errors."""
    ev = ReconstructedEvent(
        event_id="e-custom",
        trace_id="tr-custom",
        event_type="CUSTOM_DYNAMIC_ACTION",
        timestamp=make_dt(0),
    )
    trace = ReconstructedTrace(
        trace_id="tr-custom",
        name="custom-agent",
        start_time=make_dt(0),
        status="running",
        event_count=1,
        metadata=TraceExecutionMetadata(total_event_count=1),
        events=[ev],
        root_event_ids=["e-custom"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.nodes[0].label == "Custom Dynamic Action"
    assert graph.nodes[0].event_type == "CUSTOM_DYNAMIC_ACTION"


def test_event_duration_propagation():
    """15. Test that duration_ms is correctly propagated to the graph node."""
    ev = ReconstructedEvent(
        event_id="e-dur",
        trace_id="tr-dur",
        event_type="TOOL_RESPONSE",
        timestamp=make_dt(0),
        duration_ms=125.75,
    )
    trace = ReconstructedTrace(
        trace_id="tr-dur",
        name="dur-agent",
        start_time=make_dt(0),
        status="running",
        event_count=1,
        metadata=TraceExecutionMetadata(total_event_count=1),
        events=[ev],
        root_event_ids=["e-dur"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.nodes[0].duration_ms == 125.75


def test_trace_id_propagation():
    """16. Test that trace_id is correctly propagated to the graph root and all nodes."""
    expected_trace_id = "test-propagation-trace-xyz"
    events = [
        ReconstructedEvent(event_id="n1", trace_id=expected_trace_id, event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="n2", trace_id=expected_trace_id, event_type="AGENT_END", timestamp=make_dt(1)),
    ]
    trace = ReconstructedTrace(
        trace_id=expected_trace_id,
        name="prop-agent",
        start_time=make_dt(0),
        status="completed",
        event_count=2,
        metadata=TraceExecutionMetadata(total_event_count=2),
        events=events,
        root_event_ids=["n1"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.trace_id == expected_trace_id
    assert all(n.trace_id == expected_trace_id for n in graph.nodes)


def test_correct_node_count():
    """17. Test that node_count matches len(nodes) across varying sizes."""
    events = [
        ReconstructedEvent(event_id=f"node-{i}", trace_id="tr-nc", event_type="STATE_CHANGE", timestamp=make_dt(i))
        for i in range(5)
    ]
    trace = ReconstructedTrace(
        trace_id="tr-nc",
        name="nc-agent",
        start_time=make_dt(0),
        status="running",
        event_count=5,
        metadata=TraceExecutionMetadata(total_event_count=5),
        events=events,
        root_event_ids=["node-0"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.node_count == 5
    assert len(graph.nodes) == 5


def test_correct_edge_count():
    """18. Test that edge_count matches len(edges) across varying graph topologies."""
    # Tree: root -> c1 -> gc1, root -> c2 => 3 edges
    events = [
        ReconstructedEvent(event_id="root", trace_id="tr-ec", event_type="AGENT_START", timestamp=make_dt(0)),
        ReconstructedEvent(event_id="c1", trace_id="tr-ec", parent_event_id="root", event_type="LLM_CALL", timestamp=make_dt(1)),
        ReconstructedEvent(event_id="gc1", trace_id="tr-ec", parent_event_id="c1", event_type="LLM_RESPONSE", timestamp=make_dt(2)),
        ReconstructedEvent(event_id="c2", trace_id="tr-ec", parent_event_id="root", event_type="TOOL_CALL", timestamp=make_dt(3)),
    ]
    trace = ReconstructedTrace(
        trace_id="tr-ec",
        name="ec-agent",
        start_time=make_dt(0),
        status="running",
        event_count=4,
        metadata=TraceExecutionMetadata(total_event_count=4),
        events=events,
        root_event_ids=["root"],
    )
    graph = execution_graph_service.build_graph(trace)
    assert graph.edge_count == 3
    assert len(graph.edges) == 3


# ==============================================================================
# API Endpoint Tests: GET /api/v1/traces/{trace_id}/graph
# ==============================================================================


def test_api_success(client, auth_headers):
    """19. Test API GET /api/v1/traces/{trace_id}/graph returns 200 with ExecutionGraph."""
    trace_id = "api-p8-graph-001"
    trace_payload = {
        "trace_id": trace_id,
        "name": "graph-test-agent",
        "start_time": make_dt(0).isoformat(),
        "status": "running",
        "metadata": {"env": "test"},
    }
    client.post("/api/v1/traces", json=trace_payload, headers=auth_headers)

    events_payload = [
        {
            "event_id": f"{trace_id}-root",
            "trace_id": trace_id,
            "parent_event_id": None,
            "event_type": "AGENT_START",
            "timestamp": make_dt(0.5).isoformat(),
            "data": {"query": "hello"},
            "metadata": {},
        },
        {
            "event_id": f"{trace_id}-child",
            "trace_id": trace_id,
            "parent_event_id": f"{trace_id}-root",
            "event_type": "LLM_CALL",
            "timestamp": make_dt(1.0).isoformat(),
            "data": {"model": "llama"},
            "metadata": {},
        },
    ]
    client.post("/api/v1/events", json=events_payload, headers=auth_headers)

    res = client.get(f"/api/v1/traces/{trace_id}/graph", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["trace_id"] == trace_id
    assert data["node_count"] == 2
    assert data["edge_count"] == 1
    assert data["nodes"][0]["id"] == f"{trace_id}-root"
    assert data["nodes"][1]["id"] == f"{trace_id}-child"
    assert data["edges"][0]["source"] == f"{trace_id}-root"
    assert data["edges"][0]["target"] == f"{trace_id}-child"


def test_api_authentication_failure(client):
    """20. Test API returns 401 when request is unauthenticated."""
    res = client.get("/api/v1/traces/some-trace-id/graph")
    assert res.status_code == 401


def test_api_trace_not_found(client, auth_headers):
    """21. Test API returns 404 when trace does not exist."""
    res = client.get("/api/v1/traces/nonexistent-p8-graph/graph", headers=auth_headers)
    assert res.status_code == 404
    data = res.json()
    assert "not found" in data["detail"].lower()


def test_existing_phase7_endpoint_still_works(client, auth_headers):
    """22. Verify existing Phase 7 endpoint GET /api/v1/traces/{trace_id} continues to work."""
    trace_id = "phase7-intact-001"
    trace_payload = {
        "trace_id": trace_id,
        "name": "intact-agent",
        "start_time": make_dt(0).isoformat(),
        "status": "completed",
        "metadata": {},
    }
    client.post("/api/v1/traces", json=trace_payload, headers=auth_headers)

    res = client.get(f"/api/v1/traces/{trace_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["trace_id"] == trace_id
    assert "metadata" in data
    assert "events" in data
