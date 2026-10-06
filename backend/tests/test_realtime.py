"""Tests for Phase 10 Real-Time WebSocket and Redis Pub/Sub monitoring."""

import asyncio
from datetime import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.db import get_db
from app.main import app
from app.models.realtime import (
    EventCreatedMessage,
    RealtimeEventPayload,
    TraceCompletedMessage,
    TraceStartedMessage,
)
from app.services.realtime_publisher import RealtimePublisher
from app.services.realtime_service import RealtimeService


@pytest.fixture
def client(override_get_db):
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_trace(client):
    """Create a sample trace in the database."""
    headers = {
        "Authorization": "Bearer test_api_key_123",
        "X-AgentLens-Project": "test-project",
    }
    payload = {
        "trace_id": "trace_rt_123",
        "name": "realtime-agent",
        "start_time": datetime.utcnow().isoformat(),
        "status": "running",
        "metadata": {},
    }
    res = client.post("/api/v1/traces", json=payload, headers=headers)
    assert res.status_code == 201
    return payload


@pytest.mark.asyncio
async def test_redis_publisher_successful():
    """Test successful message publication to Redis."""
    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(return_value=1)

    publisher = RealtimePublisher(redis_url="redis://localhost:6379/0")
    publisher._redis = mock_redis

    msg = TraceStartedMessage(
        trace_id="tr_1",
        name="Agent",
        start_time=datetime.utcnow(),
    )
    success = await publisher.publish("tr_1", msg)
    assert success is True
    assert mock_redis.publish.called
    channel_arg, payload_arg = mock_redis.publish.call_args[0]
    assert channel_arg == "agentlens:trace:tr_1"
    assert "trace_started" in payload_arg


@pytest.mark.asyncio
async def test_redis_publisher_failure_resilience():
    """Test that Redis failure does not raise an exception and returns False."""
    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = ConnectionError("Redis is unreachable")

    publisher = RealtimePublisher(redis_url="redis://localhost:6379/0")
    publisher._redis = mock_redis

    msg = TraceStartedMessage(
        trace_id="tr_1",
        name="Agent",
        start_time=datetime.utcnow(),
    )
    # Should not raise exception
    success = await publisher.publish("tr_1", msg)
    assert success is False


def test_ingestion_succeeds_even_when_redis_fails(client, sample_trace):
    """Test HTTP event ingestion succeeds normally even if Redis publish raises an error."""
    headers = {"Authorization": "Bearer test_api_key_123"}
    event_payload = {
        "event_id": "evt_resilience_1",
        "trace_id": sample_trace["trace_id"],
        "event_type": "LLM_CALL",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"prompt": "Hello"},
        "metadata": {},
    }

    with patch(
        "app.services.realtime_publisher.realtime_publisher.publish",
        side_effect=Exception("Redis down completely"),
    ):
        res = client.post("/api/v1/events", json=[event_payload], headers=headers)
        # Ingestion must NOT fail
        assert res.status_code == 201
        assert res.json()[0]["event_id"] == "evt_resilience_1"


def test_websocket_missing_api_key(client, sample_trace):
    """Test WebSocket connection without API key is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/api/v1/ws/traces/{sample_trace['trace_id']}"
        ) as ws:
            ws.receive_text()


def test_websocket_invalid_api_key(client, sample_trace):
    """Test WebSocket connection with invalid API key is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/api/v1/ws/traces/{sample_trace['trace_id']}?token=invalid_key"
        ) as ws:
            ws.receive_text()


def test_websocket_nonexistent_trace(client):
    """Test WebSocket connection to non-existent trace is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect(
            "/api/v1/ws/traces/non_existent_trace?token=test_api_key_123"
        ) as ws:
            ws.receive_text()


def test_websocket_authenticated_connect_and_ping(client, sample_trace):
    """Test WebSocket connection and ping/pong handshake."""
    with client.websocket_connect(
        f"/api/v1/ws/traces/{sample_trace['trace_id']}?token=test_api_key_123"
    ) as ws:
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_receives_event_created(client, sample_trace):
    """Test WebSocket client receives real-time event_created messages on event ingestion."""
    headers = {"Authorization": "Bearer test_api_key_123"}
    trace_id = sample_trace["trace_id"]

    with client.websocket_connect(
        f"/api/v1/ws/traces/{trace_id}?token=test_api_key_123"
    ) as ws:
        # Ingest an event via HTTP POST
        event_payload = {
            "event_id": "evt_live_101",
            "trace_id": trace_id,
            "event_type": "TOOL_CALL",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"tool": "search"},
            "metadata": {},
        }
        res = client.post("/api/v1/events", json=[event_payload], headers=headers)
        assert res.status_code == 201

        # WebSocket should receive event_created message
        raw_msg = ws.receive_text()
        msg_data = json.loads(raw_msg)

        assert msg_data["type"] == "event_created"
        assert msg_data["trace_id"] == trace_id
        assert msg_data["event"]["event_id"] == "evt_live_101"
        assert msg_data["event"]["event_type"] == "TOOL_CALL"


def test_websocket_receives_trace_completed_on_agent_end(client, sample_trace):
    """Test WebSocket receives both event_created and trace_completed when AGENT_END is ingested."""
    headers = {"Authorization": "Bearer test_api_key_123"}
    trace_id = sample_trace["trace_id"]

    with client.websocket_connect(
        f"/api/v1/ws/traces/{trace_id}?token=test_api_key_123"
    ) as ws:
        # Ingest AGENT_END
        end_event = {
            "event_id": "evt_end_999",
            "trace_id": trace_id,
            "event_type": "AGENT_END",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"status": "completed"},
            "metadata": {},
        }
        res = client.post("/api/v1/events", json=[end_event], headers=headers)
        assert res.status_code == 201

        # First message: event_created
        msg1 = json.loads(ws.receive_text())
        assert msg1["type"] == "event_created"
        assert msg1["event"]["event_type"] == "AGENT_END"

        # Second message: trace_completed
        msg2 = json.loads(ws.receive_text())
        assert msg2["type"] == "trace_completed"
        assert msg2["trace_id"] == trace_id
        assert msg2["status"] == "completed"


@pytest.mark.asyncio
async def test_realtime_service_disconnect_cleanup():
    """Test that RealtimeService cleanly cleans up connections and Redis tasks on disconnect."""
    service = RealtimeService()
    mock_ws = AsyncMock()

    await service.connect(mock_ws, "trace_cleanup_test")
    assert "trace_cleanup_test" in service._connections
    assert mock_ws in service._connections["trace_cleanup_test"]

    await service.disconnect(mock_ws, "trace_cleanup_test")
    assert "trace_cleanup_test" not in service._connections
