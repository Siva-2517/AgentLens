"""Centralized sensitive data redaction utility (Phase 17 Security Hardening).

Recursively sanitizes telemetry payloads, error messages, investigation contexts,
embeddings, and MCP responses to prevent accidental disclosure of API keys, tokens,
passwords, and database connection strings while preserving legitimate telemetry
metrics (e.g., prompt_tokens, completion_tokens, cache_key).
"""

import re
from typing import Any, Set

# Exact keys or substrings that contain security credentials
SENSITIVE_EXACT_KEYS: Set[str] = {
    "api_key",
    "apikey",
    "secret",
    "client_secret",
    "password",
    "passwd",
    "authorization",
    "auth",
    "access_token",
    "refresh_token",
    "auth_token",
    "session_token",
    "private_key",
    "db_password",
    "postgres_password",
    "database_url",
    "credential",
    "credentials",
    "bearer_token",
    "jwt",
    "token",
}

# Explicit whitelist of keys containing words like "token" or "key" that are NOT secrets
SAFE_METRIC_KEYS: Set[str] = {
    "tokens",
    "total_tokens",
    "prompt_tokens",
    "completion_tokens",
    "token_count",
    "model_tokens",
    "tokens_used",
    "cache_key",
    "key_events",
    "primary_key",
    "sort_key",
    "foreign_key",
    "routing_key",
    "id_key",
    "name",
}

# Regex patterns for sensitive string contents
DB_URL_PATTERN = re.compile(
    r"(postgresql(?:\+asyncpg)?|postgres|mysql|mongodb|rediss?):\/\/[^\s\"'<>]+",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE)
JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]+")
SK_KEY_PATTERN = re.compile(r"sk-[a-zA-Z0-9_\-]{8,}")
AL_KEY_PATTERN = re.compile(r"al_(?:live|test)_[a-zA-Z0-9_\-]+", re.IGNORECASE)
API_KEY_QUERY_PATTERN = re.compile(r"(?:api[_-]?key|token)=[^&\s]+", re.IGNORECASE)
PASSWORD_ASSIGNMENT_PATTERN = re.compile(
    r"(?:password|passwd|secret|jwt_secret_key)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?",
    re.IGNORECASE,
)


def mask_sensitive_text(val: str) -> str:
    """Mask credentials, tokens, and connection strings from arbitrary text or log records."""
    if not val or not isinstance(val, str):
        return str(val) if val is not None else ""

    text = DB_URL_PATTERN.sub("[REDACTED_CONNECTION_URL]", val)
    text = JWT_PATTERN.sub("[REDACTED_JWT]", text)
    text = BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", text)
    text = AL_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    text = SK_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    text = API_KEY_QUERY_PATTERN.sub("api_key=[REDACTED]", text)
    text = PASSWORD_ASSIGNMENT_PATTERN.sub("password=[REDACTED]", text)
    return text


def is_sensitive_key(key: Any) -> bool:
    """Determine if a dictionary key name indicates a sensitive credential."""
    k_str = str(key).strip().lower()

    # If it's explicitly in the safe metric whitelist, do not redact
    if k_str in SAFE_METRIC_KEYS:
        return False

    # Check exact match
    if k_str in SENSITIVE_EXACT_KEYS:
        return True

    # Check compound names (e.g. user_password, client_secret_id, service_api_key)
    for sk in ("password", "secret", "api_key", "apikey", "access_token", "refresh_token", "private_key", "client_secret", "database_url"):
        if sk in k_str:
            return True

    # Check suffix e.g. auth_token, user_token (but not metric tokens)
    if k_str.endswith("_token") and not (k_str.endswith("_tokens") or "count" in k_str or "metric" in k_str):
        return True

    return False


def sanitize_string(val: str) -> str:
    """Redact sensitive patterns from a string value."""
    if not val:
        return val

    lower_val = val.lower()

    # 1. Database URLs
    if "postgresql://" in lower_val or "postgres://" in lower_val or "redis://" in lower_val or "mysql://" in lower_val or "mongodb://" in lower_val:
        return "[REDACTED_DB_URL]"

    # 2. Bearer tokens, API keys, secrets (including AgentLens al_live_ keys)
    if "bearer " in lower_val or "sk-" in val or "al_live_" in lower_val or "api_key=" in lower_val or "apikey=" in lower_val:
        return "[REDACTED_SECRET]"

    return val


def sanitize_telemetry(val: Any) -> Any:
    """Recursively redact sensitive keys, tokens, and credentials from telemetry or API structures.

    Preserves safe metrics like token counts and numeric data.
    """
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if is_sensitive_key(k):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_telemetry(v)
        return sanitized

    if isinstance(val, list):
        return [sanitize_telemetry(item) for item in val]

    if isinstance(val, str):
        return sanitize_string(val)

    return val


def mask_connection_string(val: str) -> str:
    """Safely mask connection strings and secrets in error messages and logs."""
    if not val:
        return val
    return mask_sensitive_text(str(val))
