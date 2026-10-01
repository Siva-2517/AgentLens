"""Application configuration."""

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

    # Database Configuration
    database_url: str = "postgresql://agentlens:agentlens@localhost:5432/agentlens"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # LLM Provider API Keys
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Application Settings
    log_level: str = "INFO"
    environment: str = "development"


settings = Settings()
