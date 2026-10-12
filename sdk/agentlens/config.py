import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentLensConfig(BaseModel):
    """Configuration for AgentLens SDK."""

    model_config = ConfigDict(validate_assignment=True)

    api_url: str = Field(
        default_factory=lambda: os.getenv("AGENTLENS_API_URL", "http://localhost:8000"),
        description="AgentLens API base URL",
    )
    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("AGENTLENS_API_KEY"),
        description="API key for authentication (al_live_...)",
    )
    project_name: Optional[str] = Field(
        default_factory=lambda: os.getenv("AGENTLENS_PROJECT_NAME"),
        description="Project name for trace organization",
    )
    enabled: bool = Field(
        default=True,
        description="Enable/disable telemetry capture",
    )
    flush_interval: int = Field(
        default=5,
        description="Seconds between automatic event flushes",
    )
    batch_size: int = Field(
        default=100,
        description="Maximum events to batch before flushing",
    )
    timeout: int = Field(
        default=5,
        description="HTTP request timeout in seconds",
    )
