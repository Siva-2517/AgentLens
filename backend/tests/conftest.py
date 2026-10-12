"""Test configuration and fixtures (Phase 19 Multi-Tenant)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, DEFAULT_PROJECT_ID
from app.main import app

from sqlalchemy.pool import StaticPool

# Test database URL - uses in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create test database engine with default multi-tenant fixture."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Seed default test org and test project so default_project_id FK is always satisfied in tests
        await conn.execute(text(f"""
            INSERT OR IGNORE INTO organizations (id, name, slug)
            VALUES ('{DEFAULT_PROJECT_ID}', 'Default Test Org', 'default-test-org');
        """))
        await conn.execute(text(f"""
            INSERT OR IGNORE INTO projects (id, organization_id, name, slug)
            VALUES ('{DEFAULT_PROJECT_ID}', '{DEFAULT_PROJECT_ID}', 'Default Project', 'default');
        """))

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_engine):
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
def override_get_db(test_db_session):
    """Override get_db dependency for testing."""
    async def _override_get_db():
        yield test_db_session

    return _override_get_db


@pytest.fixture(autouse=True)
def bypass_remote_init_db_in_tests(monkeypatch):
    """Bypass remote Neon migration in FastAPI lifespan for fast local unit tests."""
    async def _noop():
        pass
    monkeypatch.setattr("app.main.init_db", _noop)
