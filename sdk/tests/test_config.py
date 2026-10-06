"""Tests for AgentLens configuration."""

import pytest

from agentlens.config import AgentLensConfig


def test_config_defaults():
    """Test default configuration values."""
    config = AgentLensConfig()

    assert config.api_url == "http://localhost:8000"
    assert config.api_key is None
    assert config.project_name is None
    assert config.enabled is True
    assert config.flush_interval == 5
    assert config.batch_size == 100
    assert config.timeout == 5


def test_config_custom_values():
    """Test custom configuration values."""
    config = AgentLensConfig(
        api_url="https://api.example.com",
        api_key="test_key_123",
        project_name="my-project",
        enabled=False,
        batch_size=50,
    )

    assert config.api_url == "https://api.example.com"
    assert config.api_key == "test_key_123"
    assert config.project_name == "my-project"
    assert config.enabled is False
    assert config.batch_size == 50


def test_config_validation():
    """Test configuration validation."""
    config = AgentLensConfig()

    # Should allow assignment
    config.batch_size = 200
    assert config.batch_size == 200

    config.enabled = False
    assert config.enabled is False
