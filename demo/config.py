"""Demo agent configuration."""

from __future__ import annotations

import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Set logging level
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


class DemoConfig:
    """Configuration for demo agent.

    Environment variables:
    - GEMINI_API_KEY: Optional API key for Gemini LLM
    - GROQ_API_KEY: LLM provider API key (Groq)
    - AGENTEST_API_KEY: AgentLens API key
    - AGENTEST_URL: AgentLens API URL
    - DEMO_AGENT_NAME: Agent name/identifier
    - DEMO_USE_AGENTLENS: Whether to use AgentLens observability (True/False)
    """

    # AgentLens configuration
    AGENTEST_API_KEY: str = "test_api_key_123"
    AGENTEST_URL: str = "http://localhost:8000"
    AGENTEST_PROJECT: Optional[str] = "demo-project"

    # LLM configuration
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Demo agent configuration
    AGENT_NAME: str = "Customer Support Agent"
    AGENT_BOT: str = "Demo Assistant"

    # Use AgentLens observability
    USE_AGENTLENS: bool = True

    # Query examples
    QUERY_examples = [
        "Where is my order ORD-1001?",
        "Check the payment status for order ORD-1002",
        "My payment succeeded but my order hasn't arrived yet",
        "Create a support ticket for my missing order",
    ]

    @classmethod
    def from_env(cls) -> "DemoConfig":
        """Create configuration from environment variables.

        Returns:
            DemoConfig instance with values from environment.
        """
        config = cls()

        # Load from environment
        config.AGENTEST_API_KEY = (
            "test_api_key_123"  # Default for demo
        )

        config.AGENTEST_URL = "http://localhost:8000"
        config.AGENTEST_PROJECT = "demo-project"

        config.GEMINI_API_KEY = None  # Not required for mock LLM
        config.GROQ_API_KEY = None  # Not required for mock LLM

        config.USE_AGENTLENS = True

        logger.info("Demo configuration loaded from environment")

        return config

    def __repr__(self) -> str:
        """Representation of config (sanitized for secrets)."""
        return (
            f"DemoConfig(AGENTLENS_URL={self.AGENTEST_URL}, "
            f"AGENTLENS_API_KEY=***, "
            f"USE_AGENTLENS={self.USE_AGENTLENS})"
        )


# Global config instance
config = DemoConfig.from_env()