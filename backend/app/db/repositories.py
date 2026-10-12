"""Database repositories for data access (Phase 19 Multi-Tenant)."""

import logging
import uuid
from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    DEFAULT_PROJECT_ID,
    ApiKeyModel,
    EventModel,
    FailureEmbeddingModel,
    OrganizationMemberModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
    UserModel,
)
from app.models.event import EventCreate
from app.models.trace import TraceCreate

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user data operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
        is_active: bool = True,
        is_superuser: bool = False,
        user_id: Optional[str] = None,
    ) -> UserModel:
        """Create a new user."""
        user = UserModel(
            id=user_id or str(uuid.uuid4()),
            email=email.strip().lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=is_active,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        logger.info(f"Created user {user.email} ({user.id})")
        return user

    async def get_by_id(self, user_id: str) -> Optional[UserModel]:
        """Find user by unique ID."""
        stmt = select(UserModel).where(UserModel.id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[UserModel]:
        """Find user by email address."""
        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_users(self, limit: int = 100, offset: int = 0) -> list[UserModel]:
        """List users with pagination."""
        stmt = select(UserModel).order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class OrganizationRepository:
    """Repository for organization and membership data operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        slug: str,
        org_id: Optional[str] = None,
    ) -> OrganizationModel:
        """Create a new organization."""
        org = OrganizationModel(
            id=org_id or str(uuid.uuid4()),
            name=name.strip(),
            slug=slug.strip().lower(),
        )
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        logger.info(f"Created organization {org.name} ({org.slug})")
        return org

    async def get_by_id(self, org_id: str) -> Optional[OrganizationModel]:
        """Find organization by ID."""
        stmt = select(OrganizationModel).where(OrganizationModel.id == org_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[OrganizationModel]:
        """Find organization by slug."""
        stmt = select(OrganizationModel).where(OrganizationModel.slug == slug.strip().lower())
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_member(
        self,
        organization_id: str,
        user_id: str,
        role: str = "member",
    ) -> OrganizationMemberModel:
        """Add a user to an organization with a specific role."""
        member = OrganizationMemberModel(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        logger.info(f"Added member {user_id} to org {organization_id} (role={role})")
        return member

    async def get_user_role(self, organization_id: str, user_id: str) -> Optional[str]:
        """Get user's role in an organization."""
        stmt = select(OrganizationMemberModel.role).where(
            OrganizationMemberModel.organization_id == organization_id,
            OrganizationMemberModel.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_organizations(self, user_id: str) -> list[tuple[OrganizationModel, str]]:
        """Get all organizations a user belongs to along with their role."""
        stmt = (
            select(OrganizationModel, OrganizationMemberModel.role)
            .join(OrganizationMemberModel, OrganizationModel.id == OrganizationMemberModel.organization_id)
            .where(OrganizationMemberModel.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]


class ProjectRepository:
    """Repository for project operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        organization_id: str,
        name: str,
        slug: str,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> ProjectModel:
        """Create a new project scoped to an organization."""
        project = ProjectModel(
            id=project_id or str(uuid.uuid4()),
            organization_id=organization_id,
            name=name.strip(),
            slug=slug.strip().lower(),
            description=description,
        )
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        logger.info(f"Created project {project.name} ({project.id}) in org {organization_id}")
        return project

    async def get_by_id(self, project_id: str) -> Optional[ProjectModel]:
        """Find project by ID."""
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_slug(self, organization_id: str, slug: str) -> Optional[ProjectModel]:
        """Find project by slug within an organization."""
        stmt = select(ProjectModel).where(
            ProjectModel.organization_id == organization_id,
            ProjectModel.slug == slug.strip().lower(),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_organization(self, organization_id: str) -> list[ProjectModel]:
        """List all projects belonging to an organization."""
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.organization_id == organization_id)
            .order_by(ProjectModel.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_or_create_default(
        self,
        organization_id: Optional[str] = None,
        slug: str = "default",
        name: str = "Default Project",
    ) -> ProjectModel:
        """Find or create a default project to guarantee foreign key integrity."""
        # 1. Search existing project by slug
        stmt = select(ProjectModel)
        if organization_id:
            stmt = stmt.where(ProjectModel.organization_id == organization_id)
        stmt = stmt.where(ProjectModel.slug == slug)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        # 2. Scope to the designated or default organization
        if not organization_id:
            org_repo = OrganizationRepository(self.session)
            org = await org_repo.get_by_slug("default-org")
            if not org:
                org = await org_repo.create(name="Default Organization", slug="default-org")
            organization_id = org.id

        return await self.create(
            organization_id=organization_id,
            name=name,
            slug=slug,
            description="Default workspace project",
        )


class ApiKeyRepository:
    """Repository for project-scoped API keys."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: str,
        name: str,
        key_prefix: str,
        key_hash: str,
        key_type: str = "ingestion",
        scopes: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        api_key_id: Optional[str] = None,
    ) -> ApiKeyModel:
        """Create and store a new project API key record."""
        api_key = ApiKeyModel(
            id=api_key_id or str(uuid.uuid4()),
            project_id=project_id,
            name=name.strip(),
            key_prefix=key_prefix.strip(),
            key_hash=key_hash.strip(),
            key_type=key_type,
            scopes=scopes or ["ingest"],
            expires_at=expires_at,
        )
        self.session.add(api_key)
        await self.session.flush()
        await self.session.refresh(api_key)
        logger.info(f"Created API key {api_key.name} ({api_key.key_prefix}...) for project {project_id}")
        return api_key

    async def get_by_id(self, api_key_id: str) -> Optional[ApiKeyModel]:
        """Find key by ID."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.id == api_key_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKeyModel]:
        """Find active key by secret SHA-256 hash."""
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.key_hash == key_hash,
            ApiKeyModel.is_revoked.is_(False),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_prefix(self, key_prefix: str) -> list[ApiKeyModel]:
        """Find keys by prefix."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_prefix == key_prefix)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_by_project(self, project_id: str) -> list[ApiKeyModel]:
        """List all keys for a specific project."""
        stmt = (
            select(ApiKeyModel)
            .where(ApiKeyModel.project_id == project_id)
            .order_by(ApiKeyModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def revoke(self, api_key_id: str) -> bool:
        """Revoke an API key."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.id == api_key_id)
        res = await self.session.execute(stmt)
        key = res.scalar_one_or_none()
        if not key:
            return False
        key.is_revoked = True
        await self.session.flush()
        logger.info(f"Revoked API key {api_key_id}")
        return True


class TraceRepository:
    """Repository for trace database operations with project ownership."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        trace: TraceCreate,
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> TraceModel:
        """Create or update a trace with strict project ownership."""
        target_project_id = project_id or getattr(trace, "project_id", None)
        resolved_project_name = project_name or getattr(trace, "project_name", None)

        proj_repo = ProjectRepository(self.session)
        if target_project_id:
            # Validate project exists
            project = await proj_repo.get_by_id(target_project_id)
            if not project:
                if target_project_id == DEFAULT_PROJECT_ID:
                    project = await proj_repo.get_or_create_default(
                        organization_id=None,
                        name=resolved_project_name or "Default Project",
                        slug="default",
                    )
                else:
                    raise ValueError(f"Project '{target_project_id}' not found")
            if not resolved_project_name:
                resolved_project_name = project.name
        else:
            # Auto-resolve or create project matching project_name / default
            slug = resolved_project_name.lower().replace(" ", "-") if resolved_project_name else "default"
            project = await proj_repo.get_or_create_default(
                slug=slug,
                name=resolved_project_name or "Default Project",
            )
            target_project_id = project.id
            if not resolved_project_name:
                resolved_project_name = project.name

        existing = await self.get_by_trace_id(trace.trace_id)
        if existing:
            # SECURITY: Trace ownership cannot be hijacked or reassigned across projects
            if existing.project_id != target_project_id:
                raise ValueError(
                    f"Trace '{trace.trace_id}' already belongs to project '{existing.project_id}' "
                    f"and cannot be reassigned to '{target_project_id}'"
                )
            existing.name = trace.name
            if resolved_project_name:
                existing.project_name = resolved_project_name
            if trace.end_time:
                existing.end_time = trace.end_time
            if trace.status:
                existing.status = trace.status
            if hasattr(trace, "metadata_") and isinstance(trace.metadata_, dict):
                existing.metadata_ = trace.metadata_
            elif hasattr(trace, "metadata") and isinstance(trace.metadata, dict):
                existing.metadata_ = trace.metadata
            await self.session.flush()
            await self.session.refresh(existing)
            logger.info(f"Updated trace {existing.trace_id} in database")
            return existing

        trace_meta = {}
        if hasattr(trace, "metadata_") and isinstance(trace.metadata_, dict):
            trace_meta = trace.metadata_
        elif hasattr(trace, "metadata") and isinstance(trace.metadata, dict):
            trace_meta = trace.metadata

        db_trace = TraceModel(
            trace_id=trace.trace_id,
            name=trace.name,
            project_id=target_project_id,
            project_name=resolved_project_name,
            start_time=trace.start_time,
            end_time=trace.end_time,
            status=trace.status,
            metadata_=trace_meta,
        )

        self.session.add(db_trace)
        await self.session.flush()
        await self.session.refresh(db_trace)

        logger.info(f"Created trace {db_trace.trace_id} in database (project_id={target_project_id})")
        return db_trace

    async def get_by_trace_id(self, trace_id: str) -> Optional[TraceModel]:
        """Get trace by trace_id."""
        stmt = select(TraceModel).where(TraceModel.trace_id == trace_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        trace_id: str,
        status: str,
        end_time: Optional[datetime] = None,
    ) -> Optional[TraceModel]:
        """Update trace execution status and optional end_time."""
        trace = await self.get_by_trace_id(trace_id)
        if trace:
            trace.status = status
            if end_time:
                trace.end_time = end_time
            await self.session.flush()
            await self.session.refresh(trace)
            logger.info(f"Updated status of trace {trace_id} to '{status}' (end_time={end_time})")
        return trace

    async def exists(self, trace_id: str) -> bool:
        """Check if trace exists."""
        trace = await self.get_by_trace_id(trace_id)
        return trace is not None

    async def get_with_events(self, trace_id: str) -> Optional[TraceModel]:
        """Get trace with its events loaded."""
        stmt = (
            select(TraceModel)
            .options(selectinload(TraceModel.events))
            .where(TraceModel.trace_id == trace_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_traces(
        self,
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
        project_ids: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[TraceModel, int]]:
        """List traces with event count ordered by start_time descending."""
        if project_ids is not None and len(project_ids) == 0:
            return []

        stmt = (
            select(TraceModel, func.count(EventModel.id).label("event_count"))
            .outerjoin(EventModel, TraceModel.trace_id == EventModel.trace_id)
            .group_by(TraceModel.id)
            .order_by(TraceModel.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
        if project_id:
            stmt = stmt.where(TraceModel.project_id == project_id)
        elif project_ids is not None:
            stmt = stmt.where(TraceModel.project_id.in_(project_ids))
        if project_name:
            stmt = stmt.where(TraceModel.project_name == project_name)

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


class EventRepository:
    """Repository for event database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        event: EventCreate,
        project_name: Optional[str] = None,
    ) -> EventModel:
        """Create a new event."""
        db_event = EventModel(
            event_id=event.event_id,
            trace_id=event.trace_id,
            parent_event_id=event.parent_event_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            data=event.data,
            metadata_=event.metadata,
        )

        self.session.add(db_event)
        await self.session.flush()
        await self.session.refresh(db_event)

        logger.info(
            f"Created event {db_event.event_id} for trace {db_event.trace_id} in database"
        )
        return db_event

    async def get_by_event_id(self, event_id: str) -> Optional[EventModel]:
        """Get event by event_id."""
        stmt = select(EventModel).where(EventModel.event_id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_trace_id(
        self,
        trace_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[EventModel]:
        """Get all events for a trace ordered by timestamp."""
        stmt = (
            select(EventModel)
            .where(EventModel.trace_id == trace_id)
            .order_by(EventModel.timestamp.asc(), EventModel.id.asc())
            .offset(offset)
        )
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_batch(
        self,
        events: list[EventCreate],
        project_name: Optional[str] = None,
    ) -> list[EventModel]:
        """Create multiple events in a batch."""
        db_events = [
            EventModel(
                event_id=event.event_id,
                trace_id=event.trace_id,
                parent_event_id=event.parent_event_id,
                event_type=event.event_type.value,
                timestamp=event.timestamp,
                data=event.data,
                metadata_=event.metadata,
            )
            for event in events
        ]

        self.session.add_all(db_events)
        await self.session.flush()

        for db_event in db_events:
            await self.session.refresh(db_event)

        logger.info(f"Created batch of {len(db_events)} events in database")
        return db_events

    async def count_by_trace_id(self, trace_id: str) -> int:
        """Count events for a trace."""
        stmt = select(func.count(EventModel.id)).where(
            EventModel.trace_id == trace_id
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class FailureEmbeddingRepository:
    """Repository for historical failure embeddings (Phase 15 & 19)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        trace_id: str,
        finding_id: str,
        rule: str,
        category: str,
        severity: str,
        searchable_text: str,
        embedding: list[float],
        metadata: dict[str, Any],
        project_id: Optional[str] = None,
    ) -> FailureEmbeddingModel:
        """Upsert a failure embedding."""
        # Resolve and enforce consistent project ownership with parent trace
        trace_stmt = select(TraceModel.project_id).where(TraceModel.trace_id == trace_id)
        trace_res = await self.session.execute(trace_stmt)
        trace_project_id = trace_res.scalar_one_or_none()
        if not trace_project_id:
            raise ValueError(f"Cannot index failure embedding: trace '{trace_id}' not found")

        if project_id and project_id != trace_project_id:
            raise ValueError(
                f"Failure embedding project_id '{project_id}' does not match "
                f"parent trace project_id '{trace_project_id}'"
            )
        target_project_id = trace_project_id

        stmt = select(FailureEmbeddingModel).where(
            FailureEmbeddingModel.trace_id == trace_id,
            FailureEmbeddingModel.finding_id == finding_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.rule = rule
            existing.category = category
            existing.severity = severity
            existing.searchable_text = searchable_text
            existing.embedding = embedding
            existing.metadata_ = metadata
            existing.project_id = target_project_id
            await self.session.flush()
            await self.session.refresh(existing)
            logger.info(f"Updated failure embedding for {trace_id}:{finding_id}")
            return existing

        model = FailureEmbeddingModel(
            trace_id=trace_id,
            project_id=target_project_id,
            finding_id=finding_id,
            rule=rule,
            category=category,
            severity=severity,
            searchable_text=searchable_text,
            embedding=embedding,
            metadata_=metadata,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        logger.info(f"Inserted failure embedding for {trace_id}:{finding_id}")
        return model

    async def get_by_trace_id(self, trace_id: str) -> list[FailureEmbeddingModel]:
        """Retrieve all failure embeddings for a trace."""
        stmt = (
            select(FailureEmbeddingModel)
            .where(FailureEmbeddingModel.trace_id == trace_id)
            .order_by(FailureEmbeddingModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_similar(
        self,
        query_vector: list[float],
        limit: int = 10,
        severity: Optional[str] = None,
        rule: Optional[str] = None,
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
        project_ids: Optional[list[str]] = None,
    ) -> list[tuple[FailureEmbeddingModel, float, str, Optional[str]]]:
        """Search similar failure embeddings using cosine distance."""
        if project_ids is not None and len(project_ids) == 0:
            return []

        bind = self.session.bind
        dialect_name = bind.dialect.name if bind else "postgresql"

        if dialect_name == "postgresql":
            distance_expr = FailureEmbeddingModel.embedding.cosine_distance(query_vector).label("distance")
            stmt = (
                select(
                    FailureEmbeddingModel,
                    distance_expr,
                    TraceModel.name.label("trace_name"),
                    TraceModel.project_name.label("project_name"),
                )
                .join(TraceModel, FailureEmbeddingModel.trace_id == TraceModel.trace_id)
            )

            if project_id:
                stmt = stmt.where(TraceModel.project_id == project_id)
            elif project_ids is not None:
                stmt = stmt.where(TraceModel.project_id.in_(project_ids))
            if project_name:
                stmt = stmt.where(TraceModel.project_name == project_name)
            if severity:
                stmt = stmt.where(FailureEmbeddingModel.severity == severity.lower())
            if rule:
                stmt = stmt.where(FailureEmbeddingModel.rule == rule)

            stmt = stmt.order_by(
                distance_expr.asc(),
                FailureEmbeddingModel.created_at.desc(),
                FailureEmbeddingModel.trace_id.asc(),
                FailureEmbeddingModel.finding_id.asc(),
            ).limit(limit)

            result = await self.session.execute(stmt)
            rows = result.all()
            return [
                (
                    row[0],
                    round(max(0.0, min(1.0, 1.0 - float(row[1]))), 4),
                    row[2],
                    row[3],
                )
                for row in rows
            ]
        else:
            # SQLite fallback for test environments
            import math

            stmt = (
                select(
                    FailureEmbeddingModel,
                    TraceModel.name.label("trace_name"),
                    TraceModel.project_name.label("project_name"),
                )
                .join(TraceModel, FailureEmbeddingModel.trace_id == TraceModel.trace_id)
            )

            if project_id:
                stmt = stmt.where(TraceModel.project_id == project_id)
            elif project_ids is not None:
                stmt = stmt.where(TraceModel.project_id.in_(project_ids))
            if project_name:
                stmt = stmt.where(TraceModel.project_name == project_name)
            if severity:
                stmt = stmt.where(FailureEmbeddingModel.severity == severity.lower())
            if rule:
                stmt = stmt.where(FailureEmbeddingModel.rule == rule)

            result = await self.session.execute(stmt)
            candidates = result.all()

            def _cosine_sim(v1: list[float], v2: list[float]) -> float:
                dot = sum(a * b for a, b in zip(v1, v2))
                norm1 = math.sqrt(sum(a * a for a in v1))
                norm2 = math.sqrt(sum(b * b for b in v2))
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                return max(0.0, min(1.0, dot / (norm1 * norm2)))

            scored = []
            for emb_model, t_name, p_name in candidates:
                sim = _cosine_sim(query_vector, emb_model.embedding)
                scored.append((emb_model, round(sim, 4), t_name, p_name))

            scored.sort(
                key=lambda x: (
                    -x[1],
                    -x[0].created_at.timestamp() if x[0].created_at else 0,
                    x[0].trace_id,
                    x[0].finding_id,
                )
            )
            return scored[:limit]
