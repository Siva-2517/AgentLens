"""Tests for Redis Cloud configuration, TLS support, and secret redaction."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services.redaction import mask_sensitive_text, mask_connection_string
from app.services.realtime_publisher import RealtimePublisher
from verify_redis import mask_redis_url


VALID_JWT = "a" * 32 + "1234#$!"


def test_redis_cloud_standard_url_accepted():
    """Settings accepts standard redis:// URL with authentication credentials."""
    s = Settings(
        environment="development",
        jwt_secret_key=VALID_JWT,
        redis_url="redis://default:cloud_pass_123@redis-12345.c123.us-east-1-1.ec2.redns.redis-cloud.com:12345/0",
    )
    assert "redis-12345" in s.redis_url
    assert s.redis_url.startswith("redis://")


def test_redis_cloud_tls_url_accepted():
    """Settings accepts rediss:// (TLS) URL with authentication credentials."""
    s = Settings(
        environment="development",
        jwt_secret_key=VALID_JWT,
        redis_url="rediss://default:cloud_pass_123@redis-12345.c123.us-east-1-1.ec2.redns.redis-cloud.com:12345/0",
    )
    assert "redis-12345" in s.redis_url
    assert s.redis_url.startswith("rediss://")


def test_invalid_redis_url_scheme_rejected():
    """Settings rejects invalid redis URL schemes."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="development",
            jwt_secret_key=VALID_JWT,
            redis_url="http://invalid-redis-host:6379",
        )
    assert "Invalid REDIS_URL scheme" in str(exc.value)


def test_redis_cloud_credentials_masked_in_logs():
    """mask_sensitive_text and mask_connection_string must mask Redis Cloud URLs with passwords."""
    raw_url = "rediss://default:super_secret_redis_pass@redis-12345.c123.us-east-1-1.ec2.redns.redis-cloud.com:12345"
    log_msg = f"Failed to connect to Redis instance at {raw_url} due to timeout."

    masked = mask_sensitive_text(log_msg)
    assert "super_secret_redis_pass" not in masked
    assert "[REDACTED_CONNECTION_URL]" in masked

    masked_conn = mask_connection_string(raw_url)
    assert "super_secret_redis_pass" not in masked_conn
    assert "[REDACTED_CONNECTION_URL]" in masked_conn


def test_mask_redis_url_helper_preserves_host_and_masks_password():
    """verify_redis.mask_redis_url masks password but displays host and username for diagnostics."""
    raw = "rediss://default:cloud_secret_123@redis-12345.c123.us-east-1-1.ec2.redns.redis-cloud.com:12345/0"
    masked = mask_redis_url(raw)
    assert "cloud_secret_123" not in masked
    assert "default:***@redis-12345.c123.us-east-1-1.ec2.redns.redis-cloud.com:12345" in masked
    assert masked.startswith("rediss://")


def test_realtime_publisher_accepts_cloud_url():
    """RealtimePublisher instantiates cleanly with a cloud Redis URL."""
    cloud_url = "rediss://default:pass@redis-cloud.example.com:12345/0"
    pub = RealtimePublisher(redis_url=cloud_url)
    assert pub.redis_url == cloud_url


def test_production_rejects_localhost_redis_when_required():
    """In production with redis_required=True, localhost REDIS_URL must be rejected."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            jwt_secret_key="k9#Xm2$vL8*pQ4@wN7!jR5^tY1&bC3~zP6=fG0+hD_vW9",
            cookie_secure=True,
            cors_origins="https://dashboard.example.com",
            database_url="postgresql://user:pass@ep-live.neon.tech/agentlens?sslmode=require",
            agentlens_api_keys="",
            llm_provider="groq",
            groq_api_key="valid_key",
            embedding_provider="gemini",
            gemini_api_key="valid_key",
            allow_mock_providers=False,
            redis_required=True,
            redis_url="redis://localhost:6379/0",
        )
    assert "REDIS_URL cannot point to localhost/127.0.0.1 in production" in str(exc.value)
