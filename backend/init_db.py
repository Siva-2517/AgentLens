"""Database initialization script.

This script initializes the database by creating all tables.

For Phase 4, we use a simple approach with SQLAlchemy Base.metadata.create_all().
For production, consider using Alembic for proper migration management.

Usage:
    python init_db.py
"""

import asyncio
import logging

from app.db import init_db, close_db
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Initialize database tables."""
    logger.info("Initializing database...")
    logger.info(f"Database URL: {settings.database_url[:30]}...")

    try:
        await init_db()
        logger.info("✓ Database tables created successfully")
        logger.info("Tables created:")
        logger.info("  - traces")
        logger.info("  - events")

    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {e}")
        raise

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
