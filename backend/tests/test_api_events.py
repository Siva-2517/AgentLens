"""Tests for event ingestion API."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


@pytest.fixture
def client(override_get_db):
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def valid_event():
    """Create a valid event payload."""
    return {
        "event_id": "evt_123",
        "trace_id": "trace_123",
        "event_type": "LLM_CALL",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"model": "gpt-4", "prompt": "test"},
        "metadata": {},
    }


@pytest.fixture
def valid_headers():
    """Create valid request headers."""
    return {
        "Authorization": "Bearer test_api_key_123",
        "X-AgentLens-Project": "test-project",
    }


def test_ingest_valid_event(client, valid_event, valid_headers):
    """Test ingesting a valid event."""
    response = client.post(
        "/api/v1/events",
        json=[valid_event],
        headers=valid_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert len(data) == 1
    assert data[0]["event_id"] == valid_event["event_id"]
    assert data[0]["trace_id"] == valid_event["trace_id"]
    assert data[0]["event_type"] == valid_event["event_type"]
    assert data[0]["status"] == "received"


def test_ingest_multiple_events(client, valid_event, valid_headers):
    """Test ingesting multiple events."""
    events = [
        valid_event,
        {**valid_event, "event_id": "evt_124", "event_type": "LLM_RESPONSE"},
        {**valid_event, "event_id": "evt_125", "event_type": "TOOL_CALL"},
    ]

    response = client.post(
        "/api/v1/events",
        json=events,
        headers=valid_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert len(data) == 3
    assert data[0]["event_id"] == "evt_123"
    assert data[1]["event_id"] == "evt_124"
    assert data[2]["event_id"] == "evt_125"


def test_ingest_event_missing_api_key(client, valid_event):
    """Test ingesting event without API key."""
    response = client.post(
        "/api/v1/events",
        json=[valid_event],
    )

    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


def test_ingest_event_invalid_api_key(client, valid_event):
    """Test ingesting event with invalid API key."""
    headers = {"Authorization": "Bearer invalid_key"}

    response = client.post(
        "/api/v1/events",
        json=[valid_event],
        headers=headers,
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_ingest_event_invalid_auth_format(client, valid_event):
    """Test ingesting event with invalid authorization format."""
    headers = {"Authorization": "InvalidFormat test_api_key_123"}

    response = client.post(
        "/api/v1/events",
        json=[valid_event],
        headers=headers,
    )

    assert response.status_code == 401
    assert "Invalid authorization header format" in response.json()["detail"]


def test_ingest_event_invalid_payload(client, valid_headers):
    """Test ingesting event with invalid payload."""
    invalid_event = {
        "event_id": "evt_123",
        # Missing required fields
    }

    response = client.post(
        "/api/v1/events",
        json=[invalid_event],
        headers=valid_headers,
    )

    assert response.status_code == 422  # Pydantic validation error


def test_ingest_event_invalid_event_type(client, valid_event, valid_headers):
    """Test ingesting event with invalid event type."""
    invalid_event = {**valid_event, "event_type": "INVALID_TYPE"}

    response = client.post(
        "/api/v1/events",
        json=[invalid_event],
        headers=valid_headers,
    )

    assert response.status_code == 422


def test_ingest_event_empty_list(client, valid_headers):
    """Test ingesting empty event list."""
    response = client.post(
        "/api/v1/events",
        json=[],
        headers=valid_headers,
    )

    assert response.status_code == 400
    assert "Event list cannot be empty" in response.json()["detail"]


def test_ingest_single_event(client, valid_event, valid_headers):
    """Test single event endpoint."""
    response = client.post(
        "/api/v1/events/single",
        json=valid_event,
        headers=valid_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["event_id"] == valid_event["event_id"]
    assert data["status"] == "received"


def test_ingest_event_with_parent(client, valid_event, valid_headers):
    """Test ingesting event with parent_event_id."""
    event_with_parent = {**valid_event, "parent_event_id": "evt_parent_123"}

    response = client.post(
        "/api/v1/events",
        json=[event_with_parent],
        headers=valid_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert len(data) == 1
    assert data[0]["event_id"] == event_with_parent["event_id"]


def test_ingest_event_without_project_header(client, valid_event):
    """Test ingesting event without project header."""
    headers = {"Authorization": "Bearer test_api_key_123"}

    response = client.post(
        "/api/v1/events",
        json=[valid_event],
        headers=headers,
    )

    assert response.status_code == 201  # Project header is optional


def test_all_event_types(client, valid_event, valid_headers):
    """Test all supported event types."""
    event_types = [
        "AGENT_START",
        "LLM_CALL",
        "LLM_RESPONSE",
        "TOOL_CALL",
        "TOOL_RESPONSE",
        "STATE_CHANGE",
        "RETRY",
        "ERROR",
        "AGENT_END",
    ]

    for event_type in event_types:
        event = {**valid_event, "event_id": f"evt_{event_type}", "event_type": event_type}
        response = client.post(
            "/api/v1/events",
            json=[event],
            headers=valid_headers,
        )

        assert response.status_code == 201, f"Failed for event_type: {event_type}"
        assert response.json()[0]["event_type"] == event_type
