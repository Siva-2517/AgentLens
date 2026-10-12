"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, events, projects, traces, websocket

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(events.router)
api_router.include_router(traces.router)
api_router.include_router(websocket.router)
