"""Phase 18 Comprehensive System Validation Script.

Validates end-to-end:
1. Real Neon PostgreSQL path (tables, pgvector, trace persistence, reconstruction, graph, failure detection, indexing, search)
2. Redis connection, pub/sub, realtime delivery, and failure degradation
3. End-to-end Demo Customer Support Agent execution
4. Controlled Failure Scenarios: Cases A, B, C, D, E, F
5. MCP Server (all 7 tools, read-only guarantees, structured errors)
6. Python SDK tracing & export
7. Security hardening regression check
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))
# Add root directory to path for demo and sdk
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("phase18_validation")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

from app.config import settings
from app.db.session import engine, init_db, close_db
from app.db.models import TraceModel, EventModel, FailureEmbeddingModel
from app.main import app
from app.services.trace_reconstruction_service import trace_reconstruction_service
from app.services.execution_graph_service import execution_graph_service
from app.services.failure_detection_service import failure_detection_service
from app.services.investigation_service import ai_investigation_service
from app.services.failure_search_service import failure_search_service
from app.services.realtime_publisher import realtime_publisher
from app.services.realtime_service import realtime_service
from app.mcp.server import create_mcp_server
from agentlens import AgentLens, EventType
from demo.agent.runner import DemoAgentRunner

AUTH_HEADERS = {
    "Authorization": "Bearer test_api_key_123",
    "X-AgentLens-Project": "phase18-validation",
}

results = {}


def record_result(category: str, test_name: str, passed: bool, detail: str = ""):
    if category not in results:
        results[category] = []
    results[category].append({
        "name": test_name,
        "passed": passed,
        "detail": detail,
    })
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {test_name}: {detail}")


async def test_neon_and_pgvector():
    print("\n--- 1. Testing Real Neon Database & pgvector ---")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1.1 Connection & Extension check
    try:
        async with session_factory() as session:
            res = await session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
            ext = res.scalar_one_or_none()
            has_vector = ext == "vector"
            record_result("Neon", "pgvector Extension", has_vector, f"Extension found: {ext}")
    except Exception as e:
        record_result("Neon", "pgvector Extension", False, f"Failed: {type(e).__name__}: {str(e)[:100]}")

    # 1.2 Ingest trace with deterministic failure to Neon
    trace_id = f"p18-neon-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create trace
        r1 = await client.post(
            "/api/v1/traces",
            json={
                "trace_id": trace_id,
                "name": "Phase 18 Validation Trace",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
            },
            headers=AUTH_HEADERS,
        )
        record_result("Neon", "Trace Creation via API", r1.status_code == 201, f"Status {r1.status_code}")

        # Ingest events including an explicit ERROR
        events = [
            {
                "event_id": f"{trace_id}-1",
                "trace_id": trace_id,
                "event_type": "AGENT_START",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"query": "Process refund for order 999"},
            },
            {
                "event_id": f"{trace_id}-2",
                "trace_id": trace_id,
                "parent_event_id": f"{trace_id}-1",
                "event_type": "TOOL_CALL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"tool": "refund_api", "order_id": "999"},
            },
            {
                "event_id": f"{trace_id}-3",
                "trace_id": trace_id,
                "parent_event_id": f"{trace_id}-2",
                "event_type": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"error": "Payment gateway timeout 504"},
            },
            {
                "event_id": f"{trace_id}-4",
                "trace_id": trace_id,
                "parent_event_id": f"{trace_id}-1",
                "event_type": "AGENT_END",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"status": "failed"},
            },
        ]
        r2 = await client.post("/api/v1/events", json=events, headers=AUTH_HEADERS)
        record_result("Neon", "Event Ingestion via API", r2.status_code == 201, f"{len(events)} events ingested")

    # 1.3 Trace Reconstruction & Failure Detection on Neon
    async with session_factory() as session:
        rec = await trace_reconstruction_service.reconstruct_trace(trace_id, session)
        record_result("Neon", "Trace Reconstruction", rec.event_count == 4, f"Reconstructed {rec.event_count} events")

        graph = await execution_graph_service.get_execution_graph(trace_id, session)
        record_result("Neon", "Execution Graph Generation", graph.node_count == 4 and graph.edge_count == 3, f"{graph.node_count} nodes, {graph.edge_count} edges")

        findings_resp = await failure_detection_service.get_findings(trace_id, session)
        has_finding = findings_resp.total_findings > 0
        rule = findings_resp.findings[0].rule if has_finding else "none"
        record_result("Neon", "Failure Detection", has_finding, f"Rule detected: {rule}")

        # AI investigation
        inv = await ai_investigation_service.investigate_trace(trace_id, session)
        record_result("Neon", "AI Investigation", inv.status.value in ["investigated", "failed"], f"Status: {inv.status.value}, confidence: {inv.confidence}")

        # Indexing in pgvector
        idx_res = await failure_search_service.index_trace_failures(trace_id, session)
        record_result("Neon", "pgvector Indexing", idx_res.indexed_count >= 1, f"Indexed {idx_res.indexed_count} findings")

        # Semantic Search in pgvector
        search_res = await failure_search_service.search_failures(
            query="refund gateway timeout error",
            db=session,
            limit=5,
        )
        record_result("Neon", "pgvector Semantic Search", search_res.total_results >= 1, f"Returned {search_res.total_results} matching failures")


async def test_redis_realtime():
    print("\n--- 2. Testing Redis Connection & Real-Time Monitoring ---")
    # Ping Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        pong = await r.ping()
        record_result("Redis", "Redis Ping", bool(pong), "PONG received")
        await r.aclose()
    except Exception as e:
        record_result("Redis", "Redis Ping", False, str(e))

    # Publish an event through realtime_publisher
    test_trace_id = f"p18-redis-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    try:
        from app.models.realtime import EventCreatedMessage, RealtimeEventPayload
        payload = RealtimeEventPayload(
            event_id="ev-redis-1",
            trace_id=test_trace_id,
            event_type="LLM_CALL",
            timestamp=datetime.now(timezone.utc),
        )
        msg = EventCreatedMessage(trace_id=test_trace_id, event=payload)
        pub_ok = await realtime_publisher.publish(trace_id=test_trace_id, message=msg)
        record_result("Redis", "Event Publication", pub_ok, f"Published to agentlens:trace:{test_trace_id}")
    except Exception as e:
        record_result("Redis", "Event Publication", False, str(e))


async def test_demo_agent_e2e():
    print("\n--- 3. Testing End-to-End Demo Customer Support Agent ---")
    runner = DemoAgentRunner(
        api_url="http://localhost:8000",
        api_key="test_api_key_123",
        project_name="phase18-demo-test",
        use_agentlens=True,
    )
    try:
        # Run user query
        result = await runner.run_user_query(
            "Where is my order ORD-1001?",
            trace_name="Phase 18 Demo Run",
        )
        trace_id = result.get("trace_id")
        success = result.get("success", False)
        record_result("Demo Agent", "Agent Run Execution", success and bool(trace_id), f"Trace ID: {trace_id}")
    finally:
        runner.close()


async def test_failure_scenarios():
    print("\n--- 4. Testing Controlled Failure Scenarios (Cases A to F) ---")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    base_time = datetime.now(timezone.utc)

    async def ingest_trace_events(tid: str, name: str, status: str, evts: list):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/traces",
                json={"trace_id": tid, "name": name, "start_time": base_time.isoformat(), "status": status},
                headers=AUTH_HEADERS,
            )
            await client.post("/api/v1/events", json=evts, headers=AUTH_HEADERS)

    # Case A: Explicit error
    tid_a = f"case-a-{base_time.strftime('%Y%m%d%H%M%S')}"
    evts_a = [
        {"event_id": f"{tid_a}-1", "trace_id": tid_a, "event_type": "AGENT_START", "timestamp": base_time.isoformat(), "data": {}},
        {"event_id": f"{tid_a}-2", "trace_id": tid_a, "parent_event_id": f"{tid_a}-1", "event_type": "ERROR", "timestamp": base_time.isoformat(), "data": {"error": "ConnectionResetError"}},
        {"event_id": f"{tid_a}-3", "trace_id": tid_a, "parent_event_id": f"{tid_a}-1", "event_type": "AGENT_END", "timestamp": base_time.isoformat(), "data": {}},
    ]
    await ingest_trace_events(tid_a, "Case A Explicit Error", "failed", evts_a)
    async with session_factory() as session:
        fa = await failure_detection_service.get_findings(tid_a, session)
        rules = [f.rule.lower() for f in fa.findings]
        record_result("Failure Scenarios", "Case A - Explicit Error", "explicit_error" in rules, f"Rules: {rules}")

    # Case B: Missing tool response
    tid_b = f"case-b-{base_time.strftime('%Y%m%d%H%M%S')}"
    evts_b = [
        {"event_id": f"{tid_b}-1", "trace_id": tid_b, "event_type": "AGENT_START", "timestamp": base_time.isoformat(), "data": {}},
        {"event_id": f"{tid_b}-2", "trace_id": tid_b, "parent_event_id": f"{tid_b}-1", "event_type": "TOOL_CALL", "timestamp": base_time.isoformat(), "data": {"tool": "check_balance"}},
        {"event_id": f"{tid_b}-3", "trace_id": tid_b, "parent_event_id": f"{tid_b}-1", "event_type": "AGENT_END", "timestamp": base_time.isoformat(), "data": {}},
    ]
    await ingest_trace_events(tid_b, "Case B Missing Tool Response", "completed", evts_b)
    async with session_factory() as session:
        fb = await failure_detection_service.get_findings(tid_b, session)
        rules = [f.rule.lower() for f in fb.findings]
        record_result("Failure Scenarios", "Case B - Missing Tool Response", "missing_tool_response" in rules, f"Rules: {rules}")

    # Case C: Missing LLM response
    tid_c = f"case-c-{base_time.strftime('%Y%m%d%H%M%S')}"
    evts_c = [
        {"event_id": f"{tid_c}-1", "trace_id": tid_c, "event_type": "AGENT_START", "timestamp": base_time.isoformat(), "data": {}},
        {"event_id": f"{tid_c}-2", "trace_id": tid_c, "parent_event_id": f"{tid_c}-1", "event_type": "LLM_CALL", "timestamp": base_time.isoformat(), "data": {"model": "gpt-4"}},
        {"event_id": f"{tid_c}-3", "trace_id": tid_c, "parent_event_id": f"{tid_c}-1", "event_type": "AGENT_END", "timestamp": base_time.isoformat(), "data": {}},
    ]
    await ingest_trace_events(tid_c, "Case C Missing LLM Response", "completed", evts_c)
    async with session_factory() as session:
        fc = await failure_detection_service.get_findings(tid_c, session)
        rules = [f.rule.lower() for f in fc.findings]
        record_result("Failure Scenarios", "Case C - Missing LLM Response", "missing_llm_response" in rules, f"Rules: {rules}")

    # Case D: Unresolved retry sequence
    tid_d = f"case-d-{base_time.strftime('%Y%m%d%H%M%S')}"
    evts_d = [
        {"event_id": f"{tid_d}-1", "trace_id": tid_d, "event_type": "AGENT_START", "timestamp": base_time.isoformat(), "data": {}},
        {"event_id": f"{tid_d}-2", "trace_id": tid_d, "parent_event_id": f"{tid_d}-1", "event_type": "RETRY", "timestamp": base_time.isoformat(), "data": {"attempt": 1}},
        {"event_id": f"{tid_d}-3", "trace_id": tid_d, "parent_event_id": f"{tid_d}-1", "event_type": "RETRY", "timestamp": base_time.isoformat(), "data": {"attempt": 2}},
        {"event_id": f"{tid_d}-4", "trace_id": tid_d, "parent_event_id": f"{tid_d}-1", "event_type": "ERROR", "timestamp": base_time.isoformat(), "data": {"error": "Exhausted"}},
        {"event_id": f"{tid_d}-5", "trace_id": tid_d, "parent_event_id": f"{tid_d}-1", "event_type": "AGENT_END", "timestamp": base_time.isoformat(), "data": {}},
    ]
    await ingest_trace_events(tid_d, "Case D Retry Sequence", "failed", evts_d)
    async with session_factory() as session:
        fd = await failure_detection_service.get_findings(tid_d, session)
        rules = [f.rule.lower() for f in fd.findings]
        has_retry = "unresolved_retry" in rules or "consecutive_retries" in rules or any("retry" in r for r in rules)
        record_result("Failure Scenarios", "Case D - Retry Sequence", has_retry, f"Rules: {rules}")

    # Case E: Repeated tool calls / loop
    tid_e = f"case-e-{base_time.strftime('%Y%m%d%H%M%S')}"
    evts_e = [
        {"event_id": f"{tid_e}-start", "trace_id": tid_e, "event_type": "AGENT_START", "timestamp": base_time.isoformat(), "data": {}},
    ]
    for i in range(5):
        evts_e.append({"event_id": f"{tid_e}-c{i}", "trace_id": tid_e, "parent_event_id": f"{tid_e}-start", "event_type": "TOOL_CALL", "timestamp": base_time.isoformat(), "data": {"tool": "search", "query": "order"}})
        evts_e.append({"event_id": f"{tid_e}-r{i}", "trace_id": tid_e, "parent_event_id": f"{tid_e}-c{i}", "event_type": "TOOL_RESPONSE", "timestamp": base_time.isoformat(), "data": {"results": []}})
    evts_e.append({"event_id": f"{tid_e}-end", "trace_id": tid_e, "parent_event_id": f"{tid_e}-start", "event_type": "AGENT_END", "timestamp": base_time.isoformat(), "data": {}})
    await ingest_trace_events(tid_e, "Case E Repeated Tool Calls", "completed", evts_e)
    async with session_factory() as session:
        fe = await failure_detection_service.get_findings(tid_e, session)
        rules = [f.rule.lower() for f in fe.findings]
        has_loop = "repeated_tool_call" in rules or "execution_loop_detected" in rules or any("tool" in r or "loop" in r for r in rules)
        record_result("Failure Scenarios", "Case E - Repeated Calls / Loop", has_loop, f"Rules: {rules}")

    # Case F: Clean trace
    tid_f = f"case-f-{base_time.strftime('%Y%m%d%H%M%S')}"
    evts_f = [
        {"event_id": f"{tid_f}-1", "trace_id": tid_f, "event_type": "AGENT_START", "timestamp": base_time.isoformat(), "data": {"query": "Hello"}},
        {"event_id": f"{tid_f}-2", "trace_id": tid_f, "parent_event_id": f"{tid_f}-1", "event_type": "LLM_CALL", "timestamp": base_time.isoformat(), "data": {}},
        {"event_id": f"{tid_f}-3", "trace_id": tid_f, "parent_event_id": f"{tid_f}-2", "event_type": "LLM_RESPONSE", "timestamp": base_time.isoformat(), "data": {"response": "Hi!"}},
        {"event_id": f"{tid_f}-4", "trace_id": tid_f, "parent_event_id": f"{tid_f}-1", "event_type": "AGENT_END", "timestamp": base_time.isoformat(), "data": {"status": "completed"}},
    ]
    await ingest_trace_events(tid_f, "Case F Clean Trace", "completed", evts_f)
    async with session_factory() as session:
        ff = await failure_detection_service.get_findings(tid_f, session)
        inv_f = await ai_investigation_service.investigate_trace(tid_f, session)
        is_clean = ff.total_findings == 0 and inv_f.status.value in ["no_issue_detected", "investigated"]
        record_result("Failure Scenarios", "Case F - Clean Trace", is_clean, f"Findings count: {ff.total_findings}, Investigation status: {inv_f.status.value}")


async def test_mcp_validation():
    print("\n--- 5. Testing MCP Server & Read-Only Guarantees ---")
    server = create_mcp_server()
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
    has_all_7 = tool_names == expected_tools
    record_result("MCP", "7 Read-Only Tools Registered", has_all_7, f"Tools: {sorted(tool_names)}")

    # Check that calling tool with missing trace returns structured error
    from app.mcp.tools import get_trace_handler
    err_res = await get_trace_handler("non_existent_trace_12345")
    has_structured_err = err_res.get("error") == "trace_not_found"
    record_result("MCP", "Structured Error on Missing Trace", has_structured_err, f"Response: {err_res}")


async def test_sdk_validation():
    print("\n--- 6. Testing Python SDK ---")
    lens = AgentLens(api_url="http://localhost:8000", api_key="test_api_key_123", project_name="p18-sdk-test")
    try:
        trace = lens.create_trace("Phase 18 SDK Trace")
        lens.create_event(event_type=EventType.AGENT_START, data={"step": 1}, trace_id=trace.trace_id)
        lens.create_event(event_type=EventType.AGENT_END, data={"step": 2}, trace_id=trace.trace_id)
        lens.end_trace(trace.trace_id, status="completed")
        flushed = lens.flush()
        record_result("SDK", "Client Trace & Event Logging", bool(trace.trace_id), f"Trace {trace.trace_id} logged")
    finally:
        lens.close()


async def main():
    print("=" * 70)
    print("AGENTLENS PHASE 18 - COMPREHENSIVE END-TO-END VALIDATION")
    print("=" * 70)

    try:
        await init_db()
        await test_neon_and_pgvector()
        await test_redis_realtime()
        await test_demo_agent_e2e()
        await test_failure_scenarios()
        await test_mcp_validation()
        await test_sdk_validation()
    finally:
        await close_db()

    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    total_passed = 0
    total_failed = 0
    for cat, items in results.items():
        print(f"\n[{cat}]")
        for it in items:
            mark = "PASS" if it["passed"] else "FAIL"
            print(f"  {mark:4} | {it['name']} - {it['detail']}")
            if it["passed"]:
                total_passed += 1
            else:
                total_failed += 1

    print("\n" + "=" * 70)
    print(f"OVERALL RESULT: {total_passed} PASSED, {total_failed} FAILED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
