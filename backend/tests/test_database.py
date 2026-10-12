"""Tests for database models and repositories (Phase 19 Multi-Tenant)."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
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

# Test database URL - uses in-memory SQLite for testing
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


@pytest.fixture
async def sample_project(test_db):
    """Fixture providing a persisted test organization and project."""
    org = OrganizationModel(
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
    )
    test_db.add(org)
    await test_db.flush()

    project = ProjectModel(
        organization_id=org.id,
        name="Test Project",
        slug=f"test-project-{uuid.uuid4().hex[:8]}",
        description="Sample project for testing",
    )
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


# ==============================================================================
# Multi-Tenant Model Tests (Phase 19A)
# ==============================================================================

@pytest.mark.asyncio
async def test_create_user_model(test_db):
    """Test creating and retrieving a user model."""
    user = UserModel(
        email="developer@test.com",
        hashed_password="hashed_secret_pw",
        full_name="AgentLens Developer",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    assert user.id is not None
    assert user.email == "developer@test.com"
    assert user.hashed_password == "hashed_secret_pw"
    assert user.full_name == "AgentLens Developer"
    assert user.is_active is True
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_email_unique_constraint(test_db):
    """Test that email addresses must be unique."""
    u1 = UserModel(email="unique@test.com", hashed_password="pw1")
    test_db.add(u1)
    await test_db.commit()

    u2 = UserModel(email="unique@test.com", hashed_password="pw2")
    test_db.add(u2)
    with pytest.raises(Exception):
        await test_db.commit()


@pytest.mark.asyncio
async def test_create_organization_and_membership(test_db):
    """Test organization creation, membership role, and relationships."""
    user = UserModel(email="org_owner@test.com", hashed_password="pw")
    test_db.add(user)
    await test_db.flush()

    org = OrganizationModel(name="Acme Corp", slug="acme-corp")
    test_db.add(org)
    await test_db.flush()

    member = OrganizationMemberModel(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
    )
    test_db.add(member)
    await test_db.commit()

    # Load with relationship
    stmt = (
        select(OrganizationModel)
        .options(selectinload(OrganizationModel.members))
        .where(OrganizationModel.id == org.id)
    )
    res = await test_db.execute(stmt)
    loaded_org = res.scalar_one()

    assert loaded_org.name == "Acme Corp"
    assert len(loaded_org.members) == 1
    assert loaded_org.members[0].role == "owner"
    assert loaded_org.members[0].user_id == user.id


@pytest.mark.asyncio
async def test_create_project_and_api_key(test_db, sample_project):
    """Test project model and project-scoped API key creation."""
    api_key = ApiKeyModel(
        project_id=sample_project.id,
        name="Development Agent Key",
        key_prefix="al_live_abcd",
        key_hash="hash_value_1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        key_type="ingestion",
        scopes=["ingest"],
    )
    test_db.add(api_key)
    await test_db.commit()
    await test_db.refresh(api_key)

    assert api_key.id is not None
    assert api_key.project_id == sample_project.id
    assert api_key.key_prefix == "al_live_abcd"
    assert api_key.is_revoked is False
    assert api_key.created_at is not None


# ==============================================================================
# Trace & Event Model Tests (Updated with Project Ownership)
# ==============================================================================

@pytest.mark.asyncio
async def test_create_trace_model(test_db, sample_project):
    """Test creating a trace model with required project_id."""
    trace = TraceModel(
        trace_id="trace_test_123",
        name="test-agent",
        project_id=sample_project.id,
        project_name="test-project",
        start_time=datetime.utcnow(),
        status="running",
        metadata_={"key": "value"},
    )

    test_db.add(trace)
    await test_db.commit()
    await test_db.refresh(trace)

    assert trace.id is not None
    assert trace.trace_id == "trace_test_123"
    assert trace.project_id == sample_project.id
    assert trace.name == "test-agent"
    assert trace.project_name == "test-project"
    assert trace.status == "running"
    assert trace.metadata_ == {"key": "value"}
    assert trace.created_at is not None


@pytest.mark.asyncio
async def test_trace_model_relationships(test_db, sample_project):
    """Test trace to events relationship."""
    trace = TraceModel(
        trace_id="trace_rel_123",
        name="test-agent",
        project_id=sample_project.id,
        start_time=datetime.utcnow(),
        status="running",
        metadata_={},
    )

    event1 = EventModel(
        event_id="evt_1",
        trace_id="trace_rel_123",
        event_type="LLM_CALL",
        timestamp=datetime.utcnow(),
        data={},
        metadata_={},
    )

    event2 = EventModel(
        event_id="evt_2",
        trace_id="trace_rel_123",
        event_type="LLM_RESPONSE",
        timestamp=datetime.utcnow(),
        data={},
        metadata_={},
    )

    test_db.add(trace)
    test_db.add(event1)
    test_db.add(event2)
    await test_db.commit()

    # Load trace with events eagerly
    stmt = (
        select(TraceModel)
        .options(selectinload(TraceModel.events))
        .where(TraceModel.trace_id == "trace_rel_123")
    )
    result = await test_db.execute(stmt)
    loaded_trace = result.scalar_one()

    assert len(loaded_trace.events) == 2


@pytest.mark.asyncio
async def test_create_event_model(test_db, sample_project):
    """Test creating an event model."""
    trace = TraceModel(
        trace_id="trace_evt_123",
        name="test-agent",
        project_id=sample_project.id,
        start_time=datetime.utcnow(),
        status="running",
        metadata_={},
    )
    test_db.add(trace)
    await test_db.commit()

    # Create event
    event = EventModel(
        event_id="evt_test_123",
        trace_id="trace_evt_123",
        parent_event_id=None,
        event_type="LLM_CALL",
        timestamp=datetime.utcnow(),
        data={"model": "gpt-4"},
        metadata_={"source": "sdk"},
    )

    test_db.add(event)
    await test_db.commit()
    await test_db.refresh(event)

    assert event.id is not None
    assert event.event_id == "evt_test_123"
    assert event.trace_id == "trace_evt_123"
    assert event.parent_event_id is None
    assert event.event_type == "LLM_CALL"
    assert event.data == {"model": "gpt-4"}
    assert event.metadata_ == {"source": "sdk"}
    assert event.created_at is not None


@pytest.mark.asyncio
async def test_event_with_parent(test_db, sample_project):
    """Test event with parent_event_id."""
    trace = TraceModel(
        trace_id="trace_parent_123",
        name="test-agent",
        project_id=sample_project.id,
        start_time=datetime.utcnow(),
        status="running",
        metadata_={},
    )
    test_db.add(trace)
    await test_db.commit()

    parent_event = EventModel(
        event_id="evt_parent",
        trace_id="trace_parent_123",
        event_type="TOOL_CALL",
        timestamp=datetime.utcnow(),
        data={},
        metadata_={},
    )

    child_event = EventModel(
        event_id="evt_child",
        trace_id="trace_parent_123",
        parent_event_id="evt_parent",
        event_type="LLM_CALL",
        timestamp=datetime.utcnow(),
        data={},
        metadata_={},
    )

    test_db.add(parent_event)
    test_db.add(child_event)
    await test_db.commit()
    await test_db.refresh(child_event)

    assert child_event.parent_event_id == "evt_parent"


# ==============================================================================
# Trace Repository Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_trace_repo_create_and_get(test_db):
    """Test creating and retrieving a trace via repository (auto-provisions project)."""
    repo = TraceRepository(test_db)
    trace_data = TraceCreate(
        trace_id="repo_trace_123",
        name="repo-test",
        start_time=datetime.utcnow(),
        status="running",
    )

    trace = await repo.create(trace_data, project_name="my-project")
    assert trace.trace_id == "repo_trace_123"
    assert trace.project_id is not None
    assert trace.project_name == "my-project"

    retrieved = await repo.get_by_trace_id("repo_trace_123")
    assert retrieved is not None
    assert retrieved.trace_id == "repo_trace_123"
    assert retrieved.project_id == trace.project_id


@pytest.mark.asyncio
async def test_trace_repo_exists(test_db):
    """Test checking if a trace exists."""
    repo = TraceRepository(test_db)
    trace_data = TraceCreate(
        trace_id="exists_test",
        name="test",
        start_time=datetime.utcnow(),
    )
    await repo.create(trace_data)

    assert await repo.exists("exists_test") is True
    assert await repo.exists("nonexistent") is False


@pytest.mark.asyncio
async def test_trace_repo_get_with_events(test_db):
    """Test getting trace with loaded events."""
    trace_repo = TraceRepository(test_db)
    event_repo = EventRepository(test_db)

    await trace_repo.create(
        TraceCreate(
            trace_id="trace_with_events",
            name="test",
            start_time=datetime.utcnow(),
        )
    )

    await event_repo.create(
        EventCreate(
            event_id="e1",
            trace_id="trace_with_events",
            event_type=EventType.LLM_CALL,
            timestamp=datetime.utcnow(),
        )
    )

    trace = await trace_repo.get_with_events("trace_with_events")
    assert trace is not None
    assert len(trace.events) == 1
    assert trace.events[0].event_id == "e1"


# ==============================================================================
# Event Repository Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_event_repo_create_batch(test_db):
    """Test creating batch of events."""
    trace_repo = TraceRepository(test_db)
    event_repo = EventRepository(test_db)

    await trace_repo.create(
        TraceCreate(
            trace_id="batch_trace",
            name="test",
            start_time=datetime.utcnow(),
        )
    )

    events = [
        EventCreate(
            event_id=f"batch_e_{i}",
            trace_id="batch_trace",
            event_type=EventType.TOOL_CALL,
            timestamp=datetime.utcnow(),
        )
        for i in range(5)
    ]

    db_events = await event_repo.create_batch(events)
    assert len(db_events) == 5

    count = await event_repo.count_by_trace_id("batch_trace")
    assert count == 5
