"""Authentication endpoints for AgentLens (Phase 19B Core Authentication)."""

import logging
from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import UserPrincipal, get_current_user
from app.config import settings
from app.db.repositories import (
    ApiKeyRepository,
    OrganizationRepository,
    ProjectRepository,
    UserRepository,
)
from app.db.session import get_db
from app.models.auth import (
    AuthResponse,
    LoginRequest,
    OrganizationBrief,
    ProjectBrief,
    RegisterRequest,
    UserProfileResponse,
    UserResponse,
)
from app.services.security import security_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """Set HttpOnly session cookies and CSRF cookie on response."""
    # Short-lived access token cookie (HttpOnly)
    response.set_cookie(
        key="agentlens_access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
        path="/",
    )
    # Long-lived refresh token cookie (HttpOnly)
    response.set_cookie(
        key="agentlens_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        domain=settings.cookie_domain,
        path="/",
    )
    # CSRF cookie (readable by browser JS to send in X-CSRF-Token header)
    response.set_cookie(
        key="agentlens_csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear all authentication cookies."""
    for cookie_name in ("agentlens_access_token", "agentlens_refresh_token", "agentlens_csrf_token"):
        response.delete_cookie(
            key=cookie_name,
            path="/",
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=True if cookie_name != "agentlens_csrf_token" else False,
            samesite=settings.cookie_samesite,
        )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new human user, create default org & project, and issue initial ingestion key.

    Security guarantees:
    - Passwords hashed using bcrypt (work factor 12)
    - Registered users are NEVER granted superuser status (is_superuser=False)
    - Issues HttpOnly authenticated session cookies
    - Provisions initial project ingestion API key shown ONCE
    """
    user_repo = UserRepository(db)
    existing = await user_repo.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password
    hashed_pw = security_service.hash_password(payload.password)

    # 1. Create user with is_superuser=False
    user = await user_repo.create(
        email=payload.email,
        hashed_password=hashed_pw,
        full_name=payload.full_name,
        is_active=True,
        is_superuser=False,
    )

    # 2. Provision default Organization for user
    org_repo = OrganizationRepository(db)
    org_name = f"{payload.full_name}'s Org" if payload.full_name else f"{payload.email.split('@')[0]}'s Org"
    org_slug = f"org-{user.id[:8]}"
    org = await org_repo.create(name=org_name, slug=org_slug)
    await org_repo.add_member(organization_id=org.id, user_id=user.id, role="owner")

    # 3. Provision default Project
    proj_repo = ProjectRepository(db)
    project = await proj_repo.create(
        organization_id=org.id,
        name="Default Project",
        slug="default",
        description="Default workspace project",
    )

    # 4. Generate initial ingestion API key
    raw_key, prefix, key_hash = security_service.generate_ingestion_api_key()
    api_key_repo = ApiKeyRepository(db)
    await api_key_repo.create(
        project_id=project.id,
        name="Default Ingestion Key",
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=["ingest"],
    )

    # 5. Issue session tokens & CSRF token
    access_token = security_service.create_access_token(
        user_id=user.id,
        email=user.email,
        is_superuser=user.is_superuser,
    )
    refresh_token = security_service.create_refresh_token(user_id=user.id)
    csrf_token = security_service.generate_csrf_token()

    _set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        message="Registration successful",
        access_token=access_token,
        token_type="bearer",
        csrf_token=csrf_token,
        api_key=raw_key,  # Returned ONCE
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate user with email and password, establishing an HttpOnly session."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(payload.email)

    if not user or not security_service.verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    access_token = security_service.create_access_token(
        user_id=user.id,
        email=user.email,
        is_superuser=user.is_superuser,
    )
    refresh_token = security_service.create_refresh_token(user_id=user.id)
    csrf_token = security_service.generate_csrf_token()

    _set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        message="Login successful",
        access_token=access_token,
        token_type="bearer",
        csrf_token=csrf_token,
        api_key=None,
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
)
async def refresh_session(
    response: Response,
    agentlens_refresh_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh an access token using a valid refresh token."""
    raw_token = None
    if agentlens_refresh_token:
        raw_token = agentlens_refresh_token.strip()
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:].strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    try:
        payload = security_service.decode_token(raw_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for refresh",
        )

    user_id = payload.get("sub")
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found",
        )

    new_access_token = security_service.create_access_token(
        user_id=user.id,
        email=user.email,
        is_superuser=user.is_superuser,
    )
    new_refresh_token = security_service.create_refresh_token(user_id=user.id)
    new_csrf_token = security_service.generate_csrf_token()

    _set_auth_cookies(response, new_access_token, new_refresh_token, new_csrf_token)

    return {
        "message": "Token refreshed successfully",
        "access_token": new_access_token,
        "token_type": "bearer",
        "csrf_token": new_csrf_token,
    }


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
async def logout(response: Response) -> dict:
    """Clear all authenticated session cookies."""
    _clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_current_user_profile(
    current_user: UserPrincipal = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Retrieve identity, assigned organizations, and projects for current user."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    org_repo = OrganizationRepository(db)
    proj_repo = ProjectRepository(db)

    org_tuples = await org_repo.get_user_organizations(user.id)
    organizations: list[OrganizationBrief] = []
    projects: list[ProjectBrief] = []

    for org, role in org_tuples:
        organizations.append(
            OrganizationBrief(id=org.id, name=org.name, slug=org.slug, role=role)
        )
        org_projects = await proj_repo.list_by_organization(org.id)
        for proj in org_projects:
            projects.append(
                ProjectBrief(
                    id=proj.id,
                    organization_id=proj.organization_id,
                    name=proj.name,
                    slug=proj.slug,
                    description=proj.description,
                )
            )

    return UserProfileResponse(
        user=UserResponse.model_validate(user),
        organizations=organizations,
        projects=projects,
    )
