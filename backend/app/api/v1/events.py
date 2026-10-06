"""Event ingestion API endpoints (Phase 17 Security Hardened)."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_project_name, verify_api_key
from app.config import settings
from app.db import get_db
from app.models.event import EventCreate, EventResponse
from app.services.event_service import event_service
from app.services.redaction import mask_connection_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.post(
    "/events",
    response_model=List[EventResponse],
    status_code=status.HTTP_201_CREATED,
)
async def ingest_events(
    events: List[EventCreate],
    api_key: str = Depends(verify_api_key),
    project_name: Optional[str] = Depends(get_project_name),
    db: AsyncSession = Depends(get_db),
) -> List[EventResponse]:
    """Ingest a batch of events from AgentLens SDK with bounded limits.

    Args:
        events: List of events to ingest.
        api_key: Validated API key from dependency.
        project_name: Optional project name from header.
        db: Database session.

    Returns:
        List of event responses with status.

    Raises:
        HTTPException: If validation or database operation fails.
    """
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

    try:
        responses = await event_service.ingest_events_batch(events, project_name, db)
        return responses

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
    api_key: str = Depends(verify_api_key),
    project_name: Optional[str] = Depends(get_project_name),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """Ingest a single event from AgentLens SDK.

    Args:
        event: Event to ingest.
        api_key: Validated API key from dependency.
        project_name: Optional project name from header.
        db: Database session.

    Returns:
        Event response with status.

    Raises:
        HTTPException: If validation or database operation fails.
    """
    try:
        response = await event_service.ingest_event(event, project_name, db)
        return response

    except Exception as e:
        logger.error(f"Failed to ingest event: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest event due to an internal error.",
        )
