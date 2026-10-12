"""Model Context Protocol (MCP) Authentication and Project Authorization (Phase 19E).

Enforces strict tenant isolation for the AgentLens MCP Server:
1. Validates project-scoped API keys (al_live_...) against stored SHA-256 hashes.
2. Resolves authorized project ID and name strictly from verified credentials.
3. Enforces scope boundaries: keys with only ['ingest'] cannot access MCP read tools.
4. Rejects missing, invalid, expired, or revoked credentials.
5. In production environments, unhashed or legacy credentials are strictly rejected.
6. Preserves isolated local development / test credentials only in non-production environments.
"""

from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import DEFAULT_PROJECT_ID
from app.db.repositories import ApiKeyRepository, ProjectRepository
from app.services.auth import auth_service
from app.services.security import security_service

logger = logging.getLogger("agentlens.mcp.auth")

# ContextVar for per-context / per-coroutine API key overrides (used by CLI runners, tests, and workers)
_current_mcp_api_key: ContextVar[Optional[str]] = ContextVar("mcp_api_key", default=None)


@dataclass
class MCPPrincipal:
    """Authenticated project principal for MCP tool executions."""

    project_id: str
    project_name: str
    api_key_id: str
    scopes: List[str] = field(default_factory=list)
    is_legacy_dev: bool = False


def set_mcp_api_key(api_key: Optional[str]) -> Any:
    """Set the active MCP API key for the current context and return reset token."""
    return _current_mcp_api_key.set(api_key)


def clear_mcp_api_key() -> None:
    """Clear active MCP API key from current context."""
    _current_mcp_api_key.set(None)


def reset_mcp_api_key(token: Any) -> None:
    """Reset ContextVar to previous token state."""
    _current_mcp_api_key.reset(token)


@asynccontextmanager
async def mcp_api_key_context(api_key: Optional[str]):
    """Async context manager for scoped MCP API key execution."""
    token = _current_mcp_api_key.set(api_key)
    try:
        yield
    finally:
        _current_mcp_api_key.reset(token)


def get_mcp_api_key() -> Optional[str]:
    """Retrieve raw MCP credential from context var or process environment."""
    key = _current_mcp_api_key.get()
    if key and key.strip():
        return key.strip()
    env_mcp = os.environ.get("AGENTLENS_MCP_KEY")
    if env_mcp and env_mcp.strip():
        return env_mcp.strip()
    env_agentlens = os.environ.get("AGENTLENS_API_KEY")
    if env_agentlens and env_agentlens.strip():
        return env_agentlens.strip()
    return None


async def resolve_mcp_principal(
    db: AsyncSession,
) -> Tuple[Optional[MCPPrincipal], Optional[Dict[str, Any]]]:
    """Resolve and authenticate caller for MCP tool execution.

    Enforces:
    - Every tool invocation verifies the stored hash against database.
    - Revoked, expired, missing, or malformed credentials fail closed.
    - Only keys with 'mcp' or 'read' scopes are permitted.
    - Legacy fallback keys strictly fail closed outside explicit development/test environments.

    Returns:
        (MCPPrincipal, None) if authenticated.
        (None, error_dict) if authentication or authorization fails.
    """
    raw_key = get_mcp_api_key()
    if not raw_key:
        return None, {
            "error": "unauthorized",
            "message": "Authentication required: Missing MCP API key. Provide AGENTLENS_API_KEY environment variable.",
        }

    # 1. Project-scoped live API keys (al_live_...)
    if raw_key.startswith("al_live_"):
        key_hash = security_service.hash_api_key(raw_key)
        key_repo = ApiKeyRepository(db)
        key = await key_repo.get_by_hash(key_hash)

        if not key or key.is_revoked:
            return None, {
                "error": "unauthorized",
                "message": "Invalid or revoked API key.",
            }

        # Verify key expiration
        if key.expires_at:
            now = datetime.now(timezone.utc)
            exp = (
                key.expires_at
                if key.expires_at.tzinfo
                else key.expires_at.replace(tzinfo=timezone.utc)
            )
            if exp <= now:
                return None, {
                    "error": "unauthorized",
                    "message": "API key has expired.",
                }

        # Verify key scopes: ingestion-only keys cannot access MCP tools.
        # Strict explicit allowlist: must contain 'mcp' or 'read' (wildcard '*' is rejected)
        scopes = key.scopes or []
        has_mcp_access = any(s in ("mcp", "read") for s in scopes)
        if not has_mcp_access:
            return None, {
                "error": "forbidden",
                "message": "Ingestion-only API keys cannot access MCP tools. Key requires 'mcp' or 'read' scope.",
            }

        proj_repo = ProjectRepository(db)
        project = await proj_repo.get_by_id(key.project_id)
        project_name = project.name if project else "default"

        return MCPPrincipal(
            project_id=key.project_id,
            project_name=project_name,
            api_key_id=key.id,
            scopes=scopes,
            is_legacy_dev=False,
        ), None

    # 2. Legacy dev / test key fallback: strictly fail closed unless explicitly in dev/test
    env_str = getattr(settings, "environment", "development").lower()
    is_dev = env_str in ("development", "dev", "test", "testing", "local")
    if is_dev and auth_service.validate_api_key(raw_key):
        return MCPPrincipal(
            project_id=DEFAULT_PROJECT_ID,
            project_name="default",
            api_key_id="legacy-dev-key",
            scopes=["mcp", "read", "ingest"],
            is_legacy_dev=True,
        ), None

    # 3. Invalid credential or production rejection of legacy keys
    return None, {
        "error": "unauthorized",
        "message": "Invalid API key.",
    }
