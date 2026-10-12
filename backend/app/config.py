import math
from collections import Counter
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # Database Configuration (Neon PostgreSQL)
    database_url: str = "postgresql://user:password@ep-example.neon.tech/agentlens?sslmode=require"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # LLM Provider Configuration
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "groq"
    llm_model: str = ""
    llm_temperature: float = 0.0
    investigation_timeout_seconds: float = 30.0

    # Embedding Provider Configuration (Phase 15: Historical Failure Search)
    embedding_provider: str = "gemini"
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768

    # Application Settings
    log_level: str = "INFO"
    environment: str = "development"

    # API Key Configuration (Phase 3: simple validation, Phase 17: hardened validation)
    # In development, use: test_api_key_123 or dev_key
    agentlens_api_keys: str = "test_api_key_123,dev_key"

    # Security Configuration (Phase 17 & Phase 19B)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    max_event_batch_size: int = 1000
    sql_echo: bool = False

    # Authentication & Session Security (Phase 19B)
    jwt_secret_key: str = "agentlens_super_secret_jwt_hmac_signing_key_32_bytes_min!"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False  # Set to True in production HTTPS
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    # Deployment Topology & Operational Readiness (Phase 20D)
    deployment_topology: str = "single-instance"  # "single-instance" or "multi-instance"
    redis_required: bool = False
    allow_mock_providers: bool = False  # Explicitly disallow mock providers in production
    metrics_auth_token: str | None = None
    metrics_enabled: bool = True

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Fail-closed validation enforcing security requirements in production."""
        env = (self.environment or "development").strip().lower()
        is_prod = env in ("production", "prod")

        if is_prod:
            # 1. JWT Secret Key Validation & Entropy
            secret = (self.jwt_secret_key or "").strip()
            if not secret:
                raise ValueError("CRITICAL SECURITY ERROR: JWT_SECRET_KEY is required in production.")

            insecure_defaults = {
                "agentlens_super_secret_jwt_hmac_signing_key_32_bytes_min!",
                "secret",
                "changeme",
                "change_me",
                "password",
                "default",
                "admin",
                "development",
                "12345678901234567890123456789012",
            }
            if secret in insecure_defaults:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Default or known example JWT_SECRET_KEY cannot be used in production."
                )

            if len(secret) < 32:
                raise ValueError(
                    f"CRITICAL SECURITY ERROR: JWT_SECRET_KEY in production must be at least 32 characters (got {len(secret)})."
                )

            # Shannon entropy check (at least 3.5 bits/char to reject low-entropy strings)
            length = len(secret)
            counts = Counter(secret)
            entropy = -sum((c / length) * math.log2(c / length) for c in counts.values())
            if entropy < 3.5:
                raise ValueError(
                    f"CRITICAL SECURITY ERROR: JWT_SECRET_KEY has insufficient cryptographic entropy ({entropy:.2f} bits/char < 3.5)."
                )

            # 2. Cookie Security
            if not self.cookie_secure:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: COOKIE_SECURE must be True in production to enforce HTTPS-only cookies."
                )

            # 3. CORS Origins Validation
            origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
            if "*" in origins:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Wildcard '*' in CORS_ORIGINS is prohibited in production when credentials/cookies are enabled."
                )
            for origin in origins:
                if origin.startswith("http://"):
                    raise ValueError(
                        f"CRITICAL SECURITY ERROR: Insecure HTTP origin '{origin}' in CORS_ORIGINS is prohibited in production. Use HTTPS."
                    )

            # 4. Database URL & Explicit TLS/SSL Enforcement
            db_url = (self.database_url or "").lower()
            if "ep-example" in db_url or "user:password" in db_url:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Example placeholder DATABASE_URL cannot be used in production."
                )
            if not ("postgresql" in db_url or "postgres" in db_url):
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Production database must be PostgreSQL (got non-PostgreSQL URL)."
                )

            # Explicitly reject insecure SSL parameters
            insecure_ssl_params = ("sslmode=disable", "sslmode=allow", "ssl=false", "ssl=0")
            if any(p in db_url for p in insecure_ssl_params):
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Insecure SSL mode (disable/allow/false) in DATABASE_URL is prohibited in production."
                )

            # Enforce verified TLS/SSL parameters
            valid_ssl = any(
                p in db_url
                for p in ("sslmode=require", "sslmode=verify-ca", "sslmode=verify-full", "ssl=true", "ssl=1")
            )
            if not valid_ssl:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: DATABASE_URL must explicitly require TLS/SSL (e.g., sslmode=require, sslmode=verify-full, or ssl=true) in production."
                )

            # 5. Legacy API Keys
            if self.agentlens_api_keys:
                configured = [k.strip() for k in self.agentlens_api_keys.split(",") if k.strip()]
                if any(k in ("test_api_key_123", "dev_key") for k in configured):
                    raise ValueError(
                        "CRITICAL SECURITY ERROR: Development test keys (test_api_key_123, dev_key) cannot be configured in AGENTLENS_API_KEYS in production."
                    )

            # 6. Provider Mock Mode Prohibition in Production (Phase 20D)
            if not self.allow_mock_providers:
                llm_p = (self.llm_provider or "").strip().lower()
                emb_p = (self.embedding_provider or "").strip().lower()
                if llm_p == "mock":
                    raise ValueError("CRITICAL CONFIGURATION ERROR: LLM_PROVIDER cannot be 'mock' in production.")
                if emb_p == "mock":
                    raise ValueError("CRITICAL CONFIGURATION ERROR: EMBEDDING_PROVIDER cannot be 'mock' in production.")
                if llm_p == "groq" and (not self.groq_api_key or self.groq_api_key.startswith("your_")):
                    raise ValueError("CRITICAL CONFIGURATION ERROR: GROQ_API_KEY is required in production when LLM_PROVIDER is 'groq'.")
                if llm_p == "gemini" and (not self.gemini_api_key or self.gemini_api_key.startswith("your_")):
                    raise ValueError("CRITICAL CONFIGURATION ERROR: GEMINI_API_KEY is required in production when LLM_PROVIDER is 'gemini'.")
                if emb_p == "gemini" and (not self.gemini_api_key or self.gemini_api_key.startswith("your_")):
                    raise ValueError("CRITICAL CONFIGURATION ERROR: GEMINI_API_KEY is required in production when EMBEDDING_PROVIDER is 'gemini'.")

            # 7. Multi-Instance Topology Enforcement (Phase 20D)
            if (self.deployment_topology or "").strip().lower() == "multi-instance":
                self.redis_required = True

            # 8. Redis Production Endpoint Enforcement
            if self.redis_required:
                r_check = (self.redis_url or "").lower()
                if "localhost" in r_check or "127.0.0.1" in r_check:
                    raise ValueError(
                        "CRITICAL CONFIGURATION ERROR: REDIS_URL cannot point to localhost/127.0.0.1 in production when Redis is required. Configure your Redis Cloud endpoint."
                    )

        # Validate REDIS_URL scheme (supports redis:// and rediss:// for cloud TLS)
        r_url = (self.redis_url or "").strip().lower()
        if r_url and not (r_url.startswith("redis://") or r_url.startswith("rediss://")):
            raise ValueError(
                f"Invalid REDIS_URL scheme: '{self.redis_url[:15]}...'. Must begin with 'redis://' or 'rediss://' (for TLS)."
            )

        return self


settings = Settings()
