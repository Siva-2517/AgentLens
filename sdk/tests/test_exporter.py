"""Tests for HTTP exporter."""

import pytest
from unittest.mock import Mock, patch

from agentlens.config import AgentLensConfig
from agentlens.exporter import HTTPExporter
from agentlens.types import Event, EventType, Trace


@pytest.fixture
def config():
    """Create test configuration."""
    return AgentLensConfig(
        api_url="http://test.example.com",
        api_key="test_key",
        project_name="test-project",
    )


@pytest.fixture
def exporter(config):
    """Create test exporter."""
    return HTTPExporter(config)


def test_exporter_initialization(exporter, config):
    """Test exporter initialization."""
    assert exporter.config == config
    assert exporter.client is not None


def test_build_headers(exporter):
    """Test building HTTP headers."""
    headers = exporter._build_headers()

    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "agentlens-sdk/0.1.0"
    assert headers["Authorization"] == "Bearer test_key"
    assert headers["X-AgentLens-Project"] == "test-project"


def test_build_headers_without_optional_fields():
    """Test building headers without API key and project."""
    config = AgentLensConfig(api_url="http://test.example.com")
    exporter = HTTPExporter(config)

    headers = exporter._build_headers()

    assert "Authorization" not in headers
    assert "X-AgentLens-Project" not in headers


@patch("httpx.Client.post")
def test_export_trace(mock_post, exporter):
    """Test exporting a trace."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    trace = Trace(trace_id="trace_123", name="test-trace")
    result = exporter.export_trace(trace)

    assert result is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "/api/v1/traces"


@patch("httpx.Client.post")
def test_export_trace_disabled(mock_post):
    """Test export when disabled."""
    config = AgentLensConfig(enabled=False)
    exporter = HTTPExporter(config)

    trace = Trace(trace_id="trace_123", name="test-trace")
    result = exporter.export_trace(trace)

    assert result is False
    mock_post.assert_not_called()


@patch("httpx.Client.post")
def test_export_trace_http_error(mock_post, exporter):
    """Test export with HTTP error."""
    mock_post.side_effect = Exception("Network error")

    trace = Trace(trace_id="trace_123", name="test-trace")
    result = exporter.export_trace(trace)

    assert result is False


@patch("httpx.Client.post")
def test_export_events(mock_post, exporter):
    """Test exporting events."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    events = [
        Event(
            event_id="evt_1",
            trace_id="trace_123",
            event_type=EventType.LLM_CALL,
        ),
        Event(
            event_id="evt_2",
            trace_id="trace_123",
            event_type=EventType.LLM_RESPONSE,
        ),
    ]

    result = exporter.export_events(events)

    assert result is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "/api/v1/events"


@patch("httpx.Client.post")
def test_export_single_event(mock_post, exporter):
    """Test exporting a single event."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    event = Event(
        event_id="evt_1",
        trace_id="trace_123",
        event_type=EventType.ERROR,
    )

    result = exporter.export_event(event)

    assert result is True
    mock_post.assert_called_once()


def test_export_empty_events(exporter):
    """Test exporting empty event list."""
    result = exporter.export_events([])
    assert result is True


def test_exporter_context_manager():
    """Test exporter as context manager."""
    config = AgentLensConfig()

    with HTTPExporter(config) as exporter:
        assert exporter.client is not None

    # Client should be closed after exit


def test_exporter_close(exporter):
    """Test closing exporter."""
    exporter.close()
    # Should not raise any errors
