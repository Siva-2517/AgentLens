"""Model Context Protocol (MCP) package for AgentLens."""

from app.mcp.server import create_mcp_server, mcp_server
from app.mcp.tools import set_session_factory

__all__ = [
    "mcp_server",
    "create_mcp_server",
    "set_session_factory",
]
