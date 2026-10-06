"""Tests for trace management API."""

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
def valid_trace():
    """Create a valid trace payload."""
    return {
        "trace_id": "trace_123",
        "name": "test-agent",
        "start_time": datetime.utcnow().isoformat(),
        "status": "running",
        "metadata": {"version": "1.0"},
    }


@pytest.fixture
def valid_headers():
    """Create valid request headers."""
    return {
        "Authorization": "Bearer test_api_key_123",
        "X-AgentLens-Project": "test-project",
    }


def test_create_valid_trace(client, valid_trace, valid_headers):
    """Test creating a valid trace."""
    response = client.post(
        "/api/v1/traces",
        json=valid_trace,
        headers=valid_headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["trace_id"] == valid_trace["trace_id"]
    assert data["name"] == valid_trace["name"]
    assert data["status"] == valid_trace["status"]


def test_create_trace_missing_api_key(client, valid_trace):
    """Test creating trace without API key."""
    response = client.post(
        "/api/v1/traces",
        json=valid_trace,
    )

    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


def test_create_trace_invalid_api_key(client, valid_trace):
    """Test creating trace with invalid API key."""
    headers = {"Authorization": "Bearer invalid_key"}

    response = client.post(
        "/api/v1/traces",
        json=valid_trace,
        headers=headers,
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_create_trace_invalid_payload(client, valid_headers):
    """Test creating trace with invalid payload."""
    invalid_trace = {
        "trace_id": "trace_123",
        # Missing required fields
    }

    response = client.post(
        "/api/v1/traces",
        json=invalid_trace,
        headers=valid_headers,
    )

    assert response.status_code == 422  # Pydantic validation error


def test_create_trace_without_project_header(client, valid_trace):
    """Test creating trace without project header."""
    headers = {"Authorization": "Bearer test_api_key_123"}

    response = client.post(
        "/api/v1/traces",
        json=valid_trace,
        headers=headers,
    )

    assert response.status_code == 201  # Project header is optional


def test_list_traces_unauthenticated(client):
    """Test listing traces without API key."""
    response = client.get("/api/v1/traces")
    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


def test_list_traces_invalid_api_key(client):
    """Test listing traces with invalid API key."""
    response = client.get("/api/v1/traces", headers={"Authorization": "Bearer bad_key"})
    assert response.status_code == 401


def test_list_traces_empty(client, valid_headers):
    """Test listing traces when database is empty."""
    response = client.get("/api/v1/traces", headers=valid_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_traces_multiple_and_ordering(client, valid_headers):
    """Test listing multiple traces with deterministic start_time descending ordering and event count."""
    trace_early = {
        "trace_id": "trace_early",
        "name": "early-agent",
        "start_time": "2026-01-01T10:00:00Z",
        "end_time": "2026-01-01T10:00:05Z",
        "status": "completed",
    }
    trace_late = {
        "trace_id": "trace_late",
        "name": "late-agent",
        "start_time": "2026-01-01T12:00:00Z",
        "end_time": "2026-01-01T12:00:02Z",
        "status": "completed",
    }
    client.post("/api/v1/traces", json=trace_early, headers=valid_headers)
    client.post("/api/v1/traces", json=trace_late, headers=valid_headers)

    event_payload = {
        "event_id": "evt_late_1",
        "trace_id": "trace_late",
        "event_type": "AGENT_START",
        "timestamp": "2026-01-01T12:00:00Z",
        "data": {},
        "metadata": {},
    }
    event_res = client.post("/api/v1/events", json=[event_payload], headers=valid_headers)
    assert event_res.status_code == 201

    response = client.get("/api/v1/traces", headers=valid_headers)
    assert response.status_code == 200
    traces = response.json()
    assert len(traces) == 2
    # Deterministic order: newest start_time first
    assert traces[0]["trace_id"] == "trace_late"
    assert traces[0]["event_count"] == 1
    assert traces[0]["duration_ms"] == 2000.0

    assert traces[1]["trace_id"] == "trace_early"
    assert traces[1]["event_count"] == 0
    assert traces[1]["duration_ms"] == 5000.0

