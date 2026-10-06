"""Trace Reconstruction Service.

Transforms raw persisted trace and event records into a structured,
chronologically ordered, hierarchical execution trace with calculated metadata.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventModel, TraceModel
from app.db.repositories import EventRepository, TraceRepository
from app.models.event import EventType
from app.models.reconstructed_trace import (
    ReconstructedEvent,
    ReconstructedTrace,
    TraceExecutionMetadata,
)

logger = logging.getLogger(__name__)

# Deterministic ordering priority for events with identical timestamps
EVENT_TYPE_ORDER: Dict[str, int] = {
    EventType.AGENT_START.value: 0,
    EventType.LLM_CALL.value: 1,
    EventType.LLM_RESPONSE.value: 2,
    EventType.TOOL_CALL.value: 3,
    EventType.TOOL_RESPONSE.value: 4,
    EventType.STATE_CHANGE.value: 5,
    EventType.RETRY.value: 6,
    EventType.ERROR.value: 7,
    EventType.AGENT_END.value: 8,
}


class TraceNotFoundError(Exception):
    """Raised when a requested trace_id does not exist."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        super().__init__(f"Trace '{trace_id}' not found")


class TraceReconstructionService:
    """Service for reconstructing execution traces from raw database events."""

    async def reconstruct_trace(
        self,
        trace_id: str,
        db: AsyncSession,
    ) -> ReconstructedTrace:
        """Reconstruct a trace and its events into a coherent execution model.

        Args:
            trace_id: The trace identifier to reconstruct.
            db: Database session.

        Returns:
            ReconstructedTrace with ordered events, hierarchy, and metadata.

        Raises:
            TraceNotFoundError: If the trace does not exist.
        """
        trace_repo = TraceRepository(db)
        event_repo = EventRepository(db)

        # 1. Fetch trace
        trace_model = await trace_repo.get_by_trace_id(trace_id)
        if not trace_model:
            logger.warning(f"Trace not found: {trace_id}")
            raise TraceNotFoundError(trace_id)

        # 2. Fetch raw events
        event_models = await event_repo.get_by_trace_id(trace_id)

        # 3. Perform in-memory reconstruction
        return self._reconstruct_from_models(trace_model, event_models)

    def _reconstruct_from_models(
        self,
        trace: TraceModel,
        events: List[EventModel],
    ) -> ReconstructedTrace:
        """Perform in-memory reconstruction of a trace from ORM models."""
        # 1. Order events deterministically
        sorted_events = self._order_events(events)

        # 2. Build parent-child hierarchy and calculate depths
        reconstructed_events, root_event_ids = self._build_hierarchy(sorted_events, trace.name)

        # 3. Compute execution metadata
        metadata, duration_ms = self._calculate_metadata(trace, reconstructed_events)

        return ReconstructedTrace(
            trace_id=trace.trace_id,
            name=trace.name,
            project_name=trace.project_name,
            start_time=trace.start_time,
            end_time=trace.end_time,
            status=trace.status,
            duration_ms=duration_ms,
            event_count=len(reconstructed_events),
            metadata=metadata,
            events=reconstructed_events,
            root_event_ids=root_event_ids,
        )

    def _order_events(self, events: List[EventModel]) -> List[EventModel]:
        """Order events deterministically.

        Primary sort: timestamp ascending.
        Secondary sort: logical event type sequence if equal.
        Tertiary sort: event_id string comparison.
        """
        def sort_key(event: EventModel):
            ts = event.timestamp
            # If timestamp is naive, make sure comparison is consistent
            priority = EVENT_TYPE_ORDER.get(event.event_type, 99)
            event_id = event.event_id or ""
            return (ts, priority, event_id)

        return sorted(events, key=sort_key)

    def _build_hierarchy(
        self,
        sorted_events: List[EventModel],
        trace_name: str,
    ) -> tuple[List[ReconstructedEvent], List[str]]:
        """Build parent-child relationships, depth levels, and children IDs."""
        if not sorted_events:
            return [], []

        # Convert to intermediate dictionary mapping
        reconstructed_dict: Dict[str, ReconstructedEvent] = {}
        for ev in sorted_events:
            # Extract agent name from event metadata, data, or fallback to trace name
            agent_name = (
                ev.data.get("agent_name")
                or ev.metadata_.get("agent_name")
                or trace_name
            )

            # Check if duration_ms already present in data or metadata
            raw_duration = (
                ev.data.get("duration_ms")
                or ev.metadata_.get("duration_ms")
            )
            parsed_duration = float(raw_duration) if raw_duration is not None else None

            rec_event = ReconstructedEvent(
                event_id=ev.event_id,
                trace_id=ev.trace_id,
                parent_event_id=ev.parent_event_id,
                event_type=ev.event_type,
                timestamp=ev.timestamp,
                agent_name=agent_name,
                data=ev.data or {},
                metadata=ev.metadata_ or {},
                depth=0,
                children_ids=[],
                duration_ms=parsed_duration,
            )
            reconstructed_dict[ev.event_id] = rec_event

        # Populate children_ids and calculate paired durations
        root_event_ids: List[str] = []
        for ev_id, rec_event in reconstructed_dict.items():
            parent_id = rec_event.parent_event_id
            if parent_id and parent_id in reconstructed_dict:
                parent = reconstructed_dict[parent_id]
                parent.children_ids.append(ev_id)

                # Pair-duration inference: if response follows call with same parent
                if rec_event.duration_ms is None and parent.timestamp <= rec_event.timestamp:
                    if (
                        (parent.event_type == EventType.LLM_CALL.value and rec_event.event_type == EventType.LLM_RESPONSE.value)
                        or (parent.event_type == EventType.TOOL_CALL.value and rec_event.event_type == EventType.TOOL_RESPONSE.value)
                    ):
                        rec_event.duration_ms = (
                            rec_event.timestamp - parent.timestamp
                        ).total_seconds() * 1000.0
            else:
                # No parent or orphaned parent reference
                root_event_ids.append(ev_id)

        # Calculate depths via memoized traversal with cycle detection
        depth_memo: Dict[str, int] = {}

        def get_depth(cur_id: str, visited: Set[str]) -> int:
            if cur_id in depth_memo:
                return depth_memo[cur_id]
            ev = reconstructed_dict.get(cur_id)
            if not ev or not ev.parent_event_id or ev.parent_event_id not in reconstructed_dict:
                depth_memo[cur_id] = 0
                return 0
            if cur_id in visited:
                # Cycle detected; break cycle gracefully
                depth_memo[cur_id] = 0
                return 0
            visited.add(cur_id)
            d = 1 + get_depth(ev.parent_event_id, visited)
            depth_memo[cur_id] = d
            return d

        for ev_id, rec_event in reconstructed_dict.items():
            rec_event.depth = get_depth(ev_id, set())

        # Return in the original sorted chronological order
        ordered_list = [reconstructed_dict[ev.event_id] for ev in sorted_events]
        return ordered_list, root_event_ids

    def _calculate_metadata(
        self,
        trace: TraceModel,
        events: List[ReconstructedEvent],
    ) -> tuple[TraceExecutionMetadata, Optional[float]]:
        """Calculate deterministic execution metadata and total trace duration."""
        counts_by_type: Dict[str, int] = {}
        for ev in events:
            counts_by_type[ev.event_type] = counts_by_type.get(ev.event_type, 0) + 1

        llm_calls = counts_by_type.get(EventType.LLM_CALL.value, 0)
        llm_responses = counts_by_type.get(EventType.LLM_RESPONSE.value, 0)
        tool_calls = counts_by_type.get(EventType.TOOL_CALL.value, 0)
        tool_responses = counts_by_type.get(EventType.TOOL_RESPONSE.value, 0)
        errors = counts_by_type.get(EventType.ERROR.value, 0)
        retries = counts_by_type.get(EventType.RETRY.value, 0)
        state_changes = counts_by_type.get(EventType.STATE_CHANGE.value, 0)

        has_start = counts_by_type.get(EventType.AGENT_START.value, 0) > 0
        has_end = counts_by_type.get(EventType.AGENT_END.value, 0) > 0

        first_ts = events[0].timestamp if events else None
        last_ts = events[-1].timestamp if events else None

        # Trace duration calculation:
        # 1. Prefer trace.end_time - trace.start_time
        # 2. Fall back to last_event_timestamp - first_event_timestamp
        # 3. Else 0.0 or None
        duration_ms: Optional[float] = None
        if trace.end_time and trace.start_time:
            duration_ms = max(0.0, (trace.end_time - trace.start_time).total_seconds() * 1000.0)
        elif first_ts and last_ts:
            duration_ms = max(0.0, (last_ts - first_ts).total_seconds() * 1000.0)
        elif trace.status in ("completed", "failed"):
            duration_ms = 0.0

        is_complete = bool(has_start and has_end and trace.status != "running")

        metadata = TraceExecutionMetadata(
            total_event_count=len(events),
            duration_ms=duration_ms,
            llm_call_count=llm_calls,
            llm_response_count=llm_responses,
            tool_call_count=tool_calls,
            tool_response_count=tool_responses,
            error_count=errors,
            retry_count=retries,
            state_change_count=state_changes,
            first_event_timestamp=first_ts,
            last_event_timestamp=last_ts,
            has_agent_start=has_start,
            has_agent_end=has_end,
            is_complete=is_complete,
            event_type_counts=counts_by_type,
        )

        return metadata, duration_ms


# Global singleton service instance
trace_reconstruction_service = TraceReconstructionService()
