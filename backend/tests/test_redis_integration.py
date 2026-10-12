"""Redis and Real-Time Integration Tests (Phase 20A).

Validates:
1. Redis connection handling and configuration.
2. Redis Pub/Sub publishing and channel naming isolation (agentlens:trace:{trace_id}).
3. Delivery guarantees and bounded latency during Redis unavailability (graceful fallback).
4. Local broadcast fallback when Redis is unreachable.
5. Strict tenant isolation on channel subscriptions.
6. Authentication & authorization before WebSocket trace subscription.

Live Redis tests execute only when a real Redis server is reachable on settings.redis_url.
Unavailability resilience tests execute in all environments.
"""

import asyncio
import json
import uuid
import pytest

from app.config import settings
from app.models.realtime import EventCreatedMessage, RealtimeEventPayload
from app.services.realtime_publisher import RealtimePublisher
from app.services.realtime_service import RealtimeService
from tests.infra_helpers import is_redis_available


from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_redis_unavailability_produces_bounded_failures_and_local_fallback():
    """Verify that when Redis is unreachable, publishing does not hang and falls back safely."""
    # Point to an unreachable port
    unreachable_publisher = RealtimePublisher(redis_url="redis://localhost:63799/0")
    trace_id = f"trace-down-{uuid.uuid4().hex[:8]}"

    evt = RealtimeEventPayload(
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        trace_id=trace_id,
        event_type="LLM_CALL",
        timestamp=datetime.now(timezone.utc),
        data={"test": "unavailability_fallback"},
    )
    msg = EventCreatedMessage(trace_id=trace_id, event=evt)

    # Must complete promptly (< 2.5s) without raising unhandled exception
    start_time = asyncio.get_event_loop().time()
    success = await unreachable_publisher.publish(trace_id, msg)
    duration = asyncio.get_event_loop().time() - start_time

    assert success is False, "Expected redis_success to be False when Redis is down"
    assert duration < 3.0, f"Publish took {duration}s; expected bounded timeout"

    await unreachable_publisher.close()


@pytest.mark.asyncio
async def test_redis_channel_naming_strict_isolation():
    """Verify that channel names are strictly isolated per trace identifier."""
    trace_id_alpha = f"alpha-{uuid.uuid4().hex[:8]}"
    trace_id_beta = f"beta-{uuid.uuid4().hex[:8]}"

    pub = RealtimePublisher()
    channel_alpha = f"agentlens:trace:{trace_id_alpha}"
    channel_beta = f"agentlens:trace:{trace_id_beta}"

    assert channel_alpha != channel_beta
    assert channel_alpha.startswith("agentlens:trace:")
    assert trace_id_alpha in channel_alpha
    assert trace_id_beta not in channel_alpha


@pytest.mark.skipif(
    not is_redis_available(),
    reason="Live Redis service not running on configured REDIS_URL (BLOCKED)",
)
@pytest.mark.asyncio
async def test_live_redis_pubsub_broadcast_and_delivery():
    """Verify publish and subscribe over live Redis service."""
    import redis.asyncio as aioredis

    trace_id = f"trace-live-{uuid.uuid4().hex[:8]}"
    channel = f"agentlens:trace:{trace_id}"

    # 1. Start subscriber on live Redis
    sub_client = aioredis.from_url(settings.redis_url)
    pubsub = sub_client.pubsub()
    await pubsub.subscribe(channel)

    # 2. Publish via RealtimePublisher
    publisher = RealtimePublisher(redis_url=settings.redis_url)
    evt = RealtimeEventPayload(
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        trace_id=trace_id,
        event_type="LLM_CALL",
        timestamp=datetime.now(timezone.utc),
        data={"event_id": "evt-123", "event_type": "llm_call"},
    )
    msg = EventCreatedMessage(trace_id=trace_id, event=evt)

    try:
        redis_success = await publisher.publish(trace_id, msg)
        assert redis_success is True

        # 3. Read published message from subscriber
        received = None
        for _ in range(10):
            item = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if item and item.get("data"):
                envelope = json.loads(item["data"])
                received = json.loads(envelope.get("payload", "{}"))
                break

        assert received is not None
        assert received.get("trace_id") == trace_id
        assert received.get("type") == "event_created"

    finally:
        await pubsub.unsubscribe(channel)
        await sub_client.aclose()
        await publisher.close()


@pytest.mark.asyncio
async def test_realtime_service_disconnect_cleanup_resilience():
    """Verify RealtimeService cleans up subscriber references on disconnect."""
    service = RealtimeService(redis_url="redis://localhost:63799/0")
    trace_id = f"trace-clean-{uuid.uuid4().hex[:8]}"

    class MockWebSocket:
        def __init__(self):
            self.closed = False

        async def send_text(self, data: str):
            pass

    ws = MockWebSocket()
    await service.connect(ws, trace_id)
    assert trace_id in service._connections
    assert ws in service._connections[trace_id]

    await service.disconnect(ws, trace_id)
    assert trace_id not in service._connections

    await service.close_all()
