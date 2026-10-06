"""Database repositories for data access."""

import logging
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import EventModel, FailureEmbeddingModel, TraceModel
from app.models.event import EventCreate
from app.models.trace import TraceCreate

logger = logging.getLogger(__name__)


class TraceRepository:
    """Repository for trace database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository.

        Args:
            session: Database session.
        """
        self.session = session

    async def create(
        self,
        trace: TraceCreate,
        project_name: Optional[str] = None,
    ) -> TraceModel:
        """Create a new trace.

        Args:
            trace: Trace data to create.
            project_name: Optional project name.

        Returns:
            Created trace model.
        """
        existing = await self.get_by_trace_id(trace.trace_id)
        if existing:
            existing.name = trace.name
            if project_name:
                existing.project_name = project_name
            if trace.end_time:
                existing.end_time = trace.end_time
            if trace.status:
                existing.status = trace.status
            if hasattr(trace, "metadata_") and isinstance(trace.metadata_, dict):
                existing.metadata_ = trace.metadata_
            elif hasattr(trace, "metadata") and isinstance(trace.metadata, dict):
                existing.metadata_ = trace.metadata
            await self.session.flush()
            await self.session.refresh(existing)
            logger.info(f"Updated trace {existing.trace_id} in database")
            return existing

        trace_meta = {}
        if hasattr(trace, "metadata_") and isinstance(trace.metadata_, dict):
            trace_meta = trace.metadata_
        elif hasattr(trace, "metadata") and isinstance(trace.metadata, dict):
            trace_meta = trace.metadata

        db_trace = TraceModel(
            trace_id=trace.trace_id,
            name=trace.name,
            project_name=project_name or getattr(trace, "project_name", None),
            start_time=trace.start_time,
            end_time=trace.end_time,
            status=trace.status,
            metadata_=trace_meta,
        )

        self.session.add(db_trace)
        await self.session.flush()
        await self.session.refresh(db_trace)

        logger.info(f"Created trace {db_trace.trace_id} in database")
        return db_trace

    async def get_by_trace_id(self, trace_id: str) -> Optional[TraceModel]:
        """Get trace by trace_id.

        Args:
            trace_id: Trace ID to find.

        Returns:
            Trace model if found, None otherwise.
        """
        stmt = select(TraceModel).where(TraceModel.trace_id == trace_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists(self, trace_id: str) -> bool:
        """Check if trace exists.

        Args:
            trace_id: Trace ID to check.

        Returns:
            True if exists, False otherwise.
        """
        trace = await self.get_by_trace_id(trace_id)
        return trace is not None

    async def get_with_events(self, trace_id: str) -> Optional[TraceModel]:
        """Get trace with its events loaded.

        Args:
            trace_id: Trace ID to find.

        Returns:
            Trace model with events if found, None otherwise.
        """
        stmt = (
            select(TraceModel)
            .options(selectinload(TraceModel.events))
            .where(TraceModel.trace_id == trace_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_traces(
        self,
        project_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[TraceModel, int]]:
        """List traces with event count ordered by start_time descending.

        Args:
            project_name: Optional project name to filter by.
            limit: Maximum number of traces to return.
            offset: Offset for pagination.

        Returns:
            List of (TraceModel, event_count) tuples.
        """
        stmt = (
            select(TraceModel, func.count(EventModel.id).label("event_count"))
            .outerjoin(EventModel, TraceModel.trace_id == EventModel.trace_id)
            .group_by(TraceModel.id)
            .order_by(TraceModel.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
        if project_name:
            stmt = stmt.where(TraceModel.project_name == project_name)

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


class EventRepository:
    """Repository for event database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository.

        Args:
            session: Database session.
        """
        self.session = session

    async def create(
        self,
        event: EventCreate,
        project_name: Optional[str] = None,
    ) -> EventModel:
        """Create a new event.

        Args:
            event: Event data to create.
            project_name: Optional project name (for logging).

        Returns:
            Created event model.
        """
        db_event = EventModel(
            event_id=event.event_id,
            trace_id=event.trace_id,
            parent_event_id=event.parent_event_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            data=event.data,
            metadata_=event.metadata,
        )

        self.session.add(db_event)
        await self.session.flush()
        await self.session.refresh(db_event)

        logger.info(
            f"Created event {db_event.event_id} for trace {db_event.trace_id} in database"
        )
        return db_event

    async def get_by_event_id(self, event_id: str) -> Optional[EventModel]:
        """Get event by event_id.

        Args:
            event_id: Event ID to find.

        Returns:
            Event model if found, None otherwise.
        """
        stmt = select(EventModel).where(EventModel.event_id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_trace_id(self, trace_id: str) -> List[EventModel]:
        """Get all events for a trace.

        Args:
            trace_id: Trace ID to filter by.

        Returns:
            List of event models.
        """
        stmt = (
            select(EventModel)
            .where(EventModel.trace_id == trace_id)
            .order_by(EventModel.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists(self, event_id: str) -> bool:
        """Check if event exists.

        Args:
            event_id: Event ID to check.

        Returns:
            True if exists, False otherwise.
        """
        event = await self.get_by_event_id(event_id)
        return event is not None

    async def create_batch(
        self,
        events: List[EventCreate],
        project_name: Optional[str] = None,
    ) -> List[EventModel]:
        """Create multiple events in batch.

        Args:
            events: List of events to create.
            project_name: Optional project name (for logging).

        Returns:
            List of created event models.
        """
        db_events = []

        for event in events:
            db_event = EventModel(
                event_id=event.event_id,
                trace_id=event.trace_id,
                parent_event_id=event.parent_event_id,
                event_type=event.event_type.value,
                timestamp=event.timestamp,
                data=event.data,
                metadata_=event.metadata,
            )
            db_events.append(db_event)

        self.session.add_all(db_events)
        await self.session.flush()

        # Refresh all objects
        for db_event in db_events:
            await self.session.refresh(db_event)

        logger.info(f"Created batch of {len(db_events)} events in database")
        return db_events


class FailureEmbeddingRepository:
    """Repository for failure embeddings database operations (Phase 15)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        trace_id: str,
        finding_id: str,
        rule: str,
        category: str,
        severity: str,
        searchable_text: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> FailureEmbeddingModel:
        """Insert or update a failure embedding."""
        stmt = select(FailureEmbeddingModel).where(
            FailureEmbeddingModel.trace_id == trace_id,
            FailureEmbeddingModel.finding_id == finding_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.rule = rule
            existing.category = category
            existing.severity = severity
            existing.searchable_text = searchable_text
            existing.embedding = embedding
            existing.metadata_ = metadata
            await self.session.flush()
            await self.session.refresh(existing)
            logger.info(f"Updated failure embedding for {trace_id}:{finding_id}")
            return existing

        model = FailureEmbeddingModel(
            trace_id=trace_id,
            finding_id=finding_id,
            rule=rule,
            category=category,
            severity=severity,
            searchable_text=searchable_text,
            embedding=embedding,
            metadata_=metadata,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        logger.info(f"Created failure embedding for {trace_id}:{finding_id}")
        return model

    async def get_by_trace_and_finding(
        self, trace_id: str, finding_id: str
    ) -> Optional[FailureEmbeddingModel]:
        """Get failure embedding by trace_id and finding_id."""
        stmt = select(FailureEmbeddingModel).where(
            FailureEmbeddingModel.trace_id == trace_id,
            FailureEmbeddingModel.finding_id == finding_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_trace_id(self, trace_id: str) -> list[FailureEmbeddingModel]:
        """Get all failure embeddings for a trace."""
        stmt = (
            select(FailureEmbeddingModel)
            .where(FailureEmbeddingModel.trace_id == trace_id)
            .order_by(FailureEmbeddingModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_similar(
        self,
        query_vector: list[float],
        limit: int = 10,
        severity: Optional[str] = None,
        rule: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> list[tuple[FailureEmbeddingModel, float, str, Optional[str]]]:
        """Search similar failure embeddings using cosine distance.

        Returns:
            List of tuples: (FailureEmbeddingModel, similarity_score, trace_name, project_name)
        """
        # Determine dialect (PostgreSQL vs SQLite for in-memory tests)
        bind = self.session.bind
        dialect_name = bind.dialect.name if bind else "postgresql"

        if dialect_name == "postgresql":
            distance_expr = FailureEmbeddingModel.embedding.cosine_distance(query_vector).label("distance")
            stmt = (
                select(
                    FailureEmbeddingModel,
                    distance_expr,
                    TraceModel.name.label("trace_name"),
                    TraceModel.project_name.label("project_name"),
                )
                .join(TraceModel, FailureEmbeddingModel.trace_id == TraceModel.trace_id)
            )

            if severity:
                stmt = stmt.where(FailureEmbeddingModel.severity == severity.lower())
            if rule:
                stmt = stmt.where(FailureEmbeddingModel.rule == rule)
            if project_name:
                stmt = stmt.where(TraceModel.project_name == project_name)

            stmt = stmt.order_by(
                distance_expr.asc(),
                FailureEmbeddingModel.created_at.desc(),
                FailureEmbeddingModel.trace_id.asc(),
                FailureEmbeddingModel.finding_id.asc(),
            ).limit(limit)

            result = await self.session.execute(stmt)
            rows = result.all()
            return [
                (
                    row[0],
                    round(max(0.0, min(1.0, 1.0 - float(row[1]))), 4),
                    row[2],
                    row[3],
                )
                for row in rows
            ]
        else:
            # SQLite fallback for test environments: compute cosine similarity in Python
            import math

            stmt = (
                select(
                    FailureEmbeddingModel,
                    TraceModel.name.label("trace_name"),
                    TraceModel.project_name.label("project_name"),
                )
                .join(TraceModel, FailureEmbeddingModel.trace_id == TraceModel.trace_id)
            )

            if severity:
                stmt = stmt.where(FailureEmbeddingModel.severity == severity.lower())
            if rule:
                stmt = stmt.where(FailureEmbeddingModel.rule == rule)
            if project_name:
                stmt = stmt.where(TraceModel.project_name == project_name)

            result = await self.session.execute(stmt)
            candidates = result.all()

            def _cosine_sim(v1: list[float], v2: list[float]) -> float:
                dot = sum(a * b for a, b in zip(v1, v2))
                norm1 = math.sqrt(sum(a * a for a in v1))
                norm2 = math.sqrt(sum(b * b for b in v2))
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                return max(0.0, min(1.0, dot / (norm1 * norm2)))

            scored = []
            for emb_model, t_name, p_name in candidates:
                sim = _cosine_sim(query_vector, emb_model.embedding)
                scored.append((emb_model, round(sim, 4), t_name, p_name))

            scored.sort(
                key=lambda x: (
                    -x[1],
                    -x[0].created_at.timestamp() if x[0].created_at else 0,
                    x[0].trace_id,
                    x[0].finding_id,
                )
            )
            return scored[:limit]

