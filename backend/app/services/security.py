"""Security service for authentication, password hashing, JWT sessions, and API key management (Phase 19B)."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
import jwt

from app.config import settings

logger = logging.getLogger(__name__)


class SecurityService:
    """Core cryptographic and authentication utilities."""

    def __init__(self):
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days

    # =========================================================================
    # Password Hashing & Verification (bcrypt)
    # =========================================================================

    def hash_password(self, password: str) -> str:
        """Hash a plain text password using bcrypt with work factor 12."""
        if not password or not isinstance(password, str):
            raise ValueError("Password must be a non-empty string")
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a bcrypt hash in constant time."""
        if not plain_password or not hashed_password:
            return False
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception as e:
            logger.warning(f"Password verification error: {e}")
            return False

    # =========================================================================
    # JWT Tokens (Access & Refresh)
    # =========================================================================

    def create_access_token(
        self,
        user_id: str,
        email: str,
        is_superuser: bool = False,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a signed, short-lived JWT access token."""
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(minutes=self.access_token_expire_minutes))
        payload: Dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "is_superuser": is_superuser,
            "type": "access",
            "iss": "agentlens",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a signed, long-lived JWT refresh token."""
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(days=self.refresh_token_expire_days))
        payload: Dict[str, Any] = {
            "sub": user_id,
            "type": "refresh",
            "iss": "agentlens",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token claims.

        Raises:
            jwt.ExpiredSignatureError: If token is expired.
            jwt.InvalidTokenError: If token is malformed, invalid signature, or wrong issuer.
        """
        return jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.algorithm],
            issuer="agentlens",
            options={"require": ["exp", "sub", "type", "iss"]},
        )

    # =========================================================================
    # CSRF Tokens
    # =========================================================================

    def generate_csrf_token(self) -> str:
        """Generate a cryptographically secure URL-safe CSRF token."""
        return secrets.token_urlsafe(32)

    def verify_csrf_token(self, client_token: Optional[str], cookie_token: Optional[str]) -> bool:
        """Verify CSRF token using constant-time comparison."""
        if not client_token or not cookie_token:
            return False
        return secrets.compare_digest(client_token.strip(), cookie_token.strip())

    # =========================================================================
    # Ingestion API Key Generation & Hashing
    # =========================================================================

    def generate_ingestion_api_key(self) -> Tuple[str, str, str]:
        """Generate a cryptographically secure ingestion API key.

        Format: al_live_<48 hex chars>
        Returns:
            Tuple of:
            - raw_key: Returned ONCE to caller (never stored)
            - key_prefix: 'al_live_' + first 8 hex chars (stored for fast index lookup)
            - key_hash: SHA-256 of raw_key (stored for constant-time verification)
        """
        random_part = secrets.token_hex(24)
        raw_key = f"al_live_{random_part}"
        key_prefix = raw_key[:16]  # 'al_live_' + 8 chars
        key_hash = self.hash_api_key(raw_key)
        return raw_key, key_prefix, key_hash

    def hash_api_key(self, api_key: str) -> str:
        """Compute SHA-256 hash of an API key secret."""
        if not api_key:
            return ""
        return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


# Singleton instance
security_service = SecurityService()
