"""Event ingestion service."""

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import EventRepository, TraceRepository
from app.models.event import EventCreate, EventResponse

logger = logging.getLogger(__name__)


class EventService:
    """Service for handling event ingestion and storage."""

    async def ingest_event(
        self,
        event: EventCreate,
        project_name: Optional[str],
        db: AsyncSession,
    ) -> EventResponse:
        """Ingest a single event.

        Args:
            event: Event to ingest.
            project_name: Optional project name from header.
            db: Database session.

        Returns:
            Event response with status.
        """
        repo = EventRepository(db)

        # Create event in database
        db_event = await repo.create(event, project_name)

        logger.info(
            f"Ingested event {event.event_id} for trace {event.trace_id} "
            f"(type: {event.event_type}, project: {project_name})"
        )

        # If AGENT_END, update Trace status and end_time in DB
        if db_event.event_type == "AGENT_END":
            try:
                trace_repo = TraceRepository(db)
                status_val = "completed"
                if isinstance(db_event.data, dict) and db_event.data.get("status") in ("failed", "error"):
                    status_val = "failed"
                await trace_repo.update_status(
                    trace_id=db_event.trace_id,
                    status=status_val,
                    end_time=db_event.timestamp,
                )
            except Exception as e:
                logger.warning(f"Failed to update trace status on AGENT_END for {db_event.trace_id}: {e}")

        # Publish real-time event notification (failure-resilient)
        try:
            from app.models.realtime import (
                EventCreatedMessage,
                RealtimeEventPayload,
                TraceCompletedMessage,
            )
            from app.services.realtime_publisher import realtime_publisher

            event_msg = EventCreatedMessage(
                trace_id=db_event.trace_id,
                event=RealtimeEventPayload(
                    event_id=db_event.event_id,
                    trace_id=db_event.trace_id,
                    event_type=db_event.event_type,
                    timestamp=db_event.timestamp,
                    parent_event_id=db_event.parent_event_id,
                    data=db_event.data or {},
                    metadata=db_event.metadata_ or {},
                ),
            )
            await realtime_publisher.publish(db_event.trace_id, event_msg)

            if db_event.event_type == "AGENT_END":
                status_val = "completed"
                if isinstance(db_event.data, dict) and db_event.data.get("status") in ("failed", "error"):
                    status_val = "failed"
                await realtime_publisher.publish(
                    db_event.trace_id,
                    TraceCompletedMessage(
                        trace_id=db_event.trace_id,
                        status=status_val,
                        end_time=db_event.timestamp,
                    ),
                )
        except Exception as e:
            logger.warning(
                f"Failed to publish realtime notification for event {db_event.event_id}: {e}"
            )

        return EventResponse(
            event_id=db_event.event_id,
            trace_id=db_event.trace_id,
            event_type=event.event_type,
            timestamp=db_event.timestamp,
            status="received",
        )

    async def ingest_events_batch(
        self,
        events: List[EventCreate],
        project_name: Optional[str],
        db: AsyncSession,
    ) -> List[EventResponse]:
        """Ingest a batch of events.

        Args:
            events: List of events to ingest.
            project_name: Optional project name from header.
            db: Database session.

        Returns:
            List of event responses.
        """
        repo = EventRepository(db)

        # Create all events in database
        db_events = await repo.create_batch(events, project_name)

        logger.info(
            f"Ingested batch of {len(events)} events (project: {project_name})"
        )

        # Update trace status in DB for any AGENT_END events in batch
        trace_repo = TraceRepository(db)
        for db_event in db_events:
            if db_event.event_type == "AGENT_END":
                try:
                    status_val = "completed"
                    if isinstance(db_event.data, dict) and db_event.data.get("status") in ("failed", "error"):
                        status_val = "failed"
                    await trace_repo.update_status(
                        trace_id=db_event.trace_id,
                        status=status_val,
                        end_time=db_event.timestamp,
                    )
                except Exception as e:
                    logger.warning(f"Failed to update trace status on batch AGENT_END for {db_event.trace_id}: {e}")

        # Publish real-time notifications for each ingested event (failure-resilient)
        try:
            from app.models.realtime import (
                EventCreatedMessage,
                RealtimeEventPayload,
                TraceCompletedMessage,
            )
            from app.services.realtime_publisher import realtime_publisher

            for db_event, event in zip(db_events, events):
                event_msg = EventCreatedMessage(
                    trace_id=db_event.trace_id,
                    event=RealtimeEventPayload(
                        event_id=db_event.event_id,
                        trace_id=db_event.trace_id,
                        event_type=db_event.event_type,
                        timestamp=db_event.timestamp,
                        parent_event_id=db_event.parent_event_id,
                        data=db_event.data or {},
                        metadata=db_event.metadata_ or {},
                    ),
                )
                await realtime_publisher.publish(db_event.trace_id, event_msg)

                if db_event.event_type == "AGENT_END":
                    status_val = "completed"
                    if isinstance(db_event.data, dict) and db_event.data.get("status") in ("failed", "error"):
                        status_val = "failed"
                    await realtime_publisher.publish(
                        db_event.trace_id,
                        TraceCompletedMessage(
                            trace_id=db_event.trace_id,
                            status=status_val,
                            end_time=db_event.timestamp,
                        ),
                    )
        except Exception as e:
            logger.warning(f"Failed to publish realtime batch notifications: {e}")

        # Build responses
        responses = []
        for db_event, event in zip(db_events, events):
            responses.append(
                EventResponse(
                    event_id=db_event.event_id,
                    trace_id=db_event.trace_id,
                    event_type=event.event_type,
                    timestamp=db_event.timestamp,
                    status="received",
                )
            )

        return responses

    async def get_events_by_trace(
        self,
        trace_id: str,
        db: AsyncSession,
    ) -> List[dict]:
        """Get all events for a specific trace.

        Args:
            trace_id: Trace ID to filter by.
            db: Database session.

        Returns:
            List of events for the trace.
        """
        repo = EventRepository(db)
        db_events = await repo.get_by_trace_id(trace_id)

        return [
            {
                "event_id": e.event_id,
                "trace_id": e.trace_id,
                "parent_event_id": e.parent_event_id,
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "data": e.data,
                "metadata": e.metadata_,
            }
            for e in db_events
        ]


# Singleton instance
event_service = EventService()

