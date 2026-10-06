import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_project_name, verify_api_key
from app.db import get_db
from app.models.comparison import TraceComparisonResult
from app.models.execution_graph import ExecutionGraph
from app.models.failure_search import HistoricalSearchResponse, TraceIndexingResponse
from app.models.finding import FindingsResponse
from app.models.investigation import InvestigationResult
from app.models.reconstructed_trace import ReconstructedTrace
from app.models.trace import TraceCreate, TraceResponse, TraceSummary
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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[TraceSummary]:
    """Retrieve a list of execution traces.

    Args:
        project: Optional project filter query param.
        limit: Maximum number of traces to return (default 100).
        offset: Pagination offset.
        header_project: Optional project name from header.
        api_key: Validated API key.
        db: Database session.

    Returns:
        List of lightweight trace summaries.
    """
    try:
        project_name = project or header_project
        bounded_limit = max(1, min(500, limit))
        bounded_offset = max(0, offset)
        return await trace_service.list_traces(
            project_name=project_name,
            db=db,
            limit=bounded_limit,
            offset=bounded_offset,
        )
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
    api_key: str = Depends(verify_api_key),
    project_name: Optional[str] = Depends(get_project_name),
    db: AsyncSession = Depends(get_db),
) -> TraceResponse:
    """Create a new trace.

    Args:
        trace: Trace to create.
        api_key: Validated API key from dependency.
        project_name: Optional project name from header.
        db: Database session.

    Returns:
        Trace response.

    Raises:
        HTTPException: If validation or database operation fails.
    """
    try:
        response = await trace_service.create_trace(trace, project_name, db)
        return response

    except Exception as e:
        logger.error(f"Failed to create trace: {mask_connection_string(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create trace due to an internal error.",
        )


@router.get(
    "/traces/compare",
    response_model=TraceComparisonResult,
    status_code=status.HTTP_200_OK,
)
async def compare_traces(
    trace_a: str,
    trace_b: str,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> TraceComparisonResult:
    """Compare two reconstructed execution traces side-by-side.

    Provides deterministic comparison of execution metrics, sequence replay alignment,
    and failure/anomaly findings.

    Args:
        trace_a: First trace identifier.
        trace_b: Second trace identifier.
        api_key: Validated API key from dependency.
        db: Database session.

    Returns:
        Structured TraceComparisonResult.

    Raises:
        HTTPException: 400 if parameters invalid, 404 if trace missing, 500 on internal failure.
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

    if len(trace_a) > 256 or len(trace_b) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trace identifiers must not exceed 256 characters",
        )

    try:
        return await trace_comparison_service.compare_traces(trace_a, trace_b, db)
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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ReconstructedTrace:
    """Retrieve and reconstruct an execution trace with its events.

    Args:
        trace_id: Unique identifier of the trace.
        api_key: Validated API key from dependency.
        db: Database session.

    Returns:
        Reconstructed execution trace with ordered events and metadata.

    Raises:
        HTTPException: 404 if trace not found, 500 on database error.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ExecutionGraph:
    """Retrieve the execution graph representation for a trace.

    Transforms the reconstructed trace into nodes and directed edges
    representing the agent's execution flow.

    Args:
        trace_id: Unique identifier of the trace.
        api_key: Validated API key from dependency.
        db: Database session.

    Returns:
        ExecutionGraph with nodes, edges, and counts.

    Raises:
        HTTPException: 404 if trace not found, 500 on database error.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> FindingsResponse:
    """Retrieve deterministic failure and anomaly findings for a trace.

    Reconstructs the trace and evaluates deterministic detection rules
    for explicit errors, missing responses, execution loops, unresolved
    retries, repeated tool calls, and lifecycle issues.

    Args:
        trace_id: Unique identifier of the trace.
        api_key: Validated API key from dependency.
        db: Database session.

    Returns:
        FindingsResponse containing total count and ordered findings.

    Raises:
        HTTPException: 404 if trace not found, 500 on internal failure.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> InvestigationResult:
    """Perform AI-powered root-cause investigation for a trace.

    Analyzes reconstructed execution trace, execution graph, and Phase 11
    deterministic findings to determine the earliest failure, root cause,
    downstream effects, and recommended engineering actions.

    Args:
        trace_id: Unique identifier of the trace.
        api_key: Validated API key from dependency.
        db: Database session.

    Returns:
        Structured InvestigationResult.

    Raises:
        HTTPException: 404 if trace not found, 422 if validation fails, 500 on internal failure.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> TraceIndexingResponse:
    """Index deterministic failure findings for a trace into pgvector store.

    Reconstructs the trace, runs failure detection, synthesizes sanitized contextual
    searchable text, generates vector embeddings, and persists them for semantic search.

    Args:
        trace_id: Unique identifier of the trace.
        api_key: Validated API key.
        db: Database session.

    Returns:
        TraceIndexingResponse with count of indexed findings.

    Raises:
        HTTPException: 404 if trace not found, 400 on invalid input, 500 on internal failure.
    """
    clean_id = (trace_id or "").strip()
    if not clean_id or len(clean_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trace_id parameter",
        )

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
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> HistoricalSearchResponse:
    """Search historical failures using pgvector semantic similarity.

    Args:
        q: Natural-language query string describing the failure condition.
        limit: Maximum results to return (1-50, default 10).
        severity: Optional severity filter (critical, error, warning, info).
        rule: Optional rule code filter.
        project: Optional project filter.
        api_key: Validated API key.
        db: Database session.

    Returns:
        HistoricalSearchResponse with ranked matching failures and similarity scores.

    Raises:
        HTTPException: 400 on empty query, 500 on internal error.
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
        return await failure_search_service.search_failures(
            query=clean_q,
            db=db,
            limit=bounded_limit,
            severity=severity,
            rule=rule,
            project_name=project,
        )
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


