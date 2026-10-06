"""WebSocket connection and real-time subscription management service."""

import asyncio
import json
import logging
from typing import Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)


class RealtimeService:
    """Manages WebSocket connections and Redis pub/sub subscriptions for traces."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        # trace_id -> set of active WebSockets
        self._connections: dict[str, Set[WebSocket]] = {}
        # trace_id -> background asyncio.Task listening to Redis
        self._redis_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, trace_id: str) -> None:
        """Register a new WebSocket connection for a trace.

        Args:
            websocket: Accepted WebSocket connection.
            trace_id: Target trace ID.
        """
        async with self._lock:
            if trace_id not in self._connections:
                self._connections[trace_id] = set()

            self._connections[trace_id].add(websocket)
            logger.info(
                f"WebSocket connected for trace '{trace_id}'. "
                f"Active subscribers for trace: {len(self._connections[trace_id])}"
            )

            # Start Redis listener if this is the first connection for this trace
            if trace_id not in self._redis_tasks or self._redis_tasks[trace_id].done():
                self._redis_tasks[trace_id] = asyncio.create_task(
                    self._listen_to_redis_channel(trace_id)
                )

    async def disconnect(self, websocket: WebSocket, trace_id: str) -> None:
        """Unregister a WebSocket connection and clean up subscriptions if empty.

        Args:
            websocket: WebSocket connection to remove.
            trace_id: Target trace ID.
        """
        async with self._lock:
            if trace_id in self._connections:
                self._connections[trace_id].discard(websocket)
                remaining = len(self._connections[trace_id])
                logger.info(
                    f"WebSocket disconnected from trace '{trace_id}'. "
                    f"Remaining subscribers: {remaining}"
                )

                if remaining == 0:
                    del self._connections[trace_id]
                    # Cancel Redis listener task when no subscribers remain
                    task = self._redis_tasks.pop(trace_id, None)
                    if task and not task.done():
                        task.cancel()

    async def _send_to_sockets(self, trace_id: str, message_json: str) -> None:
        """Send a JSON payload to all active WebSockets for a trace."""
        sockets = list(self._connections.get(trace_id, set()))
        if not sockets:
            return

        dead_sockets = []
        for ws in sockets:
            try:
                await ws.send_text(message_json)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket for trace '{trace_id}': {e}")
                dead_sockets.append(ws)

        for dead_ws in dead_sockets:
            await self.disconnect(dead_ws, trace_id)

    async def broadcast_locally(self, trace_id: str, message_json: str) -> None:
        """Direct in-memory broadcast for local subscribers with zero latency."""
        await self._send_to_sockets(trace_id, message_json)

    async def _listen_to_redis_channel(self, trace_id: str) -> None:
        """Background worker that subscribes to Redis pub/sub channel for a trace."""
        channel_name = f"agentlens:trace:{trace_id}"
        pubsub = None
        redis_client = None

        try:
            from app.services.realtime_publisher import SERVER_INSTANCE_ID
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=5.0,
            )
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel_name)
            logger.info(f"Subscribed to Redis channel '{channel_name}'")

            while True:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message and message.get("type") == "message":
                        raw_data = message.get("data")
                        if raw_data:
                            # Unwrap envelope and check server_id to avoid echo to local clients
                            try:
                                envelope = json.loads(raw_data)
                                if isinstance(envelope, dict) and "server_id" in envelope:
                                    if envelope["server_id"] == SERVER_INSTANCE_ID:
                                        # Skip: already broadcast locally by this instance
                                        continue
                                    actual_payload = envelope.get("payload", raw_data)
                                else:
                                    actual_payload = raw_data
                            except Exception:
                                actual_payload = raw_data

                            # Forward remote message to local WebSockets connected to this trace
                            await self._send_to_sockets(trace_id, actual_payload)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Error reading from Redis channel '{channel_name}': {e}")
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(
                f"Redis subscriber encountered error for channel '{channel_name}': {e}. "
                "RealtimeService will fall back to local in-memory broadcasting."
            )
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(channel_name)
                    await pubsub.aclose()
                except Exception:
                    pass
            if redis_client is not None:
                try:
                    await redis_client.aclose()
                except Exception:
                    pass
            logger.info(f"Closed Redis subscription for channel '{channel_name}'")

    async def close_all(self) -> None:
        """Close all connections and listener tasks on server shutdown."""
        async with self._lock:
            # Cancel all Redis listener tasks
            for task in self._redis_tasks.values():
                if not task.done():
                    task.cancel()
            self._redis_tasks.clear()

            # Close all active WebSockets
            for trace_id, sockets in list(self._connections.items()):
                for ws in list(sockets):
                    try:
                        await ws.close(code=1001, reason="Server shutting down")
                    except Exception:
                        pass
            self._connections.clear()


# Singleton instance
realtime_service = RealtimeService()
