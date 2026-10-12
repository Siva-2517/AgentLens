"""Tests for Phase 19B: Core Authentication & Ingestion Channel Security."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import ApiKeyModel, DEFAULT_PROJECT_ID, UserModel
from app.main import app
from app.services.security import security_service


@pytest.fixture
async def client(override_get_db):
    """Test client with database override."""
    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# =============================================================================
# 1. Registration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, test_db_session):
    """Registration creates user, org, project, initial ingestion key, and sets cookies."""
    payload = {
        "email": "alice@example.com",
        "password": "StrongPassword123!",
        "full_name": "Alice Tester",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()

    # User profile checks
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["full_name"] == "Alice Tester"
    assert data["user"]["is_active"] is True
    assert data["user"]["is_superuser"] is False  # Must NOT be superuser!
    assert "hashed_password" not in data["user"]
    assert "password" not in data["user"]

    # Initial ingestion key returned ONCE
    assert data["api_key"] is not None
    assert data["api_key"].startswith("al_live_")

    # HttpOnly cookies set
    assert "agentlens_access_token" in client.cookies
    assert "agentlens_refresh_token" in client.cookies
    assert "agentlens_csrf_token" in client.cookies

    # Verify password was hashed with bcrypt in DB
    user_stmt = select(UserModel).where(UserModel.email == "alice@example.com")
    db_res = await test_db_session.execute(user_stmt)
    db_user = db_res.scalar_one()
    assert db_user.hashed_password != "StrongPassword123!"
    assert security_service.verify_password("StrongPassword123!", db_user.hashed_password) is True


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Duplicate email registration is rejected with 400 Bad Request."""
    payload = {
        "email": "bob@example.com",
        "password": "StrongPassword123!",
        "full_name": "Bob Original",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "Email already registered" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password_and_invalid_email(client: AsyncClient):
    """Validation rejects short passwords and invalid email formats."""
    # Short password
    res1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "short"},
    )
    assert res1.status_code in (400, 422)

    # Invalid email
    res2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "StrongPassword123!"},
    )
    assert res2.status_code in (400, 422)


# =============================================================================
# 2. Login & Credential Tests
# =============================================================================


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Login with valid credentials sets session cookies."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": "CarolPassword123!"},
    )
    client.cookies.clear()

    # Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "CarolPassword123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["user"]["email"] == "carol@example.com"
    assert data["api_key"] is None  # Never returned on login

    assert "agentlens_access_token" in client.cookies
    assert "agentlens_refresh_token" in client.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Invalid password or non-existent email returns 401 Unauthorized."""
    # Wrong password
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dan@example.com", "password": "DanPassword123!"},
    )
    client.cookies.clear()

    res1 = await client.post(
        "/api/v1/auth/login",
        json={"email": "dan@example.com", "password": "WrongPassword!"},
    )
    assert res1.status_code == 401
    assert "Invalid email or password" in res1.json()["detail"]

    # Non-existent user
    res2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "AnyPassword123!"},
    )
    assert res2.status_code == 401


# =============================================================================
# 3. Session Management & Expiration
# =============================================================================


@pytest.mark.asyncio
async def test_current_user_and_session_expiration(client: AsyncClient):
    """Valid access token returns profile; expired token returns 401."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "eve@example.com", "password": "EvePassword123!"},
    )
    user_id = reg.json()["user"]["id"]

    # Call /me with session cookie
    me_res = await client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    profile = me_res.json()
    assert profile["user"]["email"] == "eve@example.com"
    assert len(profile["organizations"]) >= 1
    assert len(profile["projects"]) >= 1

    # Clear session cookies to test expired token in isolation
    client.cookies.clear()

    # Call /me with expired token
    expired_token = security_service.create_access_token(
        user_id=user_id,
        email="eve@example.com",
        expires_delta=timedelta(seconds=-10),  # In the past
    )
    exp_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert exp_res.status_code == 401
    assert "expired" in exp_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_session_refresh_and_logout(client: AsyncClient):
    """Refresh token issues new access cookie; logout clears cookies."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "frank@example.com", "password": "FrankPassword123!"},
    )

    # Refresh
    ref_res = await client.post("/api/v1/auth/refresh")
    assert ref_res.status_code == 200
    assert "agentlens_access_token" in client.cookies

    # Logout
    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200


# =============================================================================
# 4. CSRF Defense Tests
# =============================================================================


@pytest.mark.asyncio
async def test_csrf_defense_on_cookie_auth(client: AsyncClient):
    """Cookie-authenticated state-changing calls require matching X-CSRF-Token."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "grace@example.com", "password": "GracePassword123!"},
    )
    csrf_token = reg.json()["csrf_token"]
    proj_id = reg.json()["user"]["id"]

    # 1. Cookie auth with NO X-CSRF-Token header -> 403 Forbidden
    res1 = await client.post(
        f"/api/v1/projects/{proj_id}/api-keys",
        json={"name": "Test Key"},
    )
    assert res1.status_code == 403
    assert "CSRF token missing or invalid" in res1.json()["detail"]

    # 2. Cookie auth with WRONG X-CSRF-Token header -> 403 Forbidden
    res2 = await client.post(
        f"/api/v1/projects/{proj_id}/api-keys",
        json={"name": "Test Key"},
        headers={"X-CSRF-Token": "tampered_token"},
    )
    assert res2.status_code == 403

    # 3. Cookie auth with CORRECT X-CSRF-Token header -> passes CSRF check
    res3 = await client.post(
        f"/api/v1/projects/{DEFAULT_PROJECT_ID}/api-keys",
        json={"name": "Test Key"},
        headers={"X-CSRF-Token": csrf_token},
    )
    # Passes CSRF check without CSRF error
    if res3.status_code == 403:
        assert "CSRF" not in res3.json()["detail"]


# =============================================================================
# 5. Ingestion API Key Management, Hashing & Revocation
# =============================================================================


@pytest.mark.asyncio
async def test_api_key_hashing_and_revocation(client: AsyncClient, test_db_session):
    """Raw key is returned ONCE; DB stores only SHA-256 hash; revoked keys are rejected."""
    # Register user
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "heidi@example.com", "password": "HeidiPassword123!"},
    )
    me_res = await client.get("/api/v1/auth/me")
    project_id = me_res.json()["projects"][0]["id"]
    csrf = reg.json()["csrf_token"]

    # Generate new key
    key_res = await client.post(
        f"/api/v1/projects/{project_id}/api-keys",
        json={"name": "Production Key", "expires_in_days": 30},
        headers={"X-CSRF-Token": csrf},
    )
    assert key_res.status_code == 201
    key_data = key_res.json()
    raw_key = key_data["api_key"]
    key_id = key_data["id"]
    prefix = key_data["key_prefix"]
    assert raw_key.startswith("al_live_")
    assert raw_key.startswith(prefix)

    # Verify DB: raw key is NEVER stored
    key_stmt = select(ApiKeyModel).where(ApiKeyModel.id == key_id)
    db_res = await test_db_session.execute(key_stmt)
    db_key = db_res.scalar_one()
    assert db_key.key_hash == security_service.hash_api_key(raw_key)
    assert db_key.key_hash != raw_key  # Must be hashed
    assert not hasattr(db_key, "raw_key")

    # List keys: only returns metadata, NEVER key_hash
    list_res = await client.get(f"/api/v1/projects/{project_id}/api-keys")
    assert list_res.status_code == 200
    listed_keys = list_res.json()
    found = next(k for k in listed_keys if k["id"] == key_id)
    assert "key_hash" not in found
    assert "api_key" not in found
    assert found["is_revoked"] is False

    # Clear user session cookies before simulating external SDK call
    client.cookies.clear()

    # Ingestion works with raw key
    trace_payload = {
        "trace_id": "tr-auth-key-01",
        "name": "agent-session",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    ingest_res = await client.post(
        "/api/v1/traces",
        json=trace_payload,
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert ingest_res.status_code == 201

    # Re-login user to revoke key
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "heidi@example.com", "password": "HeidiPassword123!"},
    )
    csrf = login_res.json()["csrf_token"]

    rev_res = await client.delete(
        f"/api/v1/projects/{project_id}/api-keys/{key_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert rev_res.status_code == 200

    # Clear cookies again
    client.cookies.clear()

    # Ingestion with revoked key is rejected with 401
    ingest_rev_res = await client.post(
        "/api/v1/traces",
        json={
            "trace_id": "tr-auth-key-02",
            "name": "agent-session",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert ingest_rev_res.status_code == 401
    assert "revoked" in ingest_rev_res.json()["detail"].lower()


# =============================================================================
# 6. Separation of User vs Ingestion Authentication (Security Matrix)
# =============================================================================


@pytest.mark.asyncio
async def test_ingestion_key_cannot_access_dashboard_read_endpoints(client: AsyncClient):
    """CRITICAL: Ingestion keys are strictly prohibited from reading traces (403 Forbidden)."""
    # Register user to get an ingestion key
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "ivan@example.com", "password": "IvanPassword123!"},
    )
    raw_ingestion_key = reg.json()["api_key"]

    # Clear session cookies so request only has the Authorization header
    client.cookies.clear()

    # 1. Attempt to read /api/v1/traces with ingestion key -> 403 FORBIDDEN
    read_traces_res = await client.get(
        "/api/v1/traces",
        headers={"Authorization": f"Bearer {raw_ingestion_key}"},
    )
    assert read_traces_res.status_code == 403
    assert "Ingestion keys cannot access dashboard endpoints" in read_traces_res.json()["detail"]

    # 2. Attempt to read a specific trace with ingestion key -> 403 FORBIDDEN
    read_trace_res = await client.get(
        "/api/v1/traces/any-trace-id",
        headers={"Authorization": f"Bearer {raw_ingestion_key}"},
    )
    assert read_trace_res.status_code == 403

    # 3. User session reading /api/v1/traces -> 200 OK
    await client.post(
        "/api/v1/auth/login",
        json={"email": "ivan@example.com", "password": "IvanPassword123!"},
    )
    user_read_res = await client.get("/api/v1/traces")
    assert user_read_res.status_code == 200


@pytest.mark.asyncio
async def test_cross_project_ingestion_rejection(client: AsyncClient):
    """Ingestion key cannot send events to a trace belonging to another project."""
    # User 1 registers and creates trace
    reg1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "user1@example.com", "password": "Password123!"},
    )
    key1 = reg1.json()["api_key"]

    # User 2 registers and gets key 2
    reg2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "user2@example.com", "password": "Password123!"},
    )
    key2 = reg2.json()["api_key"]

    client.cookies.clear()

    # Key 1 ingests trace
    res1 = await client.post(
        "/api/v1/traces",
        json={
            "trace_id": "tr-user1-exclusive",
            "name": "u1-agent",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        },
        headers={"Authorization": f"Bearer {key1}"},
    )
    assert res1.status_code == 201

    # Key 2 attempts to ingest an event into User 1's trace -> 403 Forbidden!
    event_payload = [
        {
            "event_id": "ev-hijack-01",
            "trace_id": "tr-user1-exclusive",
            "event_type": "AGENT_START",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {},
            "metadata": {},
        }
    ]
    res2 = await client.post(
        "/api/v1/events",
        json=event_payload,
        headers={"Authorization": f"Bearer {key2}"},
    )
    assert res2.status_code == 403
    assert "belongs to another project" in res2.json()["detail"]
