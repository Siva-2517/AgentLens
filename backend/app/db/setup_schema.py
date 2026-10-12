"""Database schema setup and migration utility (Phase 19 Multi-Tenant).

Provides an idempotent, repeatable migration strategy for both:
1. Neon Cloud PostgreSQL (production/development)
2. In-memory / local SQLite (automated test suite)
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


async def run_schema_migration(target_engine: AsyncEngine = engine) -> None:
    """Run idempotent schema setup and migration."""
    dialect_name = target_engine.dialect.name
    logger.info(f"Running database schema setup on dialect: {dialect_name}")

    if dialect_name == "postgresql":
        # 1. Enable vector extension
        async with target_engine.begin() as conn:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("pgvector extension verified")
            except Exception as e:
                logger.warning(f"pgvector extension check note: {e}")

        # 2. Ensure all tables are created from metadata
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Base metadata create_all executed")

        # 3. Add project_id column to failure_embeddings if missing
        async with target_engine.begin() as conn:
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'failure_embeddings' AND column_name = 'project_id'
                    ) THEN
                        ALTER TABLE failure_embeddings
                        ADD COLUMN project_id UUID REFERENCES projects(id) ON DELETE CASCADE;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'is_superuser'
                    ) THEN
                        ALTER TABLE users
                        ADD COLUMN is_superuser BOOLEAN NOT NULL DEFAULT FALSE;
                    END IF;
                END
                $$;
            """))

        # 4. Clean legacy disposable mock traces/events with NULL project_id (individual statements)
        async with target_engine.begin() as conn:
            await conn.execute(text("DELETE FROM events WHERE trace_id IN (SELECT trace_id FROM traces WHERE project_id IS NULL)"))
            await conn.execute(text("DELETE FROM failure_embeddings WHERE trace_id IN (SELECT trace_id FROM traces WHERE project_id IS NULL) OR project_id IS NULL"))
            await conn.execute(text("DELETE FROM traces WHERE project_id IS NULL"))
            logger.info("Cleaned disposable mock traces with NULL project_id")

        # 5. Enforce NOT NULL and foreign key constraint on traces.project_id
        async with target_engine.begin() as conn:
            await conn.execute(text("""
                DO $$
                BEGIN
                    -- Set NOT NULL
                    ALTER TABLE traces ALTER COLUMN project_id SET NOT NULL;

                    -- Ensure foreign key constraint
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE constraint_name = 'traces_project_id_fkey' AND table_name = 'traces'
                    ) THEN
                        ALTER TABLE traces
                        ADD CONSTRAINT traces_project_id_fkey
                        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
                    END IF;
                END
                $$;
            """))
            logger.info("Neon PostgreSQL schema constraints verified: traces.project_id is NOT NULL with FK to projects(id)")

        # 6. Ensure HNSW index on failure_embeddings.embedding using vector_cosine_ops
        async with target_engine.begin() as conn:
            try:
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_failure_embeddings_embedding_hnsw
                    ON failure_embeddings
                    USING hnsw (embedding vector_cosine_ops);
                """))
                logger.info("Neon PostgreSQL HNSW vector index verified on failure_embeddings(embedding)")
            except Exception as e:
                logger.warning(f"Note creating HNSW index: {e}")

    else:
        # SQLite / test engine
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("SQLite test tables initialized")

    logger.info("Schema setup and migration complete.")
