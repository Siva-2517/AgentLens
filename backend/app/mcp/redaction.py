"""Sensitive data redaction for MCP responses.

Ensures no API keys, tokens, credentials, or secrets are leaked to MCP clients.
Delegates to centralized redaction engine (Phase 17).
"""

from typing import Any
from app.services.redaction import SENSITIVE_EXACT_KEYS as SENSITIVE_KEYS, sanitize_telemetry


def sanitize_for_mcp(val: Any) -> Any:
    """Recursively redact sensitive keys, tokens, and credentials from MCP output.

    Args:
        val: Any data structure (dict, list, string, scalar).

    Returns:
        Sanitized structure with secrets redacted.
    """
    return sanitize_telemetry(val)
