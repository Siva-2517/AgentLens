"""SQLAlchemy database models (Phase 19 Multi-Tenant Hardened)."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserModel(Base):
    """SQLAlchemy model for human users."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    memberships: Mapped[List["OrganizationMemberModel"]] = relationship(
        "OrganizationMemberModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.id})>"


class OrganizationModel(Base):
    """SQLAlchemy model for organizations (tenants)."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    members: Mapped[List["OrganizationMemberModel"]] = relationship(
        "OrganizationMemberModel",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects: Mapped[List["ProjectModel"]] = relationship(
        "ProjectModel",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.slug})>"


class OrganizationMemberModel(Base):
    """SQLAlchemy model linking users to organizations with role."""

    __tablename__ = "organization_members"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    organization_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="memberships")
    organization: Mapped["OrganizationModel"] = relationship(
        "OrganizationModel", back_populates="members"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationMember {self.user_id} in {self.organization_id} ({self.role})>"


class ProjectModel(Base):
    """SQLAlchemy model for projects scoped to an organization."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    organization_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    organization: Mapped["OrganizationModel"] = relationship(
        "OrganizationModel", back_populates="projects"
    )
    api_keys: Mapped[List["ApiKeyModel"]] = relationship(
        "ApiKeyModel", back_populates="project", cascade="all, delete-orphan"
    )
    traces: Mapped[List["TraceModel"]] = relationship(
        "TraceModel", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.slug})>"


class ApiKeyModel(Base):
    """SQLAlchemy model for project-scoped ingestion API keys."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_type: Mapped[str] = mapped_column(String(32), default="ingestion", nullable=False)
    scopes: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey {self.name} ({self.key_prefix}...)>"


DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


class TraceModel(Base):
    """SQLAlchemy model for traces with project ownership."""

    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=lambda: DEFAULT_PROJECT_ID,
    )

    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="traces")
    events: Mapped[list["EventModel"]] = relationship(
        "EventModel",
        back_populates="trace",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("trace_id", "project_id", name="uq_traces_trace_project"),
    )

    def __repr__(self) -> str:
        return f"<Trace {self.trace_id} ({self.name}, proj={self.project_id})>"


class EventModel(Base):
    """SQLAlchemy model for events."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("traces.trace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to trace
    trace: Mapped["TraceModel"] = relationship("TraceModel", back_populates="events")

    def __repr__(self) -> str:
        return f"<Event {self.event_id} ({self.event_type})>"


# Composite indexes for events
Index("idx_events_trace_timestamp", EventModel.trace_id, EventModel.timestamp)
Index("idx_events_trace_type", EventModel.trace_id, EventModel.event_type)


class FailureEmbeddingModel(Base):
    """SQLAlchemy model for historical failure embeddings (Phase 15 & 19)."""

    __tablename__ = "failure_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("traces.trace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    finding_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rule: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    searchable_text: Mapped[Text] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Unique constraint per trace and finding to ensure idempotent indexing
    __table_args__ = (
        UniqueConstraint("trace_id", "finding_id", name="uq_trace_finding_embedding"),
        Index("idx_failure_embeddings_rule_sev", "rule", "severity"),
    )

    def __repr__(self) -> str:
        return f"<FailureEmbedding {self.trace_id}:{self.finding_id} ({self.rule})>"
