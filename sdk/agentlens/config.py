"""AgentLens SDK configuration."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentLensConfig(BaseModel):
    """Configuration for AgentLens SDK."""

    model_config = ConfigDict(validate_assignment=True)

    api_url: str = Field(
        default="http://localhost:8000",
        description="AgentLens API base URL",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication (optional for now)",
    )
    project_name: Optional[str] = Field(
        default=None,
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
