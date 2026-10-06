"""FastAPI application entry point (Phase 17 Security Hardened)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.config import settings
from app.db import close_db, init_db
from app.services.redaction import mask_connection_string

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting AgentLens API...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {mask_connection_string(str(e))}")
        # Don't fail startup - allow API to run even if DB is unavailable
        logger.warning("API starting without database connection")

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

# Parse configurable CORS origins from environment
configured_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not configured_origins:
    configured_origins = ["http://localhost:5173", "http://localhost:3000"]

allow_credentials = "*" not in configured_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add standard HTTP security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and mask sensitive details in responses."""
    logger.error(
        f"Unhandled server error on {request.method} {request.url.path}: {mask_connection_string(str(exc))}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred."},
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


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
