"""Project and API key management endpoints (Phase 19C Ingestion Channel Security)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import UserPrincipal, get_current_user
from app.db.repositories import ApiKeyRepository, OrganizationRepository, ProjectRepository
from app.db.session import get_db
from app.models.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreatedResponse,
    ApiKeyInfoResponse,
    ProjectBrief,
)
from app.services.authorization_service import verify_project_access
from app.services.security import security_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get(
    "",
    response_model=List[ProjectBrief],
    status_code=status.HTTP_200_OK,
)
async def list_user_projects(
    current_user: UserPrincipal = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectBrief]:
    """List all projects accessible by current user across their organizations."""
    org_repo = OrganizationRepository(db)
    proj_repo = ProjectRepository(db)

    org_tuples = await org_repo.get_user_organizations(current_user.user_id)
    projects: list[ProjectBrief] = []
    seen_ids = set()

    for org, _ in org_tuples:
        org_projects = await proj_repo.list_by_organization(org.id)
        for proj in org_projects:
            if proj.id not in seen_ids:
                seen_ids.add(proj.id)
                projects.append(
                    ProjectBrief(
                        id=proj.id,
                        organization_id=proj.organization_id,
                        name=proj.name,
                        slug=proj.slug,
                        description=proj.description,
                    )
                )

    return projects


@router.post(
    "/{project_id}/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_api_key(
    project_id: str,
    payload: ApiKeyCreateRequest,
    current_user: UserPrincipal = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedResponse:
    """Generate a cryptographically secure ingestion API key for a project.

    The raw secret key is returned ONCE and never stored. Only SHA-256 hash is persisted.
    Requires owner or admin role in project's organization.
    """
    await verify_project_access(project_id, current_user, db, required_min_role="admin")

    raw_key, prefix, key_hash = security_service.generate_ingestion_api_key()

    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    scopes = payload.scopes if payload.scopes is not None else ["ingest"]
    key_type = payload.key_type or ("mcp" if ("mcp" in scopes or "read" in scopes) else "ingestion")

    if key_type == "mcp" and not any(s in ("mcp", "read") for s in scopes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MCP key type requires 'mcp' or 'read' in scopes",
        )

    key_repo = ApiKeyRepository(db)
    api_key = await key_repo.create(
        project_id=project_id,
        name=payload.name,
        key_prefix=prefix,
        key_hash=key_hash,
        key_type=key_type,
        scopes=scopes,
        expires_at=expires_at,
    )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        project_id=api_key.project_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key_type=api_key.key_type,
        scopes=api_key.scopes or scopes,
        api_key=raw_key,  # Raw secret shown ONLY ONCE
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.get(
    "/{project_id}/api-keys",
    response_model=List[ApiKeyInfoResponse],
    status_code=status.HTTP_200_OK,
)
async def list_project_api_keys(
    project_id: str,
    current_user: UserPrincipal = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ApiKeyInfoResponse]:
    """List all API keys for a project. Secrets and key hashes are NEVER returned."""
    await verify_project_access(project_id, current_user, db)

    key_repo = ApiKeyRepository(db)
    keys = await key_repo.list_by_project(project_id)
    return [ApiKeyInfoResponse.model_validate(k) for k in keys]


@router.delete(
    "/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_200_OK,
)
async def revoke_project_api_key(
    project_id: str,
    key_id: str,
    current_user: UserPrincipal = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke an API key immediately. Revoked keys cannot ingest telemetry.

    Requires owner or admin role in project's organization.
    """
    await verify_project_access(project_id, current_user, db, required_min_role="admin")

    key_repo = ApiKeyRepository(db)
    key = await key_repo.get_by_id(key_id)
    if not key or key.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    await key_repo.revoke(key_id)
    return {"message": "API key revoked successfully", "id": key_id}
