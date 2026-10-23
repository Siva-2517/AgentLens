"""Trace context management for AgentLens SDK."""

import contextvars
from typing import Optional

# Context variable for current trace ID
_trace_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agentlens_trace_id", default=None
)

# Context variable for current parent event ID
_parent_event_context: contextvars.ContextVar[
    Optional[str]
] = contextvars.ContextVar("agentlens_parent_event_id", default=None)


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID from context.

    Returns:
        Current trace ID or None if not in a trace context.
    """
    return _trace_context.get()


def set_current_trace_id(trace_id: Optional[str]) -> None:
    """Set the current trace ID in context.

    Args:
        trace_id: Trace ID to set, or None to clear.
    """
    _trace_context.set(trace_id)


def get_parent_event_id() -> Optional[str]:
    """Get the current parent event ID from context.

    Returns:
        Current parent event ID or None.
    """
    return _parent_event_context.get()


def set_parent_event_id(event_id: Optional[str]) -> None:
    """Set the current parent event ID in context.

    Args:
        event_id: Parent event ID to set, or None to clear.
    """
    _parent_event_context.set(event_id)


def clear_context() -> None:
    """Clear all context variables."""
    _trace_context.set(None)
    _parent_event_context.set(None)
