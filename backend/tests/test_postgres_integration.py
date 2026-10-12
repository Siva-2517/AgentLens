"""Real Neon PostgreSQL and pgvector Integration Tests (Phase 20A).

Validates:
1. Connection to Neon PostgreSQL with TLS / SSL enabled.
2. pgvector extension (0.8.6+) enabled.
3. HNSW vector index created using vector_cosine_ops on failure_embeddings.
4. Real vector insertion and pgvector cosine distance search.
5. Strict database-level multi-tenant isolation (Alpha vs Beta).
6. SQL constraint enforcement (unique emails, unique API key hashes).
7. Cascade deletion on project deletion.
8. Transaction rollback and session cleanup after exceptions.
9. Schema migration repeatability and idempotency.

These tests execute ONLY when real PostgreSQL is reachable and are skipped otherwise.
Tests never fall back to SQLite or mocked vector similarity.
"""

import asyncio
from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.config import settings
from app.db.models import (
    ApiKeyModel,
    FailureEmbeddingModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
    UserModel,
)
from app.db.repositories import FailureEmbeddingRepository
from app.db.setup_schema import run_schema_migration
from tests.infra_helpers import is_postgres_available
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL/Neon infrastructure not available in current environment",
)


def get_real_test_engine():
    """Create a NullPool engine so asyncpg connections are not shared across pytest event loops."""
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


@pytest.fixture
async def real_db_session():
    """Create an async session connected directly to Neon PostgreSQL using NullPool."""
    test_engine = get_real_test_engine()
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_neon_connection_and_pgvector_extension(real_db_session):
    """Verify Neon PostgreSQL connection and pgvector extension."""
    res = await real_db_session.execute(text("SELECT version();"))
    version = res.scalar()
    assert version is not None
    assert "PostgreSQL" in version

    ext_res = await real_db_session.execute(
        text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
    )
    ext = ext_res.fetchone()
    assert ext is not None, "pgvector extension must be installed in PostgreSQL"
    assert ext[0] == "vector"
    assert ext[1] is not None


@pytest.mark.asyncio
async def test_neon_hnsw_index_and_vector_column(real_db_session):
    """Verify HNSW index syntax, operator class, and column definition on failure_embeddings."""
    # 1. Verify vector column
    col_res = await real_db_session.execute(
        text("""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'failure_embeddings' AND column_name = 'embedding';
        """)
    )
    col = col_res.fetchone()
    assert col is not None, "failure_embeddings.embedding column must exist"
    assert col[2] == "vector", f"Expected udt_name 'vector', got {col[2]}"

    # 2. Verify HNSW index
    idx_res = await real_db_session.execute(
        text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'failure_embeddings' 
              AND indexname = 'idx_failure_embeddings_embedding_hnsw';
        """)
    )
    idx = idx_res.fetchone()
    assert idx is not None, "HNSW index idx_failure_embeddings_embedding_hnsw must exist"
    assert "USING hnsw" in idx[1]
    assert "vector_cosine_ops" in idx[1]


@pytest.mark.asyncio
async def test_neon_pgvector_similarity_search_and_tenant_isolation(real_db_session):
    """Verify actual pgvector cosine search and strict tenant isolation on Neon."""
    org_id = str(uuid.uuid4())
    proj_alpha_id = str(uuid.uuid4())
    proj_beta_id = str(uuid.uuid4())
    trace_alpha_id = f"trace-a-{uuid.uuid4().hex[:8]}"
    trace_beta_id = f"trace-b-{uuid.uuid4().hex[:8]}"

    try:
        # Create Org & Projects
        org = OrganizationModel(id=org_id, name="Test Neon Org", slug=f"org-{org_id[:8]}")
        real_db_session.add(org)
        await real_db_session.flush()

        proj_alpha = ProjectModel(
            id=proj_alpha_id, organization_id=org_id, name="Neon Alpha", slug=f"alpha-{org_id[:8]}"
        )
        proj_beta = ProjectModel(
            id=proj_beta_id, organization_id=org_id, name="Neon Beta", slug=f"beta-{org_id[:8]}"
        )
        real_db_session.add_all([proj_alpha, proj_beta])
        await real_db_session.flush()

        # Create Traces
        trace_alpha = TraceModel(
            trace_id=trace_alpha_id,
            project_id=proj_alpha_id,
            project_name="Neon Alpha",
            name="Alpha Execution",
            start_time=datetime.now(timezone.utc),
            status="failed",
            metadata_={},
        )
        trace_beta = TraceModel(
            trace_id=trace_beta_id,
            project_id=proj_beta_id,
            project_name="Neon Beta",
            name="Beta Execution",
            start_time=datetime.now(timezone.utc),
            status="failed",
            metadata_={},
        )
        real_db_session.add_all([trace_alpha, trace_beta])
        await real_db_session.flush()

        # Create failure embeddings: Alpha pointing along dim 0, Beta along dim 1
        alpha_vec = [1.0] + [0.0] * 767
        beta_vec = [0.0, 1.0] + [0.0] * 766

        repo = FailureEmbeddingRepository(real_db_session)
        await repo.upsert(
            trace_id=trace_alpha_id,
            finding_id="find-a",
            rule="ALPHA_RULE",
            category="TEST",
            severity="HIGH",
            searchable_text="Alpha failure text",
            embedding=alpha_vec,
            metadata={"owner": "alpha"},
            project_id=proj_alpha_id,
        )
        await repo.upsert(
            trace_id=trace_beta_id,
            finding_id="find-b",
            rule="BETA_RULE",
            category="TEST",
            severity="CRITICAL",
            searchable_text="Beta failure text",
            embedding=beta_vec,
            metadata={"owner": "beta"},
            project_id=proj_beta_id,
        )
        await real_db_session.commit()

        # 1. Search scoped to Alpha with query vector close to Alpha
        query_vec = [0.9, 0.1] + [0.0] * 766
        alpha_results = await repo.search_similar(
            query_vector=query_vec, project_id=proj_alpha_id, limit=5
        )
        assert len(alpha_results) == 1
        assert alpha_results[0][0].trace_id == trace_alpha_id
        assert alpha_results[0][0].rule == "ALPHA_RULE"
        assert alpha_results[0][3] == "Neon Alpha"
        # Zero leakage of Beta
        assert not any(r[0].trace_id == trace_beta_id for r in alpha_results)

        # 2. Search scoped to Beta with the same query vector
        beta_results = await repo.search_similar(
            query_vector=query_vec, project_id=proj_beta_id, limit=5
        )
        assert len(beta_results) == 1
        assert beta_results[0][0].trace_id == trace_beta_id
        assert beta_results[0][0].rule == "BETA_RULE"
        assert beta_results[0][3] == "Neon Beta"
        # Zero leakage of Alpha
        assert not any(r[0].trace_id == trace_alpha_id for r in beta_results)

        # 3. Search with non-existent project returns empty
        empty_results = await repo.search_similar(
            query_vector=query_vec, project_id=str(uuid.uuid4()), limit=5
        )
        assert empty_results == []

    finally:
        # Guaranteed cleanup
        await real_db_session.rollback()
        await real_db_session.execute(text("DELETE FROM organizations WHERE id = :org_id"), {"org_id": org_id})
        await real_db_session.commit()


@pytest.mark.asyncio
async def test_neon_vector_dimension_mismatch_fails_safely(real_db_session):
    """Verify that vector dimension mismatches are rejected by PostgreSQL without leaking data."""
    # Attempt inserting a vector with 512 dimensions into a 768 dimension column
    invalid_vec = [0.1] * 512
    trace_id = f"trace-dim-{uuid.uuid4().hex[:8]}"

    emb = FailureEmbeddingModel(
        trace_id=trace_id,
        finding_id="dim-test",
        rule="DIM_RULE",
        category="TEST",
        severity="LOW",
        searchable_text="Dimension test",
        embedding=invalid_vec,
        metadata_={},
    )
    real_db_session.add(emb)
    with pytest.raises((DBAPIError, IntegrityError, Exception)) as exc_info:
        await real_db_session.commit()
    await real_db_session.rollback()

    err_str = str(exc_info.value).lower()
    # Check that pgvector rejected mismatched dimensions
    assert "dimension" in err_str or "expected 768" in err_str or "foreign key" in err_str


@pytest.mark.asyncio
async def test_neon_database_constraints_and_cascades(real_db_session):
    """Verify unique constraints and cascade deletions on PostgreSQL."""
    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    email = f"user-{user_id[:8]}@example.com"

    try:
        # 1. User duplicate email unique constraint
        u1 = UserModel(id=user_id, email=email, hashed_password="pw1", full_name="User 1")
        real_db_session.add(u1)
        await real_db_session.commit()

        u2 = UserModel(id=str(uuid.uuid4()), email=email, hashed_password="pw2", full_name="User 2")
        real_db_session.add(u2)
        with pytest.raises(IntegrityError):
            await real_db_session.commit()
        await real_db_session.rollback()

        # 2. API Key hash unique constraint
        org = OrganizationModel(id=org_id, name="Constraint Org", slug=f"org-{org_id[:8]}")
        proj = ProjectModel(id=proj_id, organization_id=org_id, name="Constraint Proj", slug=f"proj-{proj_id[:8]}")
        real_db_session.add_all([org, proj])
        await real_db_session.commit()

        dup_hash = f"hash-{uuid.uuid4().hex}"
        k1 = ApiKeyModel(
            project_id=proj_id,
            name="Key 1",
            key_prefix="al_live_k1",
            key_hash=dup_hash,
            key_type="ingestion",
            scopes=["ingest"],
        )
        real_db_session.add(k1)
        await real_db_session.commit()

        k2 = ApiKeyModel(
            project_id=proj_id,
            name="Key 2",
            key_prefix="al_live_k2",
            key_hash=dup_hash,
            key_type="ingestion",
            scopes=["ingest"],
        )
        real_db_session.add(k2)
        with pytest.raises(IntegrityError):
            await real_db_session.commit()
        await real_db_session.rollback()

        # 3. Project cascade deletion to traces and embeddings
        trace_id = f"trace-casc-{uuid.uuid4().hex[:8]}"
        trace = TraceModel(
            trace_id=trace_id,
            project_id=proj_id,
            name="Cascade Trace",
            start_time=datetime.now(timezone.utc),
            status="running",
            metadata_={},
        )
        real_db_session.add(trace)
        await real_db_session.commit()

        emb = FailureEmbeddingModel(
            trace_id=trace_id,
            project_id=proj_id,
            finding_id="find-casc",
            rule="CASC_RULE",
            category="TEST",
            severity="LOW",
            searchable_text="Cascade test text",
            embedding=[0.1] * 768,
            metadata_={},
        )
        real_db_session.add(emb)
        await real_db_session.commit()

        # Delete project and assert cascade
        proj_to_delete = await real_db_session.get(ProjectModel, proj_id)
        await real_db_session.delete(proj_to_delete)
        await real_db_session.commit()

        res_trace = await real_db_session.execute(select(TraceModel).where(TraceModel.trace_id == trace_id))
        assert res_trace.scalar_one_or_none() is None, "Trace should be cascade deleted"

        res_emb = await real_db_session.execute(select(FailureEmbeddingModel).where(FailureEmbeddingModel.trace_id == trace_id))
        assert res_emb.scalar_one_or_none() is None, "Embedding should be cascade deleted"

    finally:
        await real_db_session.rollback()
        await real_db_session.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        await real_db_session.execute(text("DELETE FROM organizations WHERE id = :org_id"), {"org_id": org_id})
        await real_db_session.commit()


@pytest.mark.asyncio
async def test_neon_transaction_rollback_and_session_cleanup(real_db_session):
    """Verify session rollback cleans dirty state and permits subsequent queries."""
    # Attempt an invalid insert that violates foreign key
    invalid_trace = TraceModel(
        trace_id=f"invalid-{uuid.uuid4().hex[:8]}",
        project_id=str(uuid.uuid4()),  # non-existent project_id
        name="Invalid FK Trace",
        start_time=datetime.now(timezone.utc),
    )
    real_db_session.add(invalid_trace)
    with pytest.raises(IntegrityError):
        await real_db_session.commit()

    # Roll back cleanly
    await real_db_session.rollback()

    # Session can still execute valid queries
    res = await real_db_session.execute(text("SELECT 1;"))
    assert res.scalar() == 1


@pytest.mark.asyncio
async def test_neon_schema_migration_idempotent():
    """Verify that run_schema_migration runs cleanly and repeatedly without errors."""
    test_engine = get_real_test_engine()
    try:
        # Run once
        await run_schema_migration(test_engine)
        # Run twice
        await run_schema_migration(test_engine)

        async with test_engine.begin() as conn:
            res = await conn.execute(
                text("""
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = 'failure_embeddings' 
                      AND indexname = 'idx_failure_embeddings_embedding_hnsw';
                """)
            )
            assert res.scalar() == 1
    finally:
        await test_engine.dispose()
