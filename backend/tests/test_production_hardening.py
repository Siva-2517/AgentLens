"""Targeted Security and Production Hardening Tests (Phase 20B).

Validates:
1. Fail-closed Settings validation when ENVIRONMENT=production:
   - Rejection of default or known example JWT_SECRET_KEY.
   - Rejection of short (< 32 char) JWT secrets.
   - Rejection of low-entropy JWT secrets (Shannon entropy < 3.5).
   - Acceptance of high-entropy JWT secrets (>= 32 chars).
   - Rejection of COOKIE_SECURE=False in production.
   - Rejection of wildcard '*' in CORS_ORIGINS in production.
   - Rejection of insecure 'http://' in CORS_ORIGINS in production.
   - Rejection of placeholder or non-SSL database URLs in production.
   - Rejection of development keys in AGENTLENS_API_KEYS in production.
2. Defense-in-depth Origin header validation on cookie-authenticated state-changing requests.
3. Health check endpoint distinguishing application health from database and Redis.
4. Production WebSocket gate rejecting legacy dev keys.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app


def test_production_rejects_default_jwt_secret():
    """Verify production startup fails closed if default JWT secret is used."""
    with pytest.raises(ValidationError, match="Default or known example JWT_SECRET_KEY"):
        Settings(
            environment="production",
            jwt_secret_key="agentlens_super_secret_jwt_hmac_signing_key_32_bytes_min!",
            cookie_secure=True,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )


def test_production_rejects_short_jwt_secret():
    """Verify production startup fails closed if JWT secret is shorter than 32 chars."""
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            environment="production",
            jwt_secret_key="short_secret_under_32_chars!",
            cookie_secure=True,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )


def test_production_rejects_low_entropy_jwt_secret():
    """Verify production startup fails closed if JWT secret lacks cryptographic entropy."""
    # 32 characters of repeated characters has near-zero Shannon entropy
    with pytest.raises(ValidationError, match="insufficient cryptographic entropy"):
        Settings(
            environment="production",
            jwt_secret_key="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            cookie_secure=True,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )


def test_production_accepts_valid_high_entropy_jwt_secret():
    """Verify production settings pass with strong secret, HTTPS cookies, and explicit CORS."""
    # 48-char random urlsafe string
    valid_secret = "k7Z9p_L2mQ4vX8yR1wT3bN6cM0jF5hG8sD4aE7uI2oP9qW3e"
    prod_settings = Settings(
        environment="production",
        jwt_secret_key=valid_secret,
        cookie_secure=True,
        cors_origins="https://app.agentlens.ai,https://admin.agentlens.ai",
        database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
        agentlens_api_keys="",
        groq_api_key="gsk_test_groq_production_key_123",
        gemini_api_key="AIzaSy_test_gemini_key_123",
    )
    assert prod_settings.environment == "production"
    assert prod_settings.cookie_secure is True


def test_production_rejects_insecure_cookies():
    """Verify production startup fails closed if COOKIE_SECURE is False."""
    valid_secret = "k7Z9p_L2mQ4vX8yR1wT3bN6cM0jF5hG8sD4aE7uI2oP9qW3e"
    with pytest.raises(ValidationError, match="COOKIE_SECURE must be True in production"):
        Settings(
            environment="production",
            jwt_secret_key=valid_secret,
            cookie_secure=False,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )


def test_production_rejects_wildcard_cors():
    """Verify production startup fails closed if CORS_ORIGINS contains wildcard '*'."""
    valid_secret = "k7Z9p_L2mQ4vX8yR1wT3bN6cM0jF5hG8sD4aE7uI2oP9qW3e"
    with pytest.raises(ValidationError, match="Wildcard '\\*' in CORS_ORIGINS is prohibited"):
        Settings(
            environment="production",
            jwt_secret_key=valid_secret,
            cookie_secure=True,
            cors_origins="*",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )


def test_production_rejects_insecure_http_cors():
    """Verify production startup fails closed if CORS_ORIGINS contains plaintext http://."""
    valid_secret = "k7Z9p_L2mQ4vX8yR1wT3bN6cM0jF5hG8sD4aE7uI2oP9qW3e"
    with pytest.raises(ValidationError, match="Insecure HTTP origin"):
        Settings(
            environment="production",
            jwt_secret_key=valid_secret,
            cookie_secure=True,
            cors_origins="http://dashboard.agentlens.ai",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )


def test_production_rejects_insecure_db_url():
    """Verify production startup fails closed if DATABASE_URL is placeholder or non-SSL."""
    valid_secret = "k7Z9p_L2mQ4vX8yR1wT3bN6cM0jF5hG8sD4aE7uI2oP9qW3e"
    with pytest.raises(ValidationError, match="Example placeholder DATABASE_URL"):
        Settings(
            environment="production",
            jwt_secret_key=valid_secret,
            cookie_secure=True,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:password@ep-example.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
        )

    with pytest.raises(ValidationError, match="require TLS/SSL"):
        Settings(
            environment="production",
            jwt_secret_key=valid_secret,
            cookie_secure=True,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:pass@ep-prod.neon.tech/agentlens",
            agentlens_api_keys="",
        )


def test_production_rejects_dev_keys_in_api_keys():
    """Verify production startup fails closed if dev test keys are configured."""
    valid_secret = "k7Z9p_L2mQ4vX8yR1wT3bN6cM0jF5hG8sD4aE7uI2oP9qW3e"
    with pytest.raises(ValidationError, match="Development test keys.*cannot be configured"):
        Settings(
            environment="production",
            jwt_secret_key=valid_secret,
            cookie_secure=True,
            cors_origins="https://app.agentlens.ai",
            database_url="postgresql://user:pass@ep-real.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="test_api_key_123,prod_key",
        )


@pytest.mark.asyncio
async def test_health_check_distinguishes_service_status():
    """Verify /health endpoint returns healthy status and service diagnostics."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    with patch("app.db.session.engine", mock_engine), \
         patch("app.services.realtime_publisher.realtime_publisher._get_redis", AsyncMock(return_value=mock_redis)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert "services" in data
            assert "database" in data["services"]
            assert "redis" in data["services"]


@pytest.mark.asyncio
async def test_origin_header_validation_rejects_unauthorized_cross_origin(override_get_db):
    """Verify Origin validation rejects cookie-authenticated state-changing requests from foreign origins."""
    from app.db.session import get_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register user to obtain cookies
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "origintest@example.com",
                    "password": "SecurePassword123!",
                    "full_name": "Origin Tester",
                },
            )
            assert reg_resp.status_code == 201
            csrf_token = reg_resp.json()["csrf_token"]

            # Attempt state-changing request with foreign Origin header (evil.com)
            resp = await client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/api-keys",
                json={"name": "Test Key", "scopes": ["ingest"]},
                headers={
                    "X-CSRF-Token": csrf_token,
                    "Origin": "https://evil-attacker.com",
                },
            )
            # Must be rejected with 403 Forbidden
            assert resp.status_code == 403
            assert "Origin not allowed" in resp.json()["detail"]

            # Attempt with matching configured Origin (localhost:5173 is in default cors_origins)
            valid_resp = await client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/api-keys",
                json={"name": "Valid Origin Key", "scopes": ["ingest"]},
                headers={
                    "X-CSRF-Token": csrf_token,
                    "Origin": "http://localhost:5173",
                },
            )
            # Origin accepted (reaches project auth layer)
            assert valid_resp.status_code != 403 or "Origin not allowed" not in valid_resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_websocket_rejects_legacy_dev_key_in_production(monkeypatch):
    """Verify WebSocket handshake strictly rejects legacy dev keys when ENVIRONMENT=production."""
    from app.api.v1.websocket import _authenticate_websocket
    from app.config import settings
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr(settings, "environment", "production")

    mock_ws = MagicMock()
    mock_ws.cookies = {}
    mock_ws.headers = {}
    mock_db = AsyncMock()

    # Attempt authenticating with legacy dev key in production
    principal = await _authenticate_websocket(
        websocket=mock_ws,
        token_param="test_api_key_123",
        api_key_param=None,
        db=mock_db,
    )
    assert principal is None, "Legacy dev key must fail closed in production environment"
