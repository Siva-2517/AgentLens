"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
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

    # Security Configuration (Phase 17)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    max_event_batch_size: int = 1000
    sql_echo: bool = False


settings = Settings()
