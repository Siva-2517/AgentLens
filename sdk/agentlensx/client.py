"""AgentLens client for trace and event management."""

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

from agentlensx.config import AgentLensConfig
from agentlensx.context import (
    clear_context,
    get_current_trace_id,
    get_parent_event_id,
    set_current_trace_id,
    set_parent_event_id,
)
from agentlensx.exporter import HTTPExporter
from agentlensx.types import Event, EventType, Trace

logger = logging.getLogger(__name__)


class AgentLens:
    """Main AgentLens SDK client for capturing agent telemetry."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        project_name: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize AgentLens client.

        Args:
            api_url: AgentLens API base URL (defaults to AGENTLENS_API_URL env or http://localhost:8000).
            api_key: Optional API key for authentication (defaults to AGENTLENS_API_KEY env).
            project_name: Optional project name for organization (defaults to AGENTLENS_PROJECT_NAME env).
            **kwargs: Additional configuration options.
        """
        config_kwargs: dict[str, Any] = {}
        if api_url is not None:
            config_kwargs["api_url"] = api_url
        if api_key is not None:
            config_kwargs["api_key"] = api_key
        if project_name is not None:
            config_kwargs["project_name"] = project_name
        config_kwargs.update(kwargs)

        self.config = AgentLensConfig(**config_kwargs)
        self.exporter = HTTPExporter(self.config)
        self._traces: dict[str, Trace] = {}
        self._events: list[Event] = []

        logger.info(f"AgentLens initialized with API URL: {self.config.api_url}")

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID.

        Returns:
            UUID-based trace ID.
        """
        return str(uuid.uuid4())

    def _generate_event_id(self) -> str:
        """Generate a unique event ID.

        Returns:
            UUID-based event ID.
        """
        return str(uuid.uuid4())

    def create_trace(
        self,
        name: str,
        trace_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Trace:
        """Create a new trace.

        Args:
            name: Trace name/description.
            trace_id: Optional custom trace ID (auto-generated if not provided).
            metadata: Optional trace metadata.

        Returns:
            Created trace object.
        """
        if trace_id is None:
            trace_id = self._generate_trace_id()

        trace = Trace(
            trace_id=trace_id,
            name=name,
            metadata=metadata or {},
        )

        self._traces[trace_id] = trace
        self.exporter.export_trace(trace)

        logger.debug(f"Created trace {trace_id}: {name}")
        return trace

    def end_trace(
        self,
        trace_id: str,
        status: str = "completed",
    ) -> None:
        """End a trace.

        Args:
            trace_id: Trace ID to end.
            status: Final status (e.g., 'completed', 'failed').
        """
        if trace_id not in self._traces:
            logger.warning(f"Trace {trace_id} not found")
            return

        trace = self._traces[trace_id]
        trace.end_time = datetime.utcnow()
        trace.status = status

        self.exporter.export_trace(trace)
        logger.debug(f"Ended trace {trace_id} with status: {status}")

    def create_event(
        self,
        event_type: EventType,
        data: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Event:
        """Create an event.

        Args:
            event_type: Type of event.
            data: Event-specific data.
            trace_id: Trace ID (uses current context if not provided).
            parent_event_id: Parent event ID (uses current context if not provided).
            metadata: Optional event metadata.

        Returns:
            Created event object.
        """
        # Use context if trace_id not provided
        if trace_id is None:
            trace_id = get_current_trace_id()

        if trace_id is None:
            logger.warning("No trace context available for event")
            trace_id = "unknown"

        # Use context if parent_event_id not provided
        if parent_event_id is None:
            parent_event_id = get_parent_event_id()

        event = Event(
            event_id=self._generate_event_id(),
            trace_id=trace_id,
            event_type=event_type,
            data=data or {},
            parent_event_id=parent_event_id,
            metadata=metadata or {},
        )

        self._events.append(event)

        # Auto-flush if batch size reached
        if len(self._events) >= self.config.batch_size:
            self.flush()

        logger.debug(f"Created event {event.event_id} of type {event_type}")
        return event

    def flush(self) -> None:
        """Flush all pending events to the API."""
        if not self._events:
            return

        events_to_send = self._events.copy()
        self._events.clear()

        self.exporter.export_events(events_to_send)
        logger.debug(f"Flushed {len(events_to_send)} events")

    @contextmanager
    def trace(
        self,
        name: str,
        trace_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Context manager for tracing agent execution.

        Usage:
            with lens.trace("my-agent"):
                # Agent execution here
                result = agent.invoke(input)

        Args:
            name: Trace name.
            trace_id: Optional custom trace ID.
            metadata: Optional trace metadata.

        Yields:
            The trace ID.
        """
        trace = self.create_trace(name, trace_id, metadata)
        trace_id = trace.trace_id

        # Set trace context
        previous_trace_id = get_current_trace_id()
        set_current_trace_id(trace_id)

        # Create AGENT_START event
        start_event = self.create_event(
            EventType.AGENT_START,
            data={"trace_name": name},
            trace_id=trace_id,
        )

        try:
            yield trace_id

            # Create AGENT_END event
            self.create_event(
                EventType.AGENT_END,
                data={"status": "completed"},
                trace_id=trace_id,
            )
            self.end_trace(trace_id, status="completed")

        except Exception as e:
            # Create ERROR event
            self.create_event(
                EventType.ERROR,
                data={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                trace_id=trace_id,
            )
            self.end_trace(trace_id, status="failed")
            raise

        finally:
            # Restore previous trace context
            set_current_trace_id(previous_trace_id)
            # Flush events
            self.flush()

    def close(self) -> None:
        """Close the client and flush remaining events."""
        self.flush()
        self.exporter.close()
        logger.info("AgentLens client closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
