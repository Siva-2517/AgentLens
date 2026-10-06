"""Tests for trace context management."""

import pytest

from agentlens import context


def test_trace_context_default():
    """Test default trace context."""
    context.clear_context()
    assert context.get_current_trace_id() is None


def test_set_and_get_trace_id():
    """Test setting and getting trace ID."""
    context.clear_context()

    context.set_current_trace_id("trace_123")
    assert context.get_current_trace_id() == "trace_123"

    context.set_current_trace_id("trace_456")
    assert context.get_current_trace_id() == "trace_456"


def test_clear_trace_context():
    """Test clearing trace context."""
    context.set_current_trace_id("trace_123")
    context.clear_context()
    assert context.get_current_trace_id() is None


def test_parent_event_context_default():
    """Test default parent event context."""
    context.clear_context()
    assert context.get_parent_event_id() is None


def test_set_and_get_parent_event_id():
    """Test setting and getting parent event ID."""
    context.clear_context()

    context.set_parent_event_id("evt_parent")
    assert context.get_parent_event_id() == "evt_parent"

    context.set_parent_event_id("evt_another")
    assert context.get_parent_event_id() == "evt_another"


def test_clear_all_context():
    """Test clearing all context variables."""
    context.set_current_trace_id("trace_123")
    context.set_parent_event_id("evt_parent")

    context.clear_context()

    assert context.get_current_trace_id() is None
    assert context.get_parent_event_id() is None


def test_context_isolation():
    """Test that context is properly isolated."""
    context.clear_context()

    # Set trace ID
    context.set_current_trace_id("trace_123")
    assert context.get_current_trace_id() == "trace_123"
    assert context.get_parent_event_id() is None

    # Set parent event ID
    context.set_parent_event_id("evt_parent")
    assert context.get_current_trace_id() == "trace_123"
    assert context.get_parent_event_id() == "evt_parent"
