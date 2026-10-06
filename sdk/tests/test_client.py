"""Tests for AgentLens client."""

import pytest

from agentlens import AgentLens, EventType
from agentlens.context import get_current_trace_id


@pytest.fixture
def client():
    """Create test client with disabled exporter."""
    return AgentLens(
        api_url="http://test.example.com",
        enabled=False,  # Disable HTTP calls for tests
    )


def test_client_initialization(client):
    """Test client initialization."""
    assert client.config.api_url == "http://test.example.com"
    assert client.config.enabled is False
    assert client._traces == {}
    assert client._events == []


def test_generate_trace_id(client):
    """Test trace ID generation."""
    trace_id1 = client._generate_trace_id()
    trace_id2 = client._generate_trace_id()

    assert isinstance(trace_id1, str)
    assert isinstance(trace_id2, str)
    assert trace_id1 != trace_id2  # Should be unique


def test_generate_event_id(client):
    """Test event ID generation."""
    event_id1 = client._generate_event_id()
    event_id2 = client._generate_event_id()

    assert isinstance(event_id1, str)
    assert isinstance(event_id2, str)
    assert event_id1 != event_id2  # Should be unique


def test_create_trace(client):
    """Test trace creation."""
    trace = client.create_trace("test-trace", metadata={"env": "test"})

    assert trace.name == "test-trace"
    assert trace.status == "running"
    assert trace.metadata == {"env": "test"}
    assert trace.trace_id in client._traces


def test_create_trace_with_custom_id(client):
    """Test trace creation with custom ID."""
    trace = client.create_trace("test-trace", trace_id="custom_123")

    assert trace.trace_id == "custom_123"
    assert "custom_123" in client._traces


def test_end_trace(client):
    """Test ending a trace."""
    trace = client.create_trace("test-trace")
    trace_id = trace.trace_id

    client.end_trace(trace_id, status="completed")

    ended_trace = client._traces[trace_id]
    assert ended_trace.status == "completed"
    assert ended_trace.end_time is not None


def test_create_event(client):
    """Test event creation."""
    trace = client.create_trace("test-trace")

    event = client.create_event(
        EventType.LLM_CALL,
        data={"model": "gpt-4"},
        trace_id=trace.trace_id,
    )

    assert event.event_type == EventType.LLM_CALL
    assert event.trace_id == trace.trace_id
    assert event.data == {"model": "gpt-4"}
    assert len(client._events) == 1


def test_create_event_with_context(client):
    """Test event creation using trace context."""
    with client.trace("test-trace") as trace_id:
        # Create event without explicit trace_id
        event = client.create_event(
            EventType.TOOL_CALL,
            data={"tool": "calculator"},
        )

        assert event.trace_id == trace_id


def test_trace_context_manager(client):
    """Test trace context manager."""
    assert get_current_trace_id() is None

    with client.trace("test-trace") as trace_id:
        # Inside context, trace ID should be set
        assert get_current_trace_id() == trace_id
        assert trace_id in client._traces

    # Outside context, trace ID should be cleared
    assert get_current_trace_id() is None


def test_trace_context_manager_success(client):
    """Test trace context manager with successful execution."""
    with client.trace("test-trace") as trace_id:
        pass  # Successful execution

    trace = client._traces[trace_id]
    assert trace.status == "completed"


def test_trace_context_manager_error(client):
    """Test trace context manager with error."""
    with pytest.raises(ValueError):
        with client.trace("test-trace") as trace_id:
            raise ValueError("Test error")

    trace = client._traces[trace_id]
    assert trace.status == "failed"


def test_flush_events(client):
    """Test flushing events."""
    trace = client.create_trace("test-trace")

    # Create some events
    client.create_event(EventType.LLM_CALL, trace_id=trace.trace_id)
    client.create_event(EventType.LLM_RESPONSE, trace_id=trace.trace_id)

    assert len(client._events) == 2

    # Flush should clear events
    client.flush()
    assert len(client._events) == 0


def test_auto_flush_on_batch_size(client):
    """Test automatic flush when batch size is reached."""
    client.config.batch_size = 3
    trace = client.create_trace("test-trace")

    # Create events up to batch size
    client.create_event(EventType.LLM_CALL, trace_id=trace.trace_id)
    client.create_event(EventType.LLM_RESPONSE, trace_id=trace.trace_id)
    assert len(client._events) == 2

    # This should trigger auto-flush
    client.create_event(EventType.TOOL_CALL, trace_id=trace.trace_id)
    assert len(client._events) == 0  # Flushed


def test_client_context_manager(client):
    """Test client as context manager."""
    with AgentLens(enabled=False) as lens:
        trace = lens.create_trace("test-trace")
        assert trace.trace_id in lens._traces

    # After exit, client should be closed
    # (events flushed, exporter closed)


def test_close_client(client):
    """Test closing client."""
    trace = client.create_trace("test-trace")
    client.create_event(EventType.LLM_CALL, trace_id=trace.trace_id)

    assert len(client._events) == 1

    client.close()

    # Events should be flushed
    assert len(client._events) == 0
