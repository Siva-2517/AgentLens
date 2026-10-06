"""Trace management service."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import TraceRepository
from app.models.trace import TraceCreate, TraceResponse, TraceSummary

logger = logging.getLogger(__name__)


class TraceService:
    """Service for handling trace management."""

    async def create_trace(
        self,
        trace: TraceCreate,
        project_name: Optional[str],
        db: AsyncSession,
    ) -> TraceResponse:
        """Create a new trace.

        Args:
            trace: Trace to create.
            project_name: Optional project name from header.
            db: Database session.

        Returns:
            Trace response.
        """
        repo = TraceRepository(db)

        # Create trace in database
        db_trace = await repo.create(trace, project_name)

        logger.info(
            f"Created trace {trace.trace_id} ({trace.name}, project: {project_name})"
        )

        # Publish real-time trace lifecycle event (failure-resilient)
        try:
            from app.models.realtime import TraceCompletedMessage, TraceStartedMessage
            from app.services.realtime_publisher import realtime_publisher

            if db_trace.status in ("completed", "failed") or db_trace.end_time is not None:
                duration_ms = None
                if db_trace.start_time and db_trace.end_time:
                    duration_ms = round(
                        (db_trace.end_time - db_trace.start_time).total_seconds() * 1000, 2
                    )
                await realtime_publisher.publish(
                    db_trace.trace_id,
                    TraceCompletedMessage(
                        trace_id=db_trace.trace_id,
                        status=db_trace.status,
                        end_time=db_trace.end_time,
                        duration_ms=duration_ms,
                    ),
                )
            else:
                await realtime_publisher.publish(
                    db_trace.trace_id,
                    TraceStartedMessage(
                        trace_id=db_trace.trace_id,
                        name=db_trace.name,
                        project_name=db_trace.project_name,
                        start_time=db_trace.start_time,
                        status=db_trace.status,
                    ),
                )
        except Exception as e:
            logger.warning(
                f"Failed to publish realtime lifecycle event for trace {db_trace.trace_id}: {e}"
            )

        return TraceResponse(
            trace_id=db_trace.trace_id,
            name=db_trace.name,
            start_time=db_trace.start_time,
            status=db_trace.status,
        )

    async def get_trace_by_id(
        self,
        trace_id: str,
        db: AsyncSession,
    ) -> Optional[dict]:
        """Get a trace by ID.

        Args:
            trace_id: Trace ID to find.
            db: Database session.

        Returns:
            Trace data if found, None otherwise.
        """
        repo = TraceRepository(db)
        db_trace = await repo.get_by_trace_id(trace_id)

        if not db_trace:
            return None

        return {
            "trace_id": db_trace.trace_id,
            "name": db_trace.name,
            "project_name": db_trace.project_name,
            "start_time": db_trace.start_time,
            "end_time": db_trace.end_time,
            "status": db_trace.status,
            "metadata": db_trace.metadata_,
        }

    async def list_traces(
        self,
        project_name: Optional[str],
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TraceSummary]:
        """List traces with event counts and durations.

        Args:
            project_name: Optional project name filter.
            db: Database session.
            limit: Maximum number of traces to return.
            offset: Offset for pagination.

        Returns:
            List of trace summaries.
        """
        repo = TraceRepository(db)
        records = await repo.list_traces(
            project_name=project_name,
            limit=limit,
            offset=offset,
        )

        summaries = []
        for trace_model, event_count in records:
            duration_ms = None
            if trace_model.start_time and trace_model.end_time:
                duration_ms = round(
                    (trace_model.end_time - trace_model.start_time).total_seconds() * 1000,
                    2,
                )

            summaries.append(
                TraceSummary(
                    trace_id=trace_model.trace_id,
                    name=trace_model.name,
                    project_name=trace_model.project_name,
                    status=trace_model.status,
                    start_time=trace_model.start_time,
                    end_time=trace_model.end_time,
                    duration_ms=duration_ms,
                    event_count=event_count,
                )
            )

        return summaries


# Singleton instance
trace_service = TraceService()

