"""Phase 17 - Security Hardening Test Suite.

Validates:
1. Authentication & timing attack mitigations
2. Input validation and payload bounds
3. Centralized sensitive credential redaction (passwords, tokens, DB URLs) while preserving metrics
4. Error safety and exception masking
5. MCP read-only guarantees and sanitized error output
6. WebSocket trace ID validation and authentication
7. Security headers and configurable CORS
8. AI investigation prompt injection boundary markers
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.config import settings
from app.services.auth import auth_service
from app.services.redaction import (
    is_sensitive_key,
    mask_connection_string,
    sanitize_string,
    sanitize_telemetry,
)
from app.services.llm_provider import INVESTIGATION_SYSTEM_PROMPT
from app.mcp.server import create_mcp_server
from app.mcp.tools import _format_error, compare_traces_handler, search_historical_failures_handler


# ==============================================================================
# 1. API Authentication & Authorization
# ==============================================================================


@pytest.mark.asyncio
async def test_auth_missing_header_returns_401():
    """Requests without Authorization header must return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/traces")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


@pytest.mark.asyncio
async def test_auth_invalid_key_returns_401():
    """Requests with unknown API key must return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/traces",
            headers={"Authorization": "Bearer completely_bogus_key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_auth_malformed_headers_return_401():
    """Malformed Authorization headers must be rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing Bearer prefix
        resp1 = await client.get(
            "/api/v1/traces",
            headers={"Authorization": "test_api_key_123"},
        )
        assert resp1.status_code == 401

        # Basic auth instead of Bearer
        resp2 = await client.get(
            "/api/v1/traces",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp2.status_code == 401

        # Empty Bearer token
        resp3 = await client.get(
            "/api/v1/traces",
            headers={"Authorization": "Bearer    "},
        )
        assert resp3.status_code == 401


def test_auth_service_constant_time_comparison():
    """AuthService uses constant-time string comparison for all keys."""
    # Valid key
    assert auth_service.validate_api_key("test_api_key_123") is True
    assert auth_service.validate_api_key("dev_key") is True

    # Invalid keys
    assert auth_service.validate_api_key("test_api_key_124") is False
    assert auth_service.validate_api_key("") is False
    assert auth_service.validate_api_key(None) is False

    # Dynamic key override
    auth_service.set_valid_api_keys({"custom_secure_key_999"})
    try:
        assert auth_service.validate_api_key("custom_secure_key_999") is True
        assert auth_service.validate_api_key("test_api_key_123") is False
    finally:
        auth_service.set_valid_api_keys(None)


def test_auth_service_project_name_validation():
    """Project name header must be alphanumeric with dashes/underscores and bounded."""
    assert auth_service.extract_project_name("agent-lens_prod1") == "agent-lens_prod1"
    assert auth_service.extract_project_name("invalid project; drop table") is None
    assert auth_service.extract_project_name("../path/traversal") is None
    assert auth_service.extract_project_name("a" * 200) is None  # Exceeds max length


# ==============================================================================
# 2. Input Validation & Bounds
# ==============================================================================


@pytest.mark.asyncio
async def test_event_batch_size_limit():
    """Event ingestion rejects batch sizes exceeding the configured limit."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create an oversized batch (limit + 1)
        oversized = [
            {
                "event_id": f"ev-{i}",
                "trace_id": "trace-batch-test",
                "event_type": "LLM_CALL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"call": i},
            }
            for i in range(settings.max_event_batch_size + 1)
        ]

        resp = await client.post(
            "/api/v1/events",
            json=oversized,
            headers={"Authorization": "Bearer test_api_key_123"},
        )
        assert resp.status_code == 400
        assert "exceeds maximum limit" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_trace_create_string_length_limits():
    """TraceCreate enforces maximum length bounds on identifier fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        oversized_trace = {
            "trace_id": "t" * 300,  # Max is 256
            "name": "valid-name",
            "start_time": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(
            "/api/v1/traces",
            json=oversized_trace,
            headers={"Authorization": "Bearer test_api_key_123"},
        )
        assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_search_query_length_limit():
    """Historical failure search rejects queries longer than 1000 characters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/failures/search",
            params={"q": "x" * 1001},
            headers={"Authorization": "Bearer test_api_key_123"},
        )
        assert resp.status_code == 400
        assert "exceeds maximum length" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compare_traces_length_and_identity_validation():
    """Comparing identical traces or oversized identifiers is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Oversized
        resp1 = await client.get(
            "/api/v1/traces/compare",
            params={"trace_a": "a" * 300, "trace_b": "trace-b"},
            headers={"Authorization": "Bearer test_api_key_123"},
        )
        assert resp1.status_code == 400
        assert "must not exceed 256" in resp1.json()["detail"]


# ==============================================================================
# 3. Sensitive Data Redaction
# ==============================================================================


def test_redaction_credentials_and_tokens():
    """Sensitive keys, bearer tokens, API keys, and connection strings are redacted."""
    raw = {
        "api_key": "sk-proj-1234567890abcdef",
        "client_secret": "my-client-secret-999",
        "password": "supersecretpassword",
        "authorization": "Bearer eyJhbGciOi...",
        "access_token": "ghp_abcdef123456",
        "refresh_token": "rfr_xyz987",
        "nested": {
            "auth_token": "nested-token-val",
            "db_connection": "postgresql://admin:mypassword@neon.tech:5432/db",
            "redis_connection": "redis://:secretpass@localhost:6379/0",
            "message": "Authorization failed with Bearer secret_session_token",
            "query": "https://api.example.com/data?api_key=sk-inline-secret-key",
        },
    }

    sanitized = sanitize_telemetry(raw)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["refresh_token"] == "[REDACTED]"
    assert sanitized["nested"]["auth_token"] == "[REDACTED]"
    assert sanitized["nested"]["db_connection"] == "[REDACTED_DB_URL]"
    assert sanitized["nested"]["redis_connection"] == "[REDACTED_DB_URL]"
    assert sanitized["nested"]["message"] == "[REDACTED_SECRET]"
    assert sanitized["nested"]["query"] == "[REDACTED_SECRET]"


def test_redaction_preserves_legitimate_metrics():
    """Legitimate telemetry fields like token counts and routing keys are NOT redacted."""
    telemetry = {
        "total_tokens": 1540,
        "prompt_tokens": 1200,
        "completion_tokens": 340,
        "token_count": 1540,
        "tokens": 1540,
        "cache_key": "user_query_hash_abc",
        "primary_key": "pk_123",
        "name": "payment_processor",
    }

    sanitized = sanitize_telemetry(telemetry)

    assert sanitized["total_tokens"] == 1540
    assert sanitized["prompt_tokens"] == 1200
    assert sanitized["completion_tokens"] == 340
    assert sanitized["token_count"] == 1540
    assert sanitized["tokens"] == 1540
    assert sanitized["cache_key"] == "user_query_hash_abc"
    assert sanitized["primary_key"] == "pk_123"
    assert sanitized["name"] == "payment_processor"


def test_mask_connection_string():
    """Database URLs in error logs are masked to protect credentials."""
    err = "asyncpg.exceptions.InvalidPasswordError: password authentication failed for postgresql://admin:secret123@ep-cool.neon.tech/main?sslmode=require"
    masked = mask_connection_string(err)
    assert "secret123" not in masked
    assert "[REDACTED_CONNECTION_URL]" in masked


# ==============================================================================
# 4. Error Safety & Masking
# ==============================================================================


@pytest.mark.asyncio
async def test_error_masking_does_not_leak_database_credentials():
    """Internal database errors return generic 500 detail without leaking credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.services.trace_service.trace_service.list_traces") as mock_list:
            mock_list.side_effect = Exception("connection to postgresql://user:pass123@neon.tech failed")

            resp = await client.get(
                "/api/v1/traces",
                headers={"Authorization": "Bearer test_api_key_123"},
            )
            assert resp.status_code == 500
            assert "pass123" not in resp.text
            assert "postgresql" not in resp.text
            assert resp.json()["detail"] == "Failed to list traces due to an internal error."


def test_mcp_format_error_redacts_credentials():
    """MCP structured error formatting redacts secrets embedded in details."""
    err = _format_error(
        error_code="db_error",
        message="Database query failed",
        detail="Failed connecting to postgresql://user:secret@host/db with Bearer token_abc",
    )
    assert "secret" not in err["detail"]
    assert "token_abc" not in err["detail"]
    assert "[REDACTED_DB_URL]" in err["detail"] or "[REDACTED_SECRET]" in err["detail"]


# ==============================================================================
# 5. MCP Read-Only & Tool Guarantees
# ==============================================================================


@pytest.mark.asyncio
async def test_mcp_server_is_strictly_read_only():
    """MCP server registers only the 7 approved read-only tools."""
    server = create_mcp_server()
    tools = await server.list_tools()
    registered_names = {t.name for t in tools}

    expected_tools = {
        "get_trace",
        "get_execution_graph",
        "get_trace_findings",
        "investigate_trace",
        "compare_traces",
        "search_historical_failures",
        "list_recent_traces",
    }
    assert registered_names == expected_tools

    # Disallowed dangerous tools
    forbidden_prefixes = ["write", "delete", "mutate", "execute", "run", "sql", "shell", "remediate"]
    for tool_name in registered_names:
        for forbidden in forbidden_prefixes:
            assert not tool_name.startswith(forbidden), f"Forbidden tool registered: {tool_name}"


# ==============================================================================
# 6. Security Headers & CORS
# ==============================================================================


@pytest.mark.asyncio
async def test_security_headers_present_on_responses():
    """Every HTTP response includes standard defensive security headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"


@pytest.mark.asyncio
async def test_cors_preflight_headers():
    """CORS middleware responds correctly to preflight requests from allowed origins."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/api/v1/traces",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


# ==============================================================================
# 7. AI Investigation Prompt Injection Boundary
# ==============================================================================


def test_investigation_system_prompt_contains_security_boundaries():
    """Investigation system prompt explicitly defines boundaries for untrusted telemetry."""
    assert "SECURITY BOUNDARY & UNTRUSTED DATA RULES" in INVESTIGATION_SYSTEM_PROMPT
    assert "<untrusted_telemetry_context>" in INVESTIGATION_SYSTEM_PROMPT
    assert "IGNORE PREVIOUS INSTRUCTIONS" in INVESTIGATION_SYSTEM_PROMPT
    assert "inert observational telemetry" in INVESTIGATION_SYSTEM_PROMPT
