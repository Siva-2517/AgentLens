"""Publisher service for broadcasting execution trace events via Redis pub/sub."""

import json
import logging
import uuid
from typing import Optional

from app.config import settings
from app.models.realtime import RealtimeMessage

logger = logging.getLogger(__name__)

# Unique ID for this server process to prevent echo duplicates
SERVER_INSTANCE_ID = str(uuid.uuid4())


class RealtimePublisher:
    """Publishes real-time execution events to Redis channels.

    Guarantees:
    - Single shared Redis connection pool (avoids 1 connection per event).
    - Redis channel naming convention: agentlens:trace:{trace_id}.
    - Failure resilience: if Redis is unavailable or encounters an error,
      the failure is logged and the method returns False, ensuring database
      persistence and HTTP ingestion are NEVER interrupted.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis = None
        self._redis_available: Optional[bool] = None

    async def _get_redis(self):
        """Get or initialize the async Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
            except Exception as e:
                logger.warning(f"Could not initialize Redis client: {e}")
                self._redis = None
        return self._redis

    async def publish(self, trace_id: str, message: RealtimeMessage) -> bool:
        """Publish a real-time message to the trace-specific channel.

        Args:
            trace_id: Target trace identifier.
            message: Validated RealtimeMessage instance.

        Returns:
            True if published to Redis or local dispatcher, False on failure.
        """
        payload_json = message.model_dump_json()
        channel = f"agentlens:trace:{trace_id}"
        redis_success = False

        # 1. Attempt Redis publication
        try:
            r = await self._get_redis()
            if r is not None:
                envelope = json.dumps({"server_id": SERVER_INSTANCE_ID, "payload": payload_json})
                await r.publish(channel, envelope)
                redis_success = True
                logger.debug(f"Published real-time message to Redis channel '{channel}': {message.type}")
        except Exception as e:
            logger.warning(
                f"Redis real-time publish failed for channel '{channel}' (message type: {message.type}): {e}. "
                "Degrading gracefully without affecting HTTP ingestion."
            )
            # Invalidate connection to retry on next publish if connection dropped
            self._redis = None

        # 2. Also notify local in-memory subscribers (for local dev, tests, or dual-tier distribution)
        try:
            from app.services.realtime_service import realtime_service
            await realtime_service.broadcast_locally(trace_id, payload_json)
        except Exception as e:
            logger.debug(f"Local realtime broadcast exception: {e}")

        return redis_success

    async def close(self):
        """Clean up Redis connection."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None


# Singleton instance
realtime_publisher = RealtimePublisher()
