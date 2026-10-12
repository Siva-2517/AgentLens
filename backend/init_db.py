"""Database initialization and schema migration script (Phase 19).

Initializes PostgreSQL (Neon) or SQLite with all multi-tenant tables,
vector extension, indexes, and foreign key constraints.

Usage:
    python init_db.py
"""

import asyncio
import logging

from app.config import settings
from app.db import close_db, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Initialize database tables and constraints."""
    logger.info("Initializing database...")
    logger.info(f"Database URL: {settings.database_url[:30]}...")

    try:
        await init_db()
        logger.info("✓ Database tables and multi-tenant constraints created successfully")
        logger.info("Tables configured:")
        logger.info("  - users")
        logger.info("  - organizations")
        logger.info("  - organization_members")
        logger.info("  - projects")
        logger.info("  - api_keys")
        logger.info("  - traces (project_id FK NOT NULL)")
        logger.info("  - events (trace_id FK)")
        logger.info("  - failure_embeddings (trace_id FK, project_id FK)")

    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {e}")
        raise

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
