"""Event ingestion API endpoints (Phase 19B Security Hardened)."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    IngestionPrincipal,
    get_ingestion_principal,
    get_project_name,
)
from app.config import settings
from app.db import get_db
from app.db.repositories import TraceRepository
from app.models.event import EventCreate, EventResponse
from app.models.trace import TraceCreate
from app.services.event_service import event_service
from app.services.redaction import mask_connection_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


async def _enforce_trace_project_binding(
    trace_ids: set[str],
    ingestion: IngestionPrincipal,
    db: AsyncSession,
    sample_timestamp=None,
    project_name: Optional[str] = None,
) -> None:
    """Ensure all traces belong to the ingestion principal's project.

    If a trace does not exist, auto-provisions it bound strictly to the API key's project.
    If a trace exists and belongs to a different project, raises 403 Forbidden.
    """
    trace_repo = TraceRepository(db)
    for tid in trace_ids:
        trace = await trace_repo.get_by_trace_id(tid)
        if trace:
            if trace.project_id != ingestion.project_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Trace '{tid}' belongs to another project and cannot accept events from this key",
                )
        else:
            # Auto-provision trace bound strictly to resolved key's project
            await trace_repo.create(
                trace=TraceCreate(
                    trace_id=tid,
                    name="telemetry-session",
                    start_time=sample_timestamp,
                    status="running",
                ),
                project_name=project_name or ingestion.project_name,
                project_id=ingestion.project_id,
            )


@router.post(
    "/events",
    response_model=List[EventResponse],
    status_code=status.HTTP_201_CREATED,
)
async def ingest_events(
    events: List[EventCreate],
    ingestion: IngestionPrincipal = Depends(get_ingestion_principal),
    project_name: Optional[str] = Depends(get_project_name),
    db: AsyncSession = Depends(get_db),
) -> List[EventResponse]:
    """Ingest a batch of events bound strictly to the API key's project."""
    if not events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event list cannot be empty",
        )

    if len(events) > settings.max_event_batch_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size exceeds maximum limit of {settings.max_event_batch_size} events",
        )

    # Validate and bind project ownership
    trace_ids = {e.trace_id for e in events}
    await _enforce_trace_project_binding(
        trace_ids=trace_ids,
        ingestion=ingestion,
        db=db,
        sample_timestamp=events[0].timestamp,
        project_name=project_name,
    )

    try:
        resolved_project = project_name or ingestion.project_name
        responses = await event_service.ingest_events_batch(events, resolved_project, db)
        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ingest events: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest events due to an internal error.",
        )


@router.post(
    "/events/single",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_single_event(
    event: EventCreate,
    ingestion: IngestionPrincipal = Depends(get_ingestion_principal),
    project_name: Optional[str] = Depends(get_project_name),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """Ingest a single event bound strictly to the API key's project."""
    await _enforce_trace_project_binding(
        trace_ids={event.trace_id},
        ingestion=ingestion,
        db=db,
        sample_timestamp=event.timestamp,
        project_name=project_name,
    )

    try:
        resolved_project = project_name or ingestion.project_name
        response = await event_service.ingest_event(event, resolved_project, db)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ingest event: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest event due to an internal error.",
        )
