"""Database session management."""

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = logging.getLogger(__name__)


# Convert postgresql:// to postgresql+asyncpg://
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not database_url.startswith("postgresql+asyncpg://"):
    logger.warning(f"Unexpected database URL format: {database_url[:20]}...")

# Handle sslmode and connection timeouts for asyncpg compatibility.
import urllib.parse

connect_args: dict = {}
parsed_url = urllib.parse.urlparse(database_url)
query_dict = urllib.parse.parse_qs(parsed_url.query)
sslmode = query_dict.get("sslmode", [None])[0]
ssl_flag = query_dict.get("ssl", [None])[0]

if sslmode in ("require", "verify-ca", "verify-full") or ssl_flag in ("true", "1", "require"):
    connect_args["ssl"] = True
elif sslmode in ("disable", "allow") or ssl_flag in ("false", "0"):
    connect_args["ssl"] = False
elif "sslmode=" in database_url:
    connect_args["ssl"] = True

# Strip query parameters for asyncpg if they contain parameters it doesn't recognize
if "?" in database_url:
    database_url = database_url.split("?")[0]

if database_url.startswith("postgresql+asyncpg://"):
    connect_args.setdefault("timeout", 15)
    connect_args.setdefault("command_timeout", 30)
    # Disable prepared statement caching and use anonymous statements for Neon PgBouncer pooler compatibility
    connect_args.setdefault("statement_cache_size", 0)
    connect_args.setdefault("prepared_statement_cache_size", 0)
    connect_args.setdefault("prepared_statement_name_func", lambda: "")
    logger.info("Configured asyncpg timeout (15s/30s) and anonymous statements for Neon pooler compatibility")

# Engine connection pool configuration with bounded timeouts
engine_kwargs: dict = {
    "echo": settings.sql_echo,
    "pool_pre_ping": True,
}
if not database_url.startswith("sqlite"):
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_recycle"] = 1800  # recycle idle connections every 30m
    engine_kwargs["pool_timeout"] = 15   # fail fast if connection pool exhausted

# Create async engine
engine = create_async_engine(
    database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for declarative models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency.

    Yields:
        AsyncSession: Database session.
    """
    from app.services.metrics import metrics_collector
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            metrics_collector.record_db_operation("transaction", success=True)
        except Exception:
            metrics_collector.record_db_operation("transaction", success=False)
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create vector extension, tables, and Phase 19 schema constraints."""
    from app.db.setup_schema import run_schema_migration
    await run_schema_migration(engine)
    logger.info("Database initialized successfully")



async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
