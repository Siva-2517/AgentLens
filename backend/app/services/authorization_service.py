"""Authorization Service (Phase 19C Server-Side Tenant Authorization).

Enforces the core AgentLens multi-tenant authorization invariant:
A dashboard user may access a project only if they have a valid organization
membership and the project's organization belongs to that membership.

Security Invariants:
1. Server-side enforcement on EVERY request.
2. Anti-IDOR: Missing resources and unauthorized tenant resources return 404 Not Found
   to prevent resource existence disclosure and enumeration attacks.
3. Ingestion API keys are strictly rejected on dashboard read endpoints (403 Forbidden).
4. Organization roles ("owner", "admin", "member", "viewer") enforce appropriate privileges.
5. Real-time WebSockets authenticate and verify tenant authorization before Redis subscription.
"""

import logging
from typing import List, Optional, Union

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import UserPrincipal
from app.db.models import (
    DEFAULT_PROJECT_ID,
    OrganizationMemberModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
)
from app.db.repositories import ProjectRepository, TraceRepository

logger = logging.getLogger(__name__)


async def get_user_accessible_project_ids(
    principal: Union[UserPrincipal, str],
    db: AsyncSession,
) -> List[str]:
    """Retrieve all project IDs accessible by the given dashboard principal.

    - Superuser: access to all projects in the system.
    - UserPrincipal: access to all projects belonging to organizations where user has active membership.
    - Legacy dev key (string): scoped to DEFAULT_PROJECT_ID and default test organization.
    """
    if isinstance(principal, str):
        # Legacy test / dev key
        stmt = select(ProjectModel.id).where(
            (ProjectModel.organization_id == DEFAULT_PROJECT_ID)
            | (ProjectModel.id == DEFAULT_PROJECT_ID)
        )
        res = await db.execute(stmt)
        ids = list(res.scalars().all())
        return ids if ids else [DEFAULT_PROJECT_ID]

    if principal.is_superuser:
        stmt = select(ProjectModel.id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # Regular UserPrincipal: scoped to user's organization memberships
    stmt = (
        select(ProjectModel.id)
        .join(
            OrganizationMemberModel,
            ProjectModel.organization_id == OrganizationMemberModel.organization_id,
        )
        .where(OrganizationMemberModel.user_id == principal.user_id)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_user_role_in_project(
    project: ProjectModel,
    principal: Union[UserPrincipal, str],
    db: AsyncSession,
) -> Optional[str]:
    """Get the caller's role in the organization owning the project."""
    if isinstance(principal, str):
        return "owner"
    if principal.is_superuser:
        return "owner"

    stmt = select(OrganizationMemberModel.role).where(
        OrganizationMemberModel.organization_id == project.organization_id,
        OrganizationMemberModel.user_id == principal.user_id,
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def verify_project_access(
    project_id: str,
    principal: Union[UserPrincipal, str],
    db: AsyncSession,
    required_min_role: Optional[str] = None,
) -> ProjectModel:
    """Verify that dashboard caller has access to the specified project.

    Returns:
        ProjectModel if access is granted.

    Raises:
        HTTPException(404): If project does not exist OR caller has no organization access (Anti-IDOR).
        HTTPException(403): If caller belongs to org but lacks required role (e.g. viewer managing keys).
    """
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id)
    if not project:
        if isinstance(principal, str) and (not project_id or project_id == DEFAULT_PROJECT_ID):
            return ProjectModel(
                id=DEFAULT_PROJECT_ID,
                organization_id=DEFAULT_PROJECT_ID,
                name="Default Project",
                slug="default",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if isinstance(principal, str):
        # Legacy test key fallback
        return project

    if principal.is_superuser:
        return project

    # Check organization membership
    stmt = select(OrganizationMemberModel).where(
        OrganizationMemberModel.organization_id == project.organization_id,
        OrganizationMemberModel.user_id == principal.user_id,
    )
    res = await db.execute(stmt)
    member = res.scalar_one_or_none()
    if not member:
        # Anti-IDOR: Return 404 to prevent resource existence disclosure
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Role enforcement
    if required_min_role in ("owner", "admin"):
        if member.role not in ("owner", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation",
            )

    return project


async def verify_trace_access(
    trace_id: str,
    principal: Union[UserPrincipal, str],
    db: AsyncSession,
) -> Optional[TraceModel]:
    """Verify that dashboard caller has access to the specified trace.

    Returns:
        TraceModel if trace exists and belongs to a project the caller is authorized to view.

    Raises:
        HTTPException(404): If trace does not exist OR belongs to an unauthorized tenant project (Anti-IDOR).
    """
    clean_id = (trace_id or "").strip()
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="trace_id parameter must not be empty",
        )

    trace_repo = TraceRepository(db)
    trace = await trace_repo.get_by_trace_id(clean_id)

    # Legacy test key: verify access if trace exists in DB;
    # if not found, allow downstream service to handle / raise TraceNotFoundError
    if isinstance(principal, str):
        if trace:
            await verify_project_access(trace.project_id, principal, db)
        return trace

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found",
        )

    # Verify project access for UserPrincipal
    try:
        await verify_project_access(trace.project_id, principal, db)
    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            # Anti-IDOR: Always return 404 with uniform trace error message
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trace '{clean_id}' not found",
            )
        raise

    return trace
