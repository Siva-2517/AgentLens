"""Tests for Phase 19A Project Ownership, Multi-Tenant Relationships, and Constraints."""

import hashlib
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.db.models import (
    ApiKeyModel,
    Base,
    EventModel,
    OrganizationMemberModel,
    OrganizationModel,
    ProjectModel,
    TraceModel,
    UserModel,
)
from app.db.repositories import (
    ApiKeyRepository,
    EventRepository,
    OrganizationRepository,
    ProjectRepository,
    TraceRepository,
    UserRepository,
)
from app.models.event import EventCreate, EventType
from app.models.trace import TraceCreate

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


# ==============================================================================
# Model & Relationship Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_user_repository_crud(test_db):
    """Test UserRepository creation and retrieval by email and ID."""
    repo = UserRepository(test_db)
    user = await repo.create(
        email="Alice@Example.com",  # verify case normalization
        hashed_password="hashed_pw_xyz",
        full_name="Alice Smith",
    )

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.full_name == "Alice Smith"
    assert user.is_active is True

    # Lookup by email
    by_email = await repo.get_by_email("ALICE@EXAMPLE.COM")
    assert by_email is not None
    assert by_email.id == user.id

    # Lookup by ID
    by_id = await repo.get_by_id(user.id)
    assert by_id is not None
    assert by_id.email == "alice@example.com"


@pytest.mark.asyncio
async def test_organization_and_membership_repository(test_db):
    """Test OrganizationRepository creation, membership addition, and role lookup."""
    user_repo = UserRepository(test_db)
    org_repo = OrganizationRepository(test_db)

    user1 = await user_repo.create("owner@test.com", "pw")
    user2 = await user_repo.create("member@test.com", "pw")

    org = await org_repo.create(name="Engineering Team", slug="eng-team")
    assert org.slug == "eng-team"

    m1 = await org_repo.add_member(org.id, user1.id, role="owner")
    m2 = await org_repo.add_member(org.id, user2.id, role="viewer")

    assert m1.role == "owner"
    assert m2.role == "viewer"

    # Verify roles
    role1 = await org_repo.get_user_role(org.id, user1.id)
    role2 = await org_repo.get_user_role(org.id, user2.id)
    assert role1 == "owner"
    assert role2 == "viewer"

    # User organizations list
    user1_orgs = await org_repo.get_user_organizations(user1.id)
    assert len(user1_orgs) == 1
    assert user1_orgs[0][0].slug == "eng-team"
    assert user1_orgs[0][1] == "owner"


@pytest.mark.asyncio
async def test_organization_member_unique_constraint(test_db):
    """Test that a user cannot have duplicate memberships in the same organization."""
    user_repo = UserRepository(test_db)
    org_repo = OrganizationRepository(test_db)

    user = await user_repo.create("dup@test.com", "pw")
    org = await org_repo.create("Dup Org", "dup-org")

    await org_repo.add_member(org.id, user.id, role="member")

    # Attempt duplicate membership
    with pytest.raises(Exception):
        await org_repo.add_member(org.id, user.id, role="admin")


@pytest.mark.asyncio
async def test_project_repository_crud(test_db):
    """Test ProjectRepository creation, slug lookup, and organization listing."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)

    org = await org_repo.create("Acme Corp", "acme-corp")
    p1 = await proj_repo.create(org.id, "Production Agent", "prod-agent", "Production AI assistant")
    p2 = await proj_repo.create(org.id, "Staging Agent", "staging-agent")

    assert p1.id is not None
    assert p1.organization_id == org.id

    # Lookup by slug
    found = await proj_repo.get_by_slug(org.id, "prod-agent")
    assert found is not None
    assert found.id == p1.id

    # List by org
    org_projects = await proj_repo.list_by_organization(org.id)
    assert len(org_projects) == 2
    slugs = [p.slug for p in org_projects]
    assert "prod-agent" in slugs
    assert "staging-agent" in slugs


@pytest.mark.asyncio
async def test_project_slug_unique_per_organization(test_db):
    """Test that project slug is unique within the same organization."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)

    org = await org_repo.create("My Org", "my-org")
    await proj_repo.create(org.id, "Agent 1", "agent-slug")

    with pytest.raises(Exception):
        await proj_repo.create(org.id, "Agent 2", "agent-slug")


@pytest.mark.asyncio
async def test_api_key_repository(test_db):
    """Test ApiKeyRepository creation, hash lookup, prefix lookup, and revocation."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)
    key_repo = ApiKeyRepository(test_db)

    org = await org_repo.create("Key Org", "key-org")
    proj = await proj_repo.create(org.id, "Key Proj", "key-proj")

    raw_secret = "al_live_sec_123456789abcdef"
    key_prefix = raw_secret[:12]
    key_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    key_record = await key_repo.create(
        project_id=proj.id,
        name="SDK Ingestion Key",
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=["ingest"],
    )

    assert key_record.id is not None
    assert key_record.project_id == proj.id
    assert key_record.is_revoked is False

    # Lookup by hash
    found = await key_repo.get_by_hash(key_hash)
    assert found is not None
    assert found.id == key_record.id

    # Lookup by prefix
    by_prefix = await key_repo.get_by_prefix(key_prefix)
    assert len(by_prefix) == 1
    assert by_prefix[0].id == key_record.id

    # Revoke key
    revoked = await key_repo.revoke(key_record.id)
    assert revoked is True

    # Active lookup returns None after revocation
    after_revocation = await key_repo.get_by_hash(key_hash)
    assert after_revocation is None


# ==============================================================================
# Trace Project Ownership & Isolation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_trace_creation_with_explicit_project(test_db):
    """Test that a trace is correctly bound to an explicit project."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)
    trace_repo = TraceRepository(test_db)

    org = await org_repo.create("Org X", "org-x")
    proj = await proj_repo.create(org.id, "Project Alpha", "project-alpha")

    trace = await trace_repo.create(
        TraceCreate(
            trace_id="trace_alpha_1",
            name="Customer Bot",
            start_time=datetime.utcnow(),
        ),
        project_id=proj.id,
    )

    assert trace.project_id == proj.id
    assert trace.project_name == "Project Alpha"

    # Query project and its traces relationship
    stmt = select(ProjectModel).options(selectinload(ProjectModel.traces)).where(ProjectModel.id == proj.id)
    res = await test_db.execute(stmt)
    loaded_proj = res.scalar_one()

    assert len(loaded_proj.traces) == 1
    assert loaded_proj.traces[0].trace_id == "trace_alpha_1"


@pytest.mark.asyncio
async def test_trace_creation_rejects_nonexistent_project_id(test_db):
    """Test that providing an invalid project_id raises ValueError."""
    trace_repo = TraceRepository(test_db)
    fake_project_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match=f"Project '{fake_project_id}' not found"):
        await trace_repo.create(
            TraceCreate(
                trace_id="trace_invalid_proj",
                name="Orphan Bot",
                start_time=datetime.utcnow(),
            ),
            project_id=fake_project_id,
        )


@pytest.mark.asyncio
async def test_trace_creation_auto_provisions_default_project(test_db):
    """Test that legacy SDK/test trace creation without project_id auto-associates with valid project."""
    trace_repo = TraceRepository(test_db)

    trace = await trace_repo.create(
        TraceCreate(
            trace_id="trace_auto_default",
            name="Default Bot",
            start_time=datetime.utcnow(),
        )
    )

    assert trace.project_id is not None

    # Verify that the project actually exists in the database
    proj_repo = ProjectRepository(test_db)
    proj = await proj_repo.get_by_id(trace.project_id)
    assert proj is not None
    assert proj.slug == "default"


@pytest.mark.asyncio
async def test_trace_list_filters_by_project_id(test_db):
    """Test that list_traces strictly isolates results by project_id."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)
    trace_repo = TraceRepository(test_db)

    org = await org_repo.create("Tenant Org", "tenant-org")
    proj_a = await proj_repo.create(org.id, "Project A", "proj-a")
    proj_b = await proj_repo.create(org.id, "Project B", "proj-b")

    # Create 2 traces in Project A and 1 in Project B
    await trace_repo.create(
        TraceCreate(trace_id="t_a_1", name="Bot A1", start_time=datetime.utcnow()),
        project_id=proj_a.id,
    )
    await trace_repo.create(
        TraceCreate(trace_id="t_a_2", name="Bot A2", start_time=datetime.utcnow()),
        project_id=proj_a.id,
    )
    await trace_repo.create(
        TraceCreate(trace_id="t_b_1", name="Bot B1", start_time=datetime.utcnow()),
        project_id=proj_b.id,
    )

    # Query Project A
    results_a = await trace_repo.list_traces(project_id=proj_a.id)
    assert len(results_a) == 2
    ids_a = {t[0].trace_id for t in results_a}
    assert ids_a == {"t_a_1", "t_a_2"}

    # Query Project B
    results_b = await trace_repo.list_traces(project_id=proj_b.id)
    assert len(results_b) == 1
    assert results_b[0][0].trace_id == "t_b_1"


@pytest.mark.asyncio
async def test_project_cascade_delete(test_db):
    """Test that deleting a project cascades and deletes associated traces and events."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)
    trace_repo = TraceRepository(test_db)
    event_repo = EventRepository(test_db)

    org = await org_repo.create("Cascade Org", "cascade-org")
    proj = await proj_repo.create(org.id, "Ephemeral Proj", "ephemeral-proj")

    trace = await trace_repo.create(
        TraceCreate(trace_id="trace_ephemeral", name="Short-lived", start_time=datetime.utcnow()),
        project_id=proj.id,
    )

    await event_repo.create(
        EventCreate(
            event_id="evt_ephemeral",
            trace_id="trace_ephemeral",
            event_type=EventType.AGENT_START,
            timestamp=datetime.utcnow(),
        )
    )

    # Delete project
    stmt = select(ProjectModel).where(ProjectModel.id == proj.id)
    res = await test_db.execute(stmt)
    proj_obj = res.scalar_one()
    await test_db.delete(proj_obj)
    await test_db.commit()

    # Verify trace is gone
    assert await trace_repo.exists("trace_ephemeral") is False

    # Verify event is gone
    evt = await event_repo.get_by_event_id("evt_ephemeral")
    assert evt is None


@pytest.mark.asyncio
async def test_trace_cannot_be_reassigned_to_different_project(test_db):
    """Test that updating an existing trace with a different project_id is rejected."""
    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)
    trace_repo = TraceRepository(test_db)

    org = await org_repo.create("Owner Org", "owner-org")
    p1 = await proj_repo.create(org.id, "Project 1", "proj-1")
    p2 = await proj_repo.create(org.id, "Project 2", "proj-2")

    # Create trace in Project 1
    await trace_repo.create(
        TraceCreate(trace_id="immutable_proj_trace", name="Bot 1", start_time=datetime.utcnow()),
        project_id=p1.id,
    )

    # Attempt to reassign to Project 2
    with pytest.raises(ValueError, match="cannot be reassigned"):
        await trace_repo.create(
            TraceCreate(trace_id="immutable_proj_trace", name="Bot 1 (Updated)", start_time=datetime.utcnow()),
            project_id=p2.id,
        )


@pytest.mark.asyncio
async def test_failure_embedding_cannot_differ_from_trace_project(test_db):
    """Test that failure embedding cannot be associated with a different project than its trace."""
    from app.db.repositories import FailureEmbeddingRepository

    org_repo = OrganizationRepository(test_db)
    proj_repo = ProjectRepository(test_db)
    trace_repo = TraceRepository(test_db)
    emb_repo = FailureEmbeddingRepository(test_db)

    org = await org_repo.create("Emb Org", "emb-org")
    p1 = await proj_repo.create(org.id, "Project Real", "proj-real")
    p2 = await proj_repo.create(org.id, "Project Imposter", "proj-imposter")

    await trace_repo.create(
        TraceCreate(trace_id="trace_emb_test", name="Bot Real", start_time=datetime.utcnow()),
        project_id=p1.id,
    )

    # Attempt to index embedding under Project Imposter
    with pytest.raises(ValueError, match="does not match parent trace project_id"):
        await emb_repo.upsert(
            trace_id="trace_emb_test",
            finding_id="f1",
            rule="explicit_error",
            category="error",
            severity="high",
            searchable_text="Sample text",
            embedding=[0.1] * 768,
            metadata={},
            project_id=p2.id,
        )

    # Omitted project_id automatically adopts parent trace's project_id
    emb = await emb_repo.upsert(
        trace_id="trace_emb_test",
        finding_id="f2",
        rule="explicit_error",
        category="error",
        severity="high",
        searchable_text="Sample text 2",
        embedding=[0.2] * 768,
        metadata={},
    )
    assert emb.project_id == p1.id

