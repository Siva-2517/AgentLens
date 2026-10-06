"""Tests for AgentLens types."""

from datetime import datetime

import pytest

from agentlens.types import Event, EventType, Trace


def test_event_type_enum():
    """Test EventType enum values."""
    assert EventType.AGENT_START == "AGENT_START"
    assert EventType.LLM_CALL == "LLM_CALL"
    assert EventType.LLM_RESPONSE == "LLM_RESPONSE"
    assert EventType.TOOL_CALL == "TOOL_CALL"
    assert EventType.TOOL_RESPONSE == "TOOL_RESPONSE"
    assert EventType.STATE_CHANGE == "STATE_CHANGE"
    assert EventType.RETRY == "RETRY"
    assert EventType.ERROR == "ERROR"
    assert EventType.AGENT_END == "AGENT_END"


def test_event_creation():
    """Test Event model creation."""
    event = Event(
        event_id="evt_123",
        trace_id="trace_456",
        event_type=EventType.LLM_CALL,
        data={"model": "gpt-4", "prompt": "test"},
        metadata={"user": "test_user"},
    )

    assert event.event_id == "evt_123"
    assert event.trace_id == "trace_456"
    assert event.event_type == EventType.LLM_CALL
    assert event.data == {"model": "gpt-4", "prompt": "test"}
    assert event.metadata == {"user": "test_user"}
    assert isinstance(event.timestamp, datetime)
    assert event.parent_event_id is None


def test_event_with_parent():
    """Test Event with parent_event_id."""
    event = Event(
        event_id="evt_child",
        trace_id="trace_123",
        event_type=EventType.TOOL_CALL,
        parent_event_id="evt_parent",
    )

    assert event.parent_event_id == "evt_parent"


def test_event_serialization():
    """Test Event JSON serialization."""
    event = Event(
        event_id="evt_123",
        trace_id="trace_456",
        event_type=EventType.ERROR,
        data={"error": "test error"},
    )

    json_data = event.model_dump(mode="json")

    assert json_data["event_id"] == "evt_123"
    assert json_data["trace_id"] == "trace_456"
    assert json_data["event_type"] == "ERROR"
    assert isinstance(json_data["timestamp"], str)  # ISO format


def test_trace_creation():
    """Test Trace model creation."""
    trace = Trace(
        trace_id="trace_123",
        name="test-agent",
        metadata={"environment": "test"},
    )

    assert trace.trace_id == "trace_123"
    assert trace.name == "test-agent"
    assert trace.status == "running"
    assert trace.metadata == {"environment": "test"}
    assert isinstance(trace.start_time, datetime)
    assert trace.end_time is None


def test_trace_completion():
    """Test Trace with end_time."""
    trace = Trace(
        trace_id="trace_123",
        name="test-agent",
        status="completed",
        end_time=datetime.utcnow(),
    )

    assert trace.status == "completed"
    assert trace.end_time is not None


def test_trace_serialization():
    """Test Trace JSON serialization."""
    trace = Trace(
        trace_id="trace_123",
        name="test-agent",
    )

    json_data = trace.model_dump(mode="json")

    assert json_data["trace_id"] == "trace_123"
    assert json_data["name"] == "test-agent"
    assert json_data["status"] == "running"
    assert isinstance(json_data["start_time"], str)  # ISO format
