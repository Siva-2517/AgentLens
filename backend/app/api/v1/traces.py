"""Traces API endpoints (Phase 19C Multi-Tenant Authorization Hardened)."""

import logging
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    DEFAULT_PROJECT_ID,
    IngestionPrincipal,
    UserPrincipal,
    get_ingestion_principal,
    get_project_name,
    verify_dashboard_access,
)
from app.db import get_db
from app.db.models import ProjectModel
from app.models.comparison import TraceComparisonResult
from app.models.execution_graph import ExecutionGraph
from app.models.failure_search import HistoricalSearchResponse, TraceIndexingResponse
from app.models.finding import FindingsResponse
from app.models.investigation import InvestigationResult
from app.models.reconstructed_trace import ReconstructedTrace
from app.models.trace import TraceCreate, TraceResponse, TraceSummary, TraceUpdate
from app.services.authorization_service import (
    get_user_accessible_project_ids,
    verify_trace_access,
)
from app.services.execution_graph_service import execution_graph_service
from app.services.failure_detection_service import failure_detection_service
from app.services.failure_search_service import failure_search_service
from app.services.investigation_service import (
    InvestigationValidationError,
    ai_investigation_service,
)
from app.services.redaction import mask_connection_string
from app.services.trace_comparison_service import trace_comparison_service
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)
from app.services.trace_service import trace_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["traces"])


@router.get(
    "/traces",
    response_model=list[TraceSummary],
    status_code=status.HTTP_200_OK,
)
async def list_traces(
    project: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    header_project: Optional[str] = Depends(get_project_name),
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> list[TraceSummary]:
    """Retrieve a list of execution traces scoped strictly to caller's tenant authorization.

    Args:
        project: Optional project filter query param (id or slug/name).
        limit: Maximum number of traces to return (default 100).
        offset: Pagination offset.
        header_project: Optional project name from header.
        principal: Validated dashboard user principal or legacy test key.
        db: Database session.

    Returns:
        List of lightweight trace summaries.
    """
    try:
        accessible_project_ids = await get_user_accessible_project_ids(principal, db)
        if not accessible_project_ids:
            return []

        bounded_limit = max(1, min(500, limit))
        bounded_offset = max(0, offset)

        project_filter = (project or header_project or "").strip()
        target_project_id: Optional[str] = None
        filter_project_name: Optional[str] = None

        if project_filter:
            if project_filter in accessible_project_ids:
                target_project_id = project_filter
            else:
                # Query project by ID, slug, or name
                stmt = select(ProjectModel).where(
                    (ProjectModel.id == project_filter)
                    | (ProjectModel.slug == project_filter.lower())
                    | (ProjectModel.name == project_filter)
                )
                res = await db.execute(stmt)
                found_proj = res.scalar_one_or_none()
                if found_proj:
                    if found_proj.id in accessible_project_ids or (
                        isinstance(principal, str)
                        and (
                            found_proj.id == DEFAULT_PROJECT_ID
                            or found_proj.organization_id == DEFAULT_PROJECT_ID
                        )
                    ):
                        target_project_id = found_proj.id
                    else:
                        # Anti-IDOR: Return 404 for unauthorized tenant project
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Project '{project_filter}' not found",
                        )
                else:
                    filter_project_name = project_filter

        return await trace_service.list_traces(
            project_name=filter_project_name,
            project_id=target_project_id,
            project_ids=accessible_project_ids if not target_project_id else None,
            db=db,
            limit=bounded_limit,
            offset=bounded_offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list traces: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list traces due to an internal error.",
        )


@router.post(
    "/traces",
    response_model=TraceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trace(
    trace: TraceCreate,
    ingestion: IngestionPrincipal = Depends(get_ingestion_principal),
    project_name: Optional[str] = Depends(get_project_name),
    db: AsyncSession = Depends(get_db),
) -> TraceResponse:
    """Create a new trace with strict project binding.

    Binds trace strictly to the project resolved from the ingestion API key,
    ignoring any untrusted client-supplied project ownership claims.
    """
    try:
        response = await trace_service.create_trace(
            trace=trace,
            project_name=project_name or ingestion.project_name,
            db=db,
            project_id=ingestion.project_id,
        )
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Failed to create trace: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create trace due to an internal error.",
        )


@router.patch(
    "/traces/{trace_id}",
    response_model=TraceResponse,
    status_code=status.HTTP_200_OK,
)
async def update_trace(
    trace_id: str,
    update: TraceUpdate,
    ingestion: IngestionPrincipal = Depends(get_ingestion_principal),
    db: AsyncSession = Depends(get_db),
) -> TraceResponse:
    """Update a trace's status, end_time, or metadata with strict tenant isolation."""
    repo = TraceRepository(db)
    trace = await repo.get_by_trace_id(trace_id)
    if not trace or trace.project_id != ingestion.project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{trace_id}' not found",
        )

    if update.status:
        trace.status = update.status
    if update.end_time:
        trace.end_time = update.end_time
    if update.metadata:
        trace.metadata_ = {**(trace.metadata_ or {}), **update.metadata}

    await db.flush()
    await db.refresh(trace)

    # Publish realtime update
    if trace.status in ("completed", "failed") or trace.end_time is not None:
        try:
            from app.models.realtime import TraceCompletedMessage
            from app.services.realtime_publisher import realtime_publisher

            await realtime_publisher.publish(
                trace.trace_id,
                TraceCompletedMessage(
                    trace_id=trace.trace_id,
                    status=trace.status,
                    end_time=trace.end_time,
                ),
            )
        except Exception:
            pass

    return TraceResponse(
        trace_id=trace.trace_id,
        name=trace.name,
        start_time=trace.start_time,
        status=trace.status,
        project_id=trace.project_id,
    )


@router.get(
    "/traces/compare",
    response_model=TraceComparisonResult,
    status_code=status.HTTP_200_OK,
)
async def compare_traces(
    trace_a: str,
    trace_b: str,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> TraceComparisonResult:
    """Compare two reconstructed execution traces side-by-side with strict tenant isolation.

    Both traces must belong to projects the caller is explicitly authorized to view.
    If either trace is missing or unauthorized, returns 404 Not Found without leaking data.

    Args:
        trace_a: First trace identifier.
        trace_b: Second trace identifier.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        Structured TraceComparisonResult.
    """
    if not trace_a or not trace_a.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'trace_a' must not be empty",
        )
    if not trace_b or not trace_b.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'trace_b' must not be empty",
        )

    clean_a = trace_a.strip()
    clean_b = trace_b.strip()

    if len(clean_a) > 256 or len(clean_b) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trace identifiers must not exceed 256 characters",
        )

    # Server-side authorization check for BOTH traces
    await verify_trace_access(clean_a, principal, db)
    await verify_trace_access(clean_b, principal, db)

    try:
        return await trace_comparison_service.compare_traces(clean_a, clean_b, db)
    except TraceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{e.trace_id}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to compare traces: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare traces due to an internal error.",
        )


@router.get(
    "/traces/{trace_id}",
    response_model=ReconstructedTrace,
    status_code=status.HTTP_200_OK,
)
async def get_reconstructed_trace(
    trace_id: str,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> ReconstructedTrace:
    """Retrieve and reconstruct an execution trace with strict tenant isolation.

    Args:
        trace_id: Unique identifier of the trace.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        Reconstructed execution trace with ordered events and metadata.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

    # Server-side tenant authorization check
    await verify_trace_access(clean_id, principal, db)

    try:
        return await trace_reconstruction_service.reconstruct_trace(clean_id, db)
    except TraceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found",
        )
    except Exception as e:
        logger.error(f"Failed to reconstruct trace: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reconstruct trace due to an internal error.",
        )


@router.get(
    "/traces/{trace_id}/graph",
    response_model=ExecutionGraph,
    status_code=status.HTTP_200_OK,
)
async def get_execution_graph(
    trace_id: str,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> ExecutionGraph:
    """Retrieve the execution graph representation for a trace with tenant isolation.

    Args:
        trace_id: Unique identifier of the trace.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        ExecutionGraph with nodes, edges, and counts.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

    # Server-side tenant authorization check
    await verify_trace_access(clean_id, principal, db)

    try:
        return await execution_graph_service.get_execution_graph(clean_id, db)
    except TraceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found",
        )
    except Exception as e:
        logger.error(f"Failed to generate execution graph: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate execution graph due to an internal error.",
        )


@router.get(
    "/traces/{trace_id}/findings",
    response_model=FindingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_trace_findings(
    trace_id: str,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> FindingsResponse:
    """Retrieve deterministic failure findings for a trace with tenant isolation.

    Args:
        trace_id: Unique identifier of the trace.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        FindingsResponse containing total count and ordered findings.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

    # Server-side tenant authorization check
    await verify_trace_access(clean_id, principal, db)

    try:
        return await failure_detection_service.get_findings(clean_id, db)
    except TraceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found",
        )
    except Exception as e:
        logger.error(f"Failed to analyze trace findings: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze trace findings due to an internal error.",
        )


@router.get(
    "/traces/{trace_id}/investigation",
    response_model=InvestigationResult,
    status_code=status.HTTP_200_OK,
)
async def get_trace_investigation(
    trace_id: str,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> InvestigationResult:
    """Perform AI-powered root-cause investigation with strict tenant isolation.

    Args:
        trace_id: Unique identifier of the trace.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        Structured InvestigationResult.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

    # Server-side tenant authorization check
    await verify_trace_access(clean_id, principal, db)

    try:
        return await ai_investigation_service.investigate_trace(clean_id, db)
    except TraceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found",
        )
    except InvestigationValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Investigation validation error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Failed to investigate trace: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to investigate trace due to an internal error.",
        )


@router.post(
    "/traces/{trace_id}/index",
    response_model=TraceIndexingResponse,
    status_code=status.HTTP_200_OK,
)
async def index_trace_failures(
    trace_id: str,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> TraceIndexingResponse:
    """Index deterministic failure findings for a trace into pgvector store with tenant isolation.

    Args:
        trace_id: Unique identifier of the trace.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        TraceIndexingResponse with count of indexed findings.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

    # Server-side tenant authorization check
    await verify_trace_access(clean_id, principal, db)

    try:
        return await failure_search_service.index_trace_failures(clean_id, db)
    except TraceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found",
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to index trace failures: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index trace failures due to an internal error.",
        )


@router.get(
    "/failures/search",
    response_model=HistoricalSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_historical_failures(
    q: str,
    limit: int = 10,
    severity: Optional[str] = None,
    rule: Optional[str] = None,
    project: Optional[str] = None,
    principal: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
    db: AsyncSession = Depends(get_db),
) -> HistoricalSearchResponse:
    """Search historical failures using pgvector semantic similarity with complete tenant isolation.

    Vector search is strictly bounded at the database query level to projects the caller is authorized to view.

    Args:
        q: Natural-language query string describing the failure condition.
        limit: Maximum results to return (1-50, default 10).
        severity: Optional severity filter (critical, error, warning, info).
        rule: Optional rule code filter.
        project: Optional project filter.
        principal: Validated dashboard user principal.
        db: Database session.

    Returns:
        HistoricalSearchResponse with ranked matching failures.
    """
    clean_q = (q or "").strip()
    if not clean_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' must not be empty",
        )

    if len(clean_q) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' exceeds maximum length of 1000 characters",
        )

    bounded_limit = max(1, min(50, limit))

    try:
        accessible_project_ids = await get_user_accessible_project_ids(principal, db)
        if not accessible_project_ids:
            return HistoricalSearchResponse(
                query=clean_q,
                total_results=0,
                results=[],
            )

        target_project_id: Optional[str] = None
        filter_project_name: Optional[str] = None

        if project:
            clean_proj = project.strip()
            if clean_proj in accessible_project_ids:
                target_project_id = clean_proj
            else:
                stmt = select(ProjectModel).where(
                    (ProjectModel.id == clean_proj)
                    | (ProjectModel.slug == clean_proj.lower())
                    | (ProjectModel.name == clean_proj)
                )
                res = await db.execute(stmt)
                found_proj = res.scalar_one_or_none()
                if found_proj:
                    if found_proj.id in accessible_project_ids or (
                        isinstance(principal, str)
                        and (
                            found_proj.id == DEFAULT_PROJECT_ID
                            or found_proj.organization_id == DEFAULT_PROJECT_ID
                        )
                    ):
                        target_project_id = found_proj.id
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Project '{clean_proj}' not found",
                        )
                else:
                    filter_project_name = clean_proj

        return await failure_search_service.search_failures(
            query=clean_q,
            db=db,
            limit=bounded_limit,
            severity=severity,
            rule=rule,
            project_name=filter_project_name,
            project_id=target_project_id,
            project_ids=accessible_project_ids if not target_project_id else None,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to search historical failures: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search historical failures due to an internal error.",
        )
