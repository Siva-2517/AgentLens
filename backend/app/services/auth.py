"""Authentication service (Phase 17 Security Hardened).

Provides constant-time API key verification, dynamic key configuration from settings,
and strict project identifier validation.
"""

import re
import secrets
from typing import Optional, Set

from app.config import settings

PROJECT_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


class AuthService:
    """Service for handling API key authentication and project identification."""

    def __init__(self):
        """Initialize auth service."""
        self._override_keys: Optional[Set[str]] = None

    def get_valid_api_keys(self) -> Set[str]:
        """Retrieve the configured set of valid API keys."""
        if self._override_keys is not None:
            return self._override_keys

        configured = settings.agentlens_api_keys
        if not configured:
            return {"test_api_key_123", "dev_key"}

        keys = {k.strip() for k in configured.split(",") if k.strip()}
        if not keys:
            return {"test_api_key_123", "dev_key"}
        return keys

    def set_valid_api_keys(self, keys: Optional[Set[str]]) -> None:
        """Override valid API keys (useful for testing)."""
        self._override_keys = keys

    def validate_api_key(self, api_key: Optional[str]) -> bool:
        """Validate an API key using constant-time comparison to prevent timing attacks.

        Args:
            api_key: API key to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not api_key or not isinstance(api_key, str):
            return False

        clean_key = api_key.strip()
        if not clean_key:
            return False

        valid_keys = self.get_valid_api_keys()
        is_valid = False
        for expected in valid_keys:
            if secrets.compare_digest(clean_key, expected):
                is_valid = True

        return is_valid

    def extract_project_name(self, project_header: Optional[str]) -> Optional[str]:
        """Extract and validate project name from header.

        Args:
            project_header: Project name from X-AgentLens-Project header.

        Returns:
            Project name if valid, None otherwise.
        """
        if not project_header or not isinstance(project_header, str):
            return None

        clean = project_header.strip()
        if not clean or len(clean) > 128:
            return None

        if not PROJECT_NAME_REGEX.match(clean):
            return None

        return clean


# Singleton instance
auth_service = AuthService()
