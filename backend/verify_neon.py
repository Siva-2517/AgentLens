#!/usr/bin/env python
"""Phase 6 — Real Neon PostgreSQL verification script.

Attempts to:
  1. Connect to Neon using DATABASE_URL from .env
  2. Initialize database tables
  3. Write a demo trace and events via the FastAPI layer (test client)
  4. Read them back from the database directly
  5. Report pass/fail clearly

Run from the backend/ directory:
    python verify_neon.py

Do NOT print DATABASE_URL or credentials.
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.WARNING)  # suppress noisy SQLAlchemy echo

PASS = "[OK]"
FAIL = "[FAIL]"
SKIP = "[WARN]"


async def run_verification() -> bool:
    """Run all Phase 6 Neon verification steps. Returns True on success."""
    print("\n" + "=" * 60)
    print("PHASE 6 — REAL NEON VERIFICATION")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Import settings and check URL
    # ------------------------------------------------------------------
    try:
        from app.config import settings
        db_url = settings.database_url
        is_placeholder = (
            "user:password" in db_url
            or "ep-example" in db_url
            or not db_url.startswith("postgresql")
        )
        if is_placeholder:
            print(f"\n{SKIP} DATABASE_URL is a placeholder — no real Neon configured.")
            print("\nREAL NEON TEST:\nNOT VERIFIED — placeholder DATABASE_URL in .env")
            return False
        print(f"{PASS} DATABASE_URL is configured (endpoint hidden for security)")
    except Exception as e:
        print(f"{FAIL} Could not load settings: {e}")
        return False

    # ------------------------------------------------------------------
    # Step 2: Initialize DB (create tables if needed)
    # ------------------------------------------------------------------
    from app.db.session import engine, Base, init_db, close_db
    from app.db.models import TraceModel, EventModel  # ensure models are imported

    print("\nStep 1 — Connecting to Neon and initialising tables...")
    try:
        await asyncio.wait_for(init_db(), timeout=15.0)
        print(f"{PASS} Connected to Neon; tables exist / created")
    except asyncio.TimeoutError:
        print(f"{FAIL} Connection timed out (15 s)")
        print("\nREAL NEON TEST:\nNOT VERIFIED — connection/network timeout")
        return False
    except Exception as e:
        err_str = str(e)
        if "getaddrinfo" in err_str or "Name or service" in err_str:
            print(f"{FAIL} DNS resolution failed — network or Neon endpoint unavailable")
        else:
            print(f"{FAIL} Connection error: {type(e).__name__}: {err_str[:120]}")
        print("\nREAL NEON TEST:\nNOT VERIFIED — connection/network timeout")
        await close_db()
        return False

    # ------------------------------------------------------------------
    # Step 3: Write a trace via FastAPI test client
    # ------------------------------------------------------------------
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.db import get_db
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    TRACE_ID = f"neon-verify-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    HEADERS = {
        "Authorization": "Bearer test_api_key_123",
        "X-AgentLens-Project": "neon-verify",
    }

    print(f"\nStep 2 — Writing trace {TRACE_ID} via FastAPI...")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Create trace
        r = await ac.post(
            "/api/v1/traces",
            json={
                "trace_id": TRACE_ID,
                "name": "neon-phase6-verify",
                "start_time": datetime.utcnow().isoformat(),
                "status": "running",
                "metadata": {"verification": "phase6"},
            },
            headers=HEADERS,
        )
        if r.status_code != 201:
            print(f"{FAIL} Trace creation failed: {r.status_code} {r.text}")
            await close_db()
            return False
        print(f"{PASS} Trace created via API (status {r.status_code})")

        # Write events
        events = [
            (f"{TRACE_ID}-evt-001", "AGENT_START", None, {"query": "Neon verification test"}),
            (f"{TRACE_ID}-evt-002", "LLM_CALL", f"{TRACE_ID}-evt-001", {"model": "test"}),
            (f"{TRACE_ID}-evt-003", "LLM_RESPONSE", f"{TRACE_ID}-evt-002", {"selected_tool": "get_order"}),
            (f"{TRACE_ID}-evt-004", "TOOL_CALL", f"{TRACE_ID}-evt-001", {"tool": "get_order", "args": {"order_id": "ORD-1001"}}),
            (f"{TRACE_ID}-evt-005", "TOOL_RESPONSE", f"{TRACE_ID}-evt-004", {"order": "ORD-1001", "status": "shipped"}),
            (f"{TRACE_ID}-evt-006", "STATE_CHANGE", f"{TRACE_ID}-evt-001", {"thought": "Generating response"}),
            (f"{TRACE_ID}-evt-007", "AGENT_END", None, {"status": "completed"}),
        ]
        payload = [
            {
                "event_id": eid,
                "trace_id": TRACE_ID,
                "parent_event_id": pid,
                "event_type": etype,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
                "metadata": {"phase": "7"},
            }
            for eid, etype, pid, data in events
        ]

        r = await ac.post("/api/v1/events", json=payload, headers=HEADERS)
        if r.status_code != 201:
            print(f"{FAIL} Events ingestion failed: {r.status_code} {r.text}")
            await close_db()
            return False
        print(f"{PASS} {len(events)} events ingested via API (status {r.status_code})")

    # ------------------------------------------------------------------
    # Step 4: Read back from Neon directly
    # ------------------------------------------------------------------
    print("\nStep 3 — Reading trace/events back from Neon directly...")
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            # Read trace
            result = await session.execute(
                select(TraceModel).where(TraceModel.trace_id == TRACE_ID)
            )
            db_trace = result.scalar_one_or_none()
            if db_trace is None:
                print(f"{FAIL} Trace NOT found in Neon database")
                await close_db()
                return False
            print(f"{PASS} Trace found in Neon: {db_trace.trace_id!r} (status={db_trace.status!r})")

            # Read events
            result = await session.execute(
                select(EventModel)
                .where(EventModel.trace_id == TRACE_ID)
                .order_by(EventModel.timestamp)
            )
            db_events = result.scalars().all()
            found_types = {e.event_type for e in db_events}
            print(f"{PASS} {len(db_events)} events found in Neon")
            print(f"     Event types: {sorted(found_types)}")

            required = {"AGENT_START", "LLM_CALL", "LLM_RESPONSE", "TOOL_CALL",
                        "TOOL_RESPONSE", "STATE_CHANGE", "AGENT_END"}
            missing = required - found_types
            if missing:
                print(f"{FAIL} Missing event types: {missing}")
                await close_db()
                return False

            print(f"{PASS} All required event types present")
            all_same_trace = all(e.trace_id == TRACE_ID for e in db_events)
            print(f"{PASS} All events share trace_id={TRACE_ID!r}: {all_same_trace}")

    except Exception as e:
        print(f"{FAIL} DB read error: {e}")
        await close_db()
        return False

    # ------------------------------------------------------------------
    # Step 5: Verify Trace Reconstruction Engine on Neon
    # ------------------------------------------------------------------
    print("\nStep 4 -- Verifying Trace Reconstruction Engine on Neon...")
    from app.services.trace_reconstruction_service import trace_reconstruction_service

    try:
        async with session_factory() as session:
            rec = await trace_reconstruction_service.reconstruct_trace(TRACE_ID, session)
            print(f"{PASS} TraceReconstructionService reconstructed trace from Neon")
            print(f"     Events count: {rec.event_count}")
            print(f"     LLM calls: {rec.metadata.llm_call_count}, Tool calls: {rec.metadata.tool_call_count}")
            print(f"     Has AGENT_START: {rec.metadata.has_agent_start}, Has AGENT_END: {rec.metadata.has_agent_end}")
            print(f"     Root events count: {len(rec.root_event_ids)}")
            if rec.event_count != len(events):
                print(f"{FAIL} Expected {len(events)} events, got {rec.event_count}")
                await close_db()
                return False

        # Also verify GET /api/v1/traces/{trace_id} via ASGI client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/traces/{TRACE_ID}", headers=HEADERS)
            if r.status_code != 200:
                print(f"{FAIL} GET /api/v1/traces/{TRACE_ID} failed: {r.status_code} {r.text}")
                await close_db()
                return False
            data = r.json()
            print(f"{PASS} API GET /api/v1/traces/{TRACE_ID} returned status 200")
            print(f"     Reconstructed trace name: {data['name']!r}, events: {len(data['events'])}")

    except Exception as e:
        print(f"{FAIL} Reconstruction error: {e}")
        await close_db()
        return False

    # ------------------------------------------------------------------
    # Step 6: Verify Phase 8 Execution Graph on Neon
    # ------------------------------------------------------------------
    print("\nStep 5 -- Verifying Phase 8 Execution Graph on Neon...")
    from app.services.execution_graph_service import execution_graph_service

    try:
        async with session_factory() as session:
            graph = await execution_graph_service.get_execution_graph(TRACE_ID, session)
            print(f"{PASS} ExecutionGraphService generated graph from Neon")
            print(f"     Nodes count: {graph.node_count}, Edges count: {graph.edge_count}")
            if graph.node_count != len(events):
                print(f"{FAIL} Expected {len(events)} nodes, got {graph.node_count}")
                await close_db()
                return False

        # Verify GET /api/v1/traces/{trace_id}/graph via ASGI client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/traces/{TRACE_ID}/graph", headers=HEADERS)
            if r.status_code != 200:
                print(f"{FAIL} GET /api/v1/traces/{TRACE_ID}/graph failed: {r.status_code} {r.text}")
                await close_db()
                return False
            gdata = r.json()
            print(f"{PASS} API GET /api/v1/traces/{TRACE_ID}/graph returned status 200")
            print(f"     Graph nodes: {gdata['node_count']}, edges: {gdata['edge_count']}")

    except Exception as e:
        print(f"{FAIL} Graph generation error: {e}")
        await close_db()
        return False

    await close_db()

    print("\n" + "=" * 60)
    print("REAL NEON TEST:\nVERIFIED -- trace, events, reconstruction & execution graph on Neon")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)
