"""Tests for database models and repositories."""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.models import TraceModel, EventModel, Base
from app.db.repositories import TraceRepository, EventRepository
from app.models.trace import TraceCreate
from app.models.event import EventCreate, EventType


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


# Trace Model Tests

@pytest.mark.asyncio
async def test_create_trace_model(test_db):
    """Test creating a trace model."""
    trace = TraceModel(
        trace_id="trace_test_123",
        name="test-agent",
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
    assert trace.name == "test-agent"
    assert trace.project_name == "test-project"
    assert trace.status == "running"
    assert trace.metadata_ == {"key": "value"}
    assert trace.created_at is not None


@pytest.mark.asyncio
async def test_trace_model_relationships(test_db):
    """Test trace to events relationship."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    trace = TraceModel(
        trace_id="trace_rel_123",
        name="test-agent",
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
    stmt = select(TraceModel).options(selectinload(TraceModel.events)).where(
        TraceModel.trace_id == "trace_rel_123"
    )
    result = await test_db.execute(stmt)
    trace = result.scalar_one()

    # Access relationship
    assert len(trace.events) == 2


# Event Model Tests

@pytest.mark.asyncio
async def test_create_event_model(test_db):
    """Test creating an event model."""
    # Create trace first
    trace = TraceModel(
        trace_id="trace_evt_123",
        name="test-agent",
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
async def test_event_with_parent(test_db):
    """Test event with parent_event_id."""
    trace = TraceModel(
        trace_id="trace_parent_123",
        name="test-agent",
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


# Trace Repository Tests

@pytest.mark.asyncio
async def test_trace_repository_create(test_db):
    """Test creating trace via repository."""
    repo = TraceRepository(test_db)

    trace = TraceCreate(
        trace_id="trace_repo_123",
        name="repo-test-agent",
        start_time=datetime.utcnow(),
        status="running",
        metadata={"test": "data"},
    )

    db_trace = await repo.create(trace, project_name="test-project")
    await test_db.commit()

    assert db_trace.trace_id == "trace_repo_123"
    assert db_trace.name == "repo-test-agent"
    assert db_trace.project_name == "test-project"
    assert db_trace.status == "running"


@pytest.mark.asyncio
async def test_trace_repository_get_by_trace_id(test_db):
    """Test getting trace by trace_id."""
    repo = TraceRepository(test_db)

    trace = TraceCreate(
        trace_id="trace_get_123",
        name="get-test-agent",
        start_time=datetime.utcnow(),
        status="running",
        metadata={},
    )

    await repo.create(trace)
    await test_db.commit()

    found_trace = await repo.get_by_trace_id("trace_get_123")

    assert found_trace is not None
    assert found_trace.trace_id == "trace_get_123"
    assert found_trace.name == "get-test-agent"


@pytest.mark.asyncio
async def test_trace_repository_exists(test_db):
    """Test checking if trace exists."""
    repo = TraceRepository(test_db)

    trace = TraceCreate(
        trace_id="trace_exists_123",
        name="exists-test-agent",
        start_time=datetime.utcnow(),
        status="running",
        metadata={},
    )

    await repo.create(trace)
    await test_db.commit()

    assert await repo.exists("trace_exists_123") is True
    assert await repo.exists("nonexistent") is False


# Event Repository Tests

@pytest.mark.asyncio
async def test_event_repository_create(test_db):
    """Test creating event via repository."""
    # Create trace first
    trace_repo = TraceRepository(test_db)
    trace = TraceCreate(
        trace_id="trace_evt_repo_123",
        name="test-agent",
        start_time=datetime.utcnow(),
        status="running",
        metadata={},
    )
    await trace_repo.create(trace)
    await test_db.commit()

    # Create event
    event_repo = EventRepository(test_db)
    event = EventCreate(
        event_id="evt_repo_123",
        trace_id="trace_evt_repo_123",
        event_type=EventType.LLM_CALL,
        timestamp=datetime.utcnow(),
        data={"model": "gpt-4"},
        metadata={},
    )

    db_event = await event_repo.create(event, project_name="test-project")
    await test_db.commit()

    assert db_event.event_id == "evt_repo_123"
    assert db_event.trace_id == "trace_evt_repo_123"
    assert db_event.event_type == "LLM_CALL"
    assert db_event.data == {"model": "gpt-4"}


@pytest.mark.asyncio
async def test_event_repository_get_by_trace_id(test_db):
    """Test getting events by trace_id."""
    # Create trace
    trace_repo = TraceRepository(test_db)
    trace = TraceCreate(
        trace_id="trace_get_events_123",
        name="test-agent",
        start_time=datetime.utcnow(),
        status="running",
        metadata={},
    )
    await trace_repo.create(trace)
    await test_db.commit()

    # Create multiple events
    event_repo = EventRepository(test_db)

    event1 = EventCreate(
        event_id="evt_1",
        trace_id="trace_get_events_123",
        event_type=EventType.AGENT_START,
        timestamp=datetime.utcnow(),
        data={},
        metadata={},
    )

    event2 = EventCreate(
        event_id="evt_2",
        trace_id="trace_get_events_123",
        event_type=EventType.LLM_CALL,
        timestamp=datetime.utcnow(),
        data={},
        metadata={},
    )

    await event_repo.create(event1)
    await event_repo.create(event2)
    await test_db.commit()

    # Get events
    events = await event_repo.get_by_trace_id("trace_get_events_123")

    assert len(events) == 2
    assert events[0].event_id in ["evt_1", "evt_2"]
    assert events[1].event_id in ["evt_1", "evt_2"]


@pytest.mark.asyncio
async def test_event_repository_create_batch(test_db):
    """Test creating multiple events in batch."""
    # Create trace
    trace_repo = TraceRepository(test_db)
    trace = TraceCreate(
        trace_id="trace_batch_123",
        name="test-agent",
        start_time=datetime.utcnow(),
        status="running",
        metadata={},
    )
    await trace_repo.create(trace)
    await test_db.commit()

    # Create batch of events
    event_repo = EventRepository(test_db)

    events = [
        EventCreate(
            event_id=f"evt_batch_{i}",
            trace_id="trace_batch_123",
            event_type=EventType.LLM_CALL,
            timestamp=datetime.utcnow(),
            data={},
            metadata={},
        )
        for i in range(5)
    ]

    db_events = await event_repo.create_batch(events)
    await test_db.commit()

    assert len(db_events) == 5
    assert all(e.trace_id == "trace_batch_123" for e in db_events)
