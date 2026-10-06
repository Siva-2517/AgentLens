"""HTTP exporter for sending events to AgentLens API."""

import logging
from typing import List

import httpx

from agentlens.config import AgentLensConfig
from agentlens.types import Event, Trace

logger = logging.getLogger(__name__)


class HTTPExporter:
    """Exports events and traces to AgentLens API via HTTP."""

    def __init__(self, config: AgentLensConfig):
        """Initialize HTTP exporter.

        Args:
            config: SDK configuration.
        """
        self.config = config
        self.client = httpx.Client(
            base_url=config.api_url,
            timeout=config.timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for requests.

        Returns:
            Dictionary of headers.
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "agentlens-sdk/0.1.0",
        }

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        if self.config.project_name:
            headers["X-AgentLens-Project"] = self.config.project_name

        return headers

    def export_trace(self, trace: Trace) -> bool:
        """Export a trace to the API.

        Args:
            trace: Trace to export.

        Returns:
            True if successful, False otherwise.
        """
        if not self.config.enabled:
            logger.debug("Exporter disabled, skipping trace export")
            return False

        try:
            response = self.client.post(
                "/api/v1/traces",
                json=trace.model_dump(mode="json"),
            )
            response.raise_for_status()
            logger.debug(f"Exported trace {trace.trace_id}")
            return True

        except Exception as e:
            logger.warning(f"Failed to export trace {trace.trace_id}: {e}")
            return False

    def export_events(self, events: List[Event]) -> bool:
        """Export a batch of events to the API.

        Args:
            events: List of events to export.

        Returns:
            True if successful, False otherwise.
        """
        if not self.config.enabled:
            logger.debug("Exporter disabled, skipping events export")
            return False

        if not events:
            return True

        try:
            response = self.client.post(
                "/api/v1/events",
                json=[event.model_dump(mode="json") for event in events],
            )
            response.raise_for_status()
            logger.debug(f"Exported {len(events)} events")
            return True

        except Exception as e:
            logger.warning(f"Failed to export {len(events)} events: {e}")
            return False

    def export_event(self, event: Event) -> bool:
        """Export a single event to the API.

        Args:
            event: Event to export.

        Returns:
            True if successful, False otherwise.
        """
        return self.export_events([event])

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
