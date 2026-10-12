"""WebSocket API endpoint for real-time agent trace monitoring (Phase 19C Security Hardened)."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Set, Union

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    DEFAULT_PROJECT_ID,
    IngestionPrincipal,
    UserPrincipal,
)
from app.config import settings
from app.db import get_db
from app.db.models import OrganizationMemberModel, ProjectModel, TraceModel
from app.db.repositories import ApiKeyRepository, ProjectRepository, TraceRepository, UserRepository
from app.services.auth import auth_service
from app.services.realtime_service import realtime_service
from app.services.redaction import mask_connection_string
from app.services.security import security_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["realtime"])

TRACE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


async def _authenticate_websocket(
    websocket: WebSocket,
    token_param: Optional[str],
    api_key_param: Optional[str],
    db: AsyncSession,
) -> Optional[Union[UserPrincipal, IngestionPrincipal, str]]:
    """Extract and validate credentials from WebSocket handshake.

    Supports:
    1. HttpOnly Cookie: `agentlens_access_token` (browser dashboard sessions)
    2. Query parameter: `token` or `api_key`
    3. Custom headers: `Authorization: Bearer ...` or `X-API-Key: ...`
    """
    raw_token = None

    # Check cookies first (standard for browser WebSockets)
    cookie_token = websocket.cookies.get("agentlens_access_token")
    if cookie_token:
        raw_token = cookie_token.strip()

    # Fall back to query params
    if not raw_token:
        auth_param = token_param or api_key_param
        if auth_param:
            raw_token = auth_param.strip()

    # Fall back to headers
    if not raw_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
        elif websocket.headers.get("x-api-key"):
            raw_token = websocket.headers.get("x-api-key", "").strip()

    if not raw_token:
        return None

    # 1. Check for JWT access token (UserPrincipal)
    if "." in raw_token:
        try:
            payload = security_service.decode_token(raw_token)
            if payload.get("type") == "access":
                user_repo = UserRepository(db)
                user = await user_repo.get_by_id(payload.get("sub", ""))
                if user and user.is_active:
                    return UserPrincipal(
                        user_id=user.id,
                        email=user.email,
                        full_name=user.full_name,
                        is_superuser=user.is_superuser,
                        is_active=user.is_active,
                    )
        except Exception:
            pass

    # 2. Check for ingestion API key (al_live_...)
    if raw_token.startswith("al_live_"):
        key_hash = security_service.hash_api_key(raw_token)
        key_repo = ApiKeyRepository(db)
        key = await key_repo.get_by_hash(key_hash)
        if key and not key.is_revoked:
            if key.expires_at:
                now = datetime.now(timezone.utc)
                exp = (
                    key.expires_at
                    if key.expires_at.tzinfo
                    else key.expires_at.replace(tzinfo=timezone.utc)
                )
                if exp <= now:
                    return None

            proj_repo = ProjectRepository(db)
            project = await proj_repo.get_by_id(key.project_id)
            return IngestionPrincipal(
                project_id=key.project_id,
                project_name=project.name if project else "default",
                api_key_id=key.id,
                key_prefix=key.key_prefix,
                scopes=key.scopes or ["ingest"],
            )
        return None

    # 3. Check for legacy dev key fallback strictly in dev/test environments
    env_str = getattr(settings, "environment", "development").lower()
    is_dev = env_str in ("development", "dev", "test", "testing", "local")
    if is_dev and auth_service.validate_api_key(raw_token):
        return raw_token

    return None


async def _verify_websocket_trace_access(
    trace_id: str,
    principal: Union[UserPrincipal, IngestionPrincipal, str],
    db: AsyncSession,
) -> bool:
    """Verify that the authenticated principal is authorized for the given trace."""
    repo = TraceRepository(db)
    trace = await repo.get_by_trace_id(trace_id)
    if not trace:
        return False

    if isinstance(principal, IngestionPrincipal):
        # Ingestion key strictly scoped to its own project
        return trace.project_id == principal.project_id

    if isinstance(principal, str):
        # Legacy test key fallback strictly in dev/test environments
        env_str = getattr(settings, "environment", "development").lower()
        return env_str in ("development", "dev", "test", "testing", "local")

    if isinstance(principal, UserPrincipal):
        if principal.is_superuser:
            return True

        # Check organization membership
        stmt = (
            select(OrganizationMemberModel)
            .join(ProjectModel, OrganizationMemberModel.organization_id == ProjectModel.organization_id)
            .where(
                ProjectModel.id == trace.project_id,
                OrganizationMemberModel.user_id == principal.user_id,
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none() is not None

    return False


@router.websocket("/ws/traces/{trace_id}")
async def trace_websocket_endpoint(
    websocket: WebSocket,
    trace_id: str,
    token: Optional[str] = Query(None, description="API key or JWT token for browser WebSocket"),
    api_key: Optional[str] = Query(None, description="Alternative API key parameter"),
    db: AsyncSession = Depends(get_db),
):
    """Real-time WebSocket endpoint streaming execution events with complete tenant isolation.

    Lifecycle:
    1. Validates trace_id format and length.
    2. Authenticates connecting client (Cookie, Query parameter, or Header).
    3. Enforces server-side tenant authorization BEFORE accepting or subscribing to Redis.
    4. Rejects unauthorized or nonexistent traces with WS_1008_POLICY_VIOLATION ("Trace not found").
    5. Accepts connection and registers subscription in Redis Pub/Sub.
    6. Allows safe subscription changes with per-trace re-authorization.
    7. Gracefully handles client disconnects, errors, and cleanup.
    """
    # 1. Validate trace_id format to prevent channel injection
    if not trace_id or not TRACE_ID_REGEX.match(trace_id):
        logger.warning(f"Rejected WebSocket connection for malformed trace ID: '{trace_id[:32]}'")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid trace ID format",
        )
        return

    # 2. Authenticate connection
    principal = await _authenticate_websocket(websocket, token, api_key, db)
    if not principal:
        logger.warning(f"Rejected unauthenticated WebSocket connection for trace '{trace_id}'")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Unauthorized: Invalid or missing API key",
        )
        return

    # 3. Verify server-side authorization for initial trace
    try:
        is_authorized = await _verify_websocket_trace_access(trace_id, principal, db)
        if not is_authorized:
            # Anti-IDOR: Always return "Trace '{trace_id}' not found" for missing or unauthorized
            logger.warning(f"Rejected unauthorized WebSocket access for trace '{trace_id}'")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Trace '{trace_id}' not found",
            )
            return
    except Exception as e:
        logger.error(
            f"Database error verifying trace for WebSocket '{trace_id}': {mask_connection_string(str(e))}"
        )
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Internal error",
        )
        return

    # 4. Accept connection and register subscription
    await websocket.accept()
    await realtime_service.connect(websocket, trace_id)

    subscribed_traces: Set[str] = {trace_id}

    # 5. Message loop with dynamic subscription authorization checks
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                continue

            try:
                msg = json.loads(data)
                action = msg.get("action")
                target_trace = msg.get("trace_id")

                if action == "subscribe" and target_trace:
                    if not TRACE_ID_REGEX.match(target_trace):
                        await websocket.send_json(
                            {"error": "Invalid trace ID format", "trace_id": target_trace}
                        )
                        continue

                    # Server-side authorization check before subscribing to new channel
                    target_authorized = await _verify_websocket_trace_access(
                        target_trace, principal, db
                    )
                    if not target_authorized:
                        await websocket.send_json(
                            {"error": f"Trace '{target_trace}' not found", "trace_id": target_trace}
                        )
                        continue

                    await realtime_service.connect(websocket, target_trace)
                    subscribed_traces.add(target_trace)
                    await websocket.send_json(
                        {"status": "subscribed", "trace_id": target_trace}
                    )

                elif action == "unsubscribe" and target_trace:
                    if target_trace in subscribed_traces:
                        await realtime_service.disconnect(websocket, target_trace)
                        subscribed_traces.discard(target_trace)
                        await websocket.send_json(
                            {"status": "unsubscribed", "trace_id": target_trace}
                        )

            except json.JSONDecodeError:
                pass  # Ignore arbitrary non-JSON text

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly for trace '{trace_id}'")
    except Exception as e:
        logger.debug(f"WebSocket connection exception for trace '{trace_id}': {e}")
    finally:
        for tid in subscribed_traces:
            await realtime_service.disconnect(websocket, tid)
