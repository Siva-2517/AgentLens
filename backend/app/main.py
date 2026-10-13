"""FastAPI application entry point (Phase 20C Reliability & Monitoring Hardened)."""

import asyncio
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.v1 import api_router
from app.config import settings
from app.db import close_db, init_db
from app.services.logging_config import (
    configure_logging,
    get_correlation_id,
    set_correlation_id,
)
from app.services.metrics import metrics_collector
from app.services.redaction import mask_connection_string

# Initialize structured logging and redaction filter
configure_logging()
logger = logging.getLogger(__name__)

REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events with bounded resource disposal.
    """
    # Startup
    logger.info("Starting AgentLens API...")
    env_str = getattr(settings, "environment", "development").lower()
    is_prod = env_str in ("production", "prod")
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {mask_connection_string(str(e))}")
        if is_prod:
            raise RuntimeError(f"Database initialization failed in production: {mask_connection_string(str(e))}")
        logger.warning("API starting without database connection (development mode)")

    yield

    # Shutdown
    logger.info("Shutting down AgentLens API...")
    try:
        from app.services.realtime_publisher import realtime_publisher
        from app.services.realtime_service import realtime_service

        await realtime_service.close_all()
        await realtime_publisher.close()
    except Exception as e:
        logger.warning(f"Error closing realtime services: {e}")
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title="AgentLens API",
    description="AI-powered observability platform for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Parse configurable CORS origins and regex from environment
configured_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not configured_origins:
    configured_origins = ["http://localhost:5173", "http://localhost:3000"]

allow_credentials = "*" not in configured_origins

cors_kwargs: dict = {
    "allow_origins": configured_origins,
    "allow_credentials": allow_credentials,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["*"],
}
if getattr(settings, "cors_origin_regex", None):
    cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex

app.add_middleware(
    CORSMiddleware,
    **cors_kwargs,
)


@app.middleware("http")
async def operational_context_and_metrics_middleware(request: Request, call_next):
    """Extract or generate correlation ID, track request latency, and record operational metrics."""
    # 1. Correlation / Request ID extraction or generation
    req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
    if not req_id or not REQUEST_ID_REGEX.match(req_id):
        req_id = f"req_{uuid.uuid4().hex[:16]}"
    set_correlation_id(req_id)

    # 2. Timing and execution
    start_time = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        duration = time.perf_counter() - start_time
        metrics_collector.record_http_request(request.method, request.url.path, 500, duration)
        raise exc

    duration = time.perf_counter() - start_time
    metrics_collector.record_http_request(request.method, request.url.path, status_code, duration)

    # 3. Response headers
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Correlation-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions, log with correlation ID, and mask sensitive details."""
    logger.error(
        f"Unhandled server error on {request.method} {request.url.path} (request_id={get_correlation_id()}): "
        f"{mask_connection_string(str(exc))}"
    )
    headers = {"X-Request-ID": get_correlation_id()}
    origin = request.headers.get("origin")
    if origin:
        regex_match = bool(settings.cors_origin_regex and re.match(settings.cors_origin_regex, origin))
        if origin in configured_origins or regex_match:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred."},
        headers=headers,
    )


# Include API router
app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "AgentLens API",
        "version": "0.1.0",
        "status": "ready",
    }


@app.get("/health/live", tags=["monitoring"])
@app.get("/api/v1/health/live", tags=["monitoring"])
async def liveness() -> dict[str, str]:
    """Process liveness probe."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["monitoring"])
@app.get("/health", tags=["monitoring"])
@app.get("/api/v1/health/ready", tags=["monitoring"])
@app.get("/api/v1/health", tags=["monitoring"])
async def readiness() -> JSONResponse:
    """Readiness probe distinguishing primary datastore from pub/sub cache status with bounded timeouts."""
    # 1. Database check with bounded 2s timeout
    db_connected = False
    try:
        from app.db.session import engine
        from sqlalchemy import text

        async def _check_db():
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1;"))

        await asyncio.wait_for(_check_db(), timeout=2.0)
        db_status = "connected"
        db_connected = True
    except Exception:
        db_status = "disconnected"

    # 2. Redis check with bounded 2s timeout
    redis_connected = False
    try:
        from app.services.realtime_publisher import realtime_publisher

        async def _check_redis():
            r = await realtime_publisher._get_redis()
            if r is not None:
                await r.ping()
                return True
            return False

        is_pong = await asyncio.wait_for(_check_redis(), timeout=3.0)
        if is_pong:
            redis_status = "connected"
            redis_connected = True
        else:
            redis_status = "degraded (local fallback active)"
    except Exception:
        redis_status = "degraded (local fallback active)"

    # 3. Determine readiness semantics based on deployment topology and redis_required
    is_multi_instance = (getattr(settings, "deployment_topology", "single-instance") or "").strip().lower() == "multi-instance"
    redis_mandatory = getattr(settings, "redis_required", False) or is_multi_instance

    if not db_connected:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "ready": False,
                "topology": getattr(settings, "deployment_topology", "single-instance"),
                "services": {
                    "database": db_status,
                    "redis": redis_status,
                },
                "error": "Primary database is disconnected",
            },
        )

    if not redis_connected:
        if redis_mandatory:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "ready": False,
                    "topology": getattr(settings, "deployment_topology", "single-instance"),
                    "services": {
                        "database": db_status,
                        "redis": redis_status,
                    },
                    "error": "Redis is required for multi-instance deployment but is unavailable",
                },
            )
        # Single-instance deployment: operational in degraded mode via local in-memory fan-out
        return JSONResponse(
            status_code=200,
            content={
                "status": "degraded",
                "ready": True,
                "topology": getattr(settings, "deployment_topology", "single-instance"),
                "services": {
                    "database": db_status,
                    "redis": redis_status,
                },
                "warning": "Redis unavailable; degraded in-memory pub/sub active for single instance",
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "ready": True,
            "topology": getattr(settings, "deployment_topology", "single-instance"),
            "services": {
                "database": db_status,
                "redis": redis_status,
            },
        },
    )


def check_metrics_access(request: Request) -> None:
    """Validate optional metrics authentication token and enabled flag (Phase 20D)."""
    if not getattr(settings, "metrics_enabled", True):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Metrics endpoint is disabled")
    token_required = getattr(settings, "metrics_auth_token", None)
    if token_required:
        auth_header = request.headers.get("Authorization", "")
        query_token = request.query_params.get("token")
        bearer_valid = auth_header.startswith("Bearer ") and auth_header[7:].strip() == token_required
        if not (bearer_valid or query_token == token_required):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Unauthorized metrics access")


@app.get("/metrics", tags=["monitoring"], response_class=PlainTextResponse)
async def metrics_prometheus(request: Request) -> str:
    """OpenMetrics / Prometheus exposition endpoint for low-cardinality operational measurements."""
    check_metrics_access(request)
    return metrics_collector.get_metrics_prometheus()


@app.get("/api/v1/metrics", tags=["monitoring"])
async def metrics_json(request: Request) -> dict:
    """Structured JSON operational metrics endpoint."""
    check_metrics_access(request)
    return metrics_collector.get_metrics_json()
