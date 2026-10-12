"""API dependencies for dependency injection (Phase 19B Multi-Tenant Security)."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Union

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import DEFAULT_PROJECT_ID
from app.db.repositories import ApiKeyRepository, ProjectRepository, UserRepository
from app.db.session import get_db
from app.services.auth import auth_service
from app.services.security import security_service

logger = logging.getLogger(__name__)


@dataclass
class UserPrincipal:
    """Authenticated human dashboard user (Channel 1)."""

    user_id: str
    email: str
    full_name: Optional[str] = None
    is_superuser: bool = False
    is_active: bool = True


@dataclass
class IngestionPrincipal:
    """Authenticated SDK / AI agent ingestion credential (Channel 2)."""

    project_id: str
    project_name: str
    api_key_id: str
    key_prefix: str
    scopes: List[str] = field(default_factory=lambda: ["ingest"])


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    agentlens_access_token: Optional[str] = Cookie(None),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    agentlens_csrf_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> UserPrincipal:
    """Resolve authenticated user principal from HttpOnly cookie or Bearer token.

    Validates:
    - JWT signature and expiration
    - Token claims ('sub', 'type' == 'access')
    - CSRF token comparison for cookie-based state-changing requests
    - User active status in database
    """
    token = None
    is_cookie_auth = False

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        is_cookie_auth = False
    elif agentlens_access_token:
        token = agentlens_access_token.strip()
        is_cookie_auth = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # CSRF protection: If authenticated via browser cookie on state-changing methods,
    # strictly verify double-submit CSRF token AND origin header against configured CORS origins.
    if is_cookie_auth and request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if not security_service.verify_csrf_token(x_csrf_token, agentlens_csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid",
            )
        origin = request.headers.get("origin")
        if origin:
            configured = [o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()]
            clean_origin = origin.strip().rstrip("/")
            if clean_origin not in configured:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Origin not allowed for cookie-authenticated request",
                )

    try:
        payload = security_service.decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found",
        )

    return UserPrincipal(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
    )


async def get_ingestion_principal(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> IngestionPrincipal:
    """Resolve authenticated ingestion principal from project-scoped API key.

    Validates:
    - API key format (al_live_...)
    - SHA-256 hash match against stored active key
    - Expiration and revocation checks
    - Development fallback keys (test_api_key_123, dev_key) for SDK tests
    """
    raw_key = None
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raw_key = authorization[7:].strip()
    elif x_api_key:
        raw_key = x_api_key.strip()
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Channel 2: Project-scoped Ingestion API Keys
    if raw_key.startswith("al_live_"):
        key_hash = security_service.hash_api_key(raw_key)
        key_repo = ApiKeyRepository(db)
        key = await key_repo.get_by_hash(key_hash)
        if not key or key.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify key expiration
        if key.expires_at:
            now = datetime.now(timezone.utc)
            exp = (
                key.expires_at
                if key.expires_at.tzinfo
                else key.expires_at.replace(tzinfo=timezone.utc)
            )
            if exp <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        proj_repo = ProjectRepository(db)
        project = await proj_repo.get_by_id(key.project_id)
        project_name = project.name if project else "default"

        return IngestionPrincipal(
            project_id=key.project_id,
            project_name=project_name,
            api_key_id=key.id,
            key_prefix=key.key_prefix,
            scopes=key.scopes or ["ingest"],
        )

    # Fallback for development / test keys (test_api_key_123, dev_key) strictly in dev/test
    env_str = getattr(settings, "environment", "development").lower()
    is_dev = env_str in ("development", "dev", "test", "testing", "local")
    if is_dev and auth_service.validate_api_key(raw_key):
        return IngestionPrincipal(
            project_id=DEFAULT_PROJECT_ID,
            project_name="default",
            api_key_id="legacy-dev-key",
            key_prefix=raw_key[:8],
            scopes=["ingest"],
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_dashboard_access(
    request: Request,
    authorization: Optional[str] = Header(None),
    agentlens_access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> Union[UserPrincipal, str]:
    """Verify that caller accessing dashboard endpoints is authorized.

    CRITICAL SECURITY INVARIANT:
    Ingestion keys (al_live_...) are strictly prohibited from reading traces (403 Forbidden).
    Dashboard access requires a valid UserPrincipal (cookie or Bearer JWT) or legacy dev key.
    """
    if not authorization and not agentlens_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_key = None
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raw_key = authorization[7:].strip()
        if not raw_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Ingestion keys are strictly forbidden on dashboard read endpoints!
    if raw_key and raw_key.startswith("al_live_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ingestion keys cannot access dashboard endpoints",
        )

    # Check for UserPrincipal (Bearer JWT or Cookie)
    token = None
    if raw_key and ("." in raw_key):  # JWT format
        token = raw_key
    elif agentlens_access_token:
        token = agentlens_access_token.strip()

    if token:
        try:
            payload = security_service.decode_token(token)
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

    # Legacy dev key fallback for Phase 1-18 test suite compatibility strictly in dev/test
    env_str = getattr(settings, "environment", "development").lower()
    is_dev = env_str in ("development", "dev", "test", "testing", "local")
    if is_dev and raw_key and auth_service.validate_api_key(raw_key):
        return raw_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_api_key(
    auth: Union[UserPrincipal, str] = Depends(verify_dashboard_access),
) -> str:
    """Legacy dependency adapter that enforces ingestion-key rejection."""
    if isinstance(auth, UserPrincipal):
        return auth.user_id
    return auth


async def get_project_name(
    x_agentlens_project: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract project name from header."""
    if not x_agentlens_project:
        return None
    return auth_service.extract_project_name(x_agentlens_project)
