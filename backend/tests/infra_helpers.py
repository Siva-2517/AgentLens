"""Helper utilities for real infrastructure integration testing (Phase 20A)."""

import asyncio
import logging
from app.config import settings

logger = logging.getLogger(__name__)

_postgres_available_cache = None
_redis_available_cache = None


def is_postgres_available() -> bool:
    """Check whether real PostgreSQL (Neon) is reachable."""
    global _postgres_available_cache
    if _postgres_available_cache is not None:
        return _postgres_available_cache

    db_url = settings.database_url
    if not ("postgresql" in db_url or "postgres" in db_url):
        _postgres_available_cache = False
        return False

    try:
        from app.db.session import engine
        from sqlalchemy import text

        async def _check():
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1;"))

        asyncio.run(_check())
        _postgres_available_cache = True
        return True
    except Exception as e:
        logger.warning(f"PostgreSQL probe failed: {e}")
        _postgres_available_cache = False
        return False


def is_redis_available() -> bool:
    """Check whether real Redis is reachable."""
    global _redis_available_cache
    if _redis_available_cache is not None:
        return _redis_available_cache

    try:
        import redis.asyncio as aioredis

        async def _check():
            client = aioredis.from_url(settings.redis_url, socket_timeout=3.0)
            try:
                pong = await client.ping()
                return pong is True
            finally:
                await client.aclose()

        _redis_available_cache = asyncio.run(_check())
        return _redis_available_cache
    except Exception as e:
        logger.warning(f"Redis probe failed: {e}")
        _redis_available_cache = False
        return False
