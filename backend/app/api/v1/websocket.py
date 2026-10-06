"""WebSocket API endpoint for real-time agent trace monitoring (Phase 17 Security Hardened)."""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.repositories import TraceRepository
from app.services.auth import auth_service
from app.services.realtime_service import realtime_service
from app.services.redaction import mask_connection_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["realtime"])

TRACE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


@router.websocket("/ws/traces/{trace_id}")
async def trace_websocket_endpoint(
    websocket: WebSocket,
    trace_id: str,
    token: Optional[str] = Query(None, description="API key token for browser WebSocket"),
    api_key: Optional[str] = Query(None, description="Alternative API key parameter"),
    db: AsyncSession = Depends(get_db),
):
    """Real-time WebSocket endpoint streaming execution events for a specific trace.

    Authentication Tradeoff Note:
    Standard browser WebSocket APIs (`new WebSocket(url)`) do not allow custom HTTP
    headers (such as `Authorization: Bearer <key>`). Therefore, the API key is passed
    via query parameter `token` or `api_key` (or header when connecting via SDK/Node clients),
    and strictly validated using constant-time comparison against the API key store before
    accepting the connection.

    Lifecycle:
    1. Validates trace_id format and length.
    2. Validates API key using constant-time verification.
    3. Validates trace existence in Neon PostgreSQL.
    4. Accepts WebSocket connection.
    5. Subscribes to Redis channel `agentlens:trace:{trace_id}`.
    6. Streams real-time events (`event_created`, `trace_started`, `trace_completed`).
    7. Gracefully handles client disconnects, Redis reconnects, and server shutdowns.
    """
    # 1. Validate trace_id format to prevent channel injection or malformed strings
    if not trace_id or not TRACE_ID_REGEX.match(trace_id):
        logger.warning(f"Rejected WebSocket connection for malformed trace ID: '{trace_id[:32]}'")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid trace ID format",
        )
        return

    # 2. Authenticate connection
    auth_token = token or api_key
    if not auth_token:
        # Check header if client supports custom headers
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    if not auth_token or not auth_service.validate_api_key(auth_token.strip()):
        logger.warning(f"Rejected unauthenticated WebSocket connection for trace '{trace_id}'")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Unauthorized: Invalid or missing API key",
        )
        return

    # 3. Verify trace exists in database
    try:
        repo = TraceRepository(db)
        trace_exists = await repo.exists(trace_id)
        if not trace_exists:
            logger.warning(f"Rejected WebSocket connection for non-existent trace '{trace_id}'")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Trace '{trace_id}' not found",
            )
            return
    except Exception as e:
        logger.error(f"Database error verifying trace for WebSocket '{trace_id}': {mask_connection_string(str(e))}")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Internal error",
        )
        return

    # 4. Accept connection and register subscription
    await websocket.accept()
    await realtime_service.connect(websocket, trace_id)

    # 5. Message loop
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly for trace '{trace_id}'")
    except Exception as e:
        logger.debug(f"WebSocket connection exception for trace '{trace_id}': {e}")
    finally:
        await realtime_service.disconnect(websocket, trace_id)
