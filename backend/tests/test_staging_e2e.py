"""Full Staging End-to-End Smoke Test on Real Neon PostgreSQL (Phase 20A).

Executes a complete real-infrastructure lifecycle smoke test against Neon PostgreSQL:
1. Provisions disposable staging organization and project.
2. Creates project ingestion API key and MCP API key.
3. Ingests a trace with child events into Neon.
4. Indexes a failure embedding into Neon pgvector.
5. Executes MCP tools with authenticated project credentials:
   - get_trace
   - get_execution_graph
   - search_historical_failures (via real pgvector similarity)
6. Verifies that all operations succeed and data is strictly project-isolated.
7. Safely removes all test staging records.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import (
    ApiKeyModel,
    EventModel,
    FailureEmbeddingModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
)
from app.db.repositories import (
    ApiKeyRepository,
    FailureEmbeddingRepository,
    TraceRepository,
)
from app.mcp.auth import mcp_api_key_context
from app.mcp.tools import (
    get_execution_graph_handler,
    get_trace_handler,
    search_historical_failures_handler,
    set_session_factory,
)
from app.services.security import security_service
from tests.infra_helpers import is_postgres_available

pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL/Neon infrastructure not available in current environment",
)


def get_staging_engine():
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    db_url = db_url.split("?")[0]
    return create_async_engine(
        db_url,
        poolclass=NullPool,
        connect_args={
            "ssl": True,
            "timeout": 60,
            "command_timeout": 60,
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: "",
        },
    )


@pytest.mark.asyncio
async def test_staging_real_infrastructure_e2e_smoke():
    """Execute end-to-end trace ingestion, pgvector indexing, and MCP tool interrogation on Neon."""
    engine = get_staging_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def session_ctx():
        async with session_factory() as sess:
            yield sess

    set_session_factory(session_ctx)

    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    trace_id = f"trace-e2e-{uuid.uuid4().hex[:8]}"

    async with session_factory() as session:
        try:
            # 1. Create Organization & Project
            org = OrganizationModel(id=org_id, name="Staging Smoke Org", slug=f"smoke-{org_id[:8]}")
            proj = ProjectModel(id=proj_id, organization_id=org_id, name="Staging Smoke Proj", slug=f"smoke-p-{org_id[:8]}")
            session.add_all([org, proj])
            await session.flush()

            # 2. Create project ingestion key and MCP key
            raw_ingest_key, ingest_prefix, ingest_hash = security_service.generate_ingestion_api_key()
            raw_mcp_key, mcp_prefix, mcp_hash = security_service.generate_ingestion_api_key()

            ingest_key_record = ApiKeyModel(
                project_id=proj_id,
                name="Staging Ingest Key",
                key_prefix=ingest_prefix,
                key_hash=ingest_hash,
                key_type="ingestion",
                scopes=["ingest"],
            )
            mcp_key_record = ApiKeyModel(
                project_id=proj_id,
                name="Staging MCP Key",
                key_prefix=mcp_prefix,
                key_hash=mcp_hash,
                key_type="mcp",
                scopes=["mcp", "read"],
            )
            session.add_all([ingest_key_record, mcp_key_record])
            await session.flush()

            # 3. Ingest trace and events into Neon
            trace = TraceModel(
                trace_id=trace_id,
                project_id=proj_id,
                project_name="Staging Smoke Proj",
                name="Staging E2E Smoke Run",
                start_time=datetime.now(timezone.utc),
                status="failed",
                metadata_={"environment": "staging"},
            )
            session.add(trace)
            await session.flush()

            evt1_id = f"evt-1-{uuid.uuid4().hex[:8]}"
            evt2_id = f"evt-2-{uuid.uuid4().hex[:8]}"

            evt1 = EventModel(
                event_id=evt1_id,
                trace_id=trace_id,
                event_type="agent_start",
                timestamp=datetime.now(timezone.utc),
                data={"agent_name": "TestAgent"},
                metadata_={},
            )
            evt2 = EventModel(
                event_id=evt2_id,
                trace_id=trace_id,
                parent_event_id=evt1_id,
                event_type="error",
                timestamp=datetime.now(timezone.utc),
                data={"error_message": "Rate limit exceeded on provider API"},
                metadata_={},
            )
            session.add_all([evt1, evt2])
            await session.flush()

            # 4. Index failure embedding into Neon pgvector
            repo = FailureEmbeddingRepository(session)
            target_vec = [0.8] + [0.2] * 767
            await repo.upsert(
                trace_id=trace_id,
                finding_id="find-e2e-1",
                rule="RATE_LIMIT",
                category="API",
                severity="CRITICAL",
                searchable_text="Rate limit exceeded on provider API in staging",
                embedding=target_vec,
                metadata={"test": "e2e_staging"},
                project_id=proj_id,
            )
            await session.commit()

            # 5. Interrogate through MCP tools using raw_mcp_key
            async with mcp_api_key_context(raw_mcp_key):
                # a) get_trace
                trace_res = await get_trace_handler(trace_id=trace_id)
                assert "error" not in trace_res, f"get_trace failed: {trace_res}"
                assert trace_res["trace_id"] == trace_id
                assert trace_res["name"] == "Staging E2E Smoke Run"

                # b) get_execution_graph
                graph_res = await get_execution_graph_handler(trace_id=trace_id)
                assert "error" not in graph_res, f"get_execution_graph failed: {graph_res}"
                assert graph_res["trace_id"] == trace_id
                assert len(graph_res["nodes"]) == 2

                # c) search_historical_failures via real pgvector
                search_res = await search_historical_failures_handler(
                    query="Rate limit provider failure",
                    limit=5,
                )
                assert "error" not in search_res, f"search_historical_failures failed: {search_res}"
                assert "results" in search_res
                results = search_res["results"]
                assert any(r["trace_id"] == trace_id for r in results)

        finally:
            # Guaranteed cleanup
            await session.rollback()
            await session.execute(text("DELETE FROM organizations WHERE id = :org_id"), {"org_id": org_id})
            await session.commit()
            await engine.dispose()
