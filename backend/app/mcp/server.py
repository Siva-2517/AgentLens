"""AgentLens Model Context Protocol (MCP) Server.

Exposes AgentLens observability, trace reconstruction, graph inspection,
failure detection, AI root-cause investigation, run comparison, and
semantic historical search to MCP-compatible AI agents.

Transport:
- Standard stdio transport for local AI development agents (Claude Code, etc.)

Guarantees:
- Read-only operations only
- No write or state-mutating tools exposed
- Credential and secret redaction on all outputs
- Thin interface delegating to core AgentLens services
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

from mcp.server.mcpserver import MCPServer

from app.mcp.tools import (
    compare_traces_handler,
    get_execution_graph_handler,
    get_trace_findings_handler,
    get_trace_handler,
    investigate_trace_handler,
    list_recent_traces_handler,
    search_historical_failures_handler,
)

logger = logging.getLogger("agentlens.mcp")


def create_mcp_server() -> MCPServer:
    """Create and configure the AgentLens MCPServer instance with registered tools."""
    server = MCPServer(
        name="AgentLens Observability Server",
        version="0.1.0",
        description="AgentLens read-only observability and failure investigation MCP server for AI agents",
    )

    # --------------------------------------------------------------------------
    # 1. get_trace
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_trace",
        description=(
            "Retrieve a structured trace summary and reconstructed execution flow for a specific trace_id. "
            "Returns execution metadata, duration, status, and compact ordered event list."
        ),
    )
    async def get_trace(trace_id: str) -> Dict[str, Any]:
        """Retrieve reconstructed trace details."""
        return await get_trace_handler(trace_id=trace_id)

    # --------------------------------------------------------------------------
    # 2. get_execution_graph
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_execution_graph",
        description=(
            "Retrieve the execution graph (nodes, directed edges, and counts) for a trace_id. "
            "Represents agent lifecycle, LLM calls, tool interactions, and errors."
        ),
    )
    async def get_execution_graph(trace_id: str) -> Dict[str, Any]:
        """Retrieve execution graph nodes and edges."""
        return await get_execution_graph_handler(trace_id=trace_id)

    # --------------------------------------------------------------------------
    # 3. get_trace_findings
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_trace_findings",
        description=(
            "Retrieve deterministic failure and anomaly findings detected for a trace_id. "
            "Includes explicit errors, missing responses, loops, retries, and severity scores."
        ),
    )
    async def get_trace_findings(trace_id: str) -> Dict[str, Any]:
        """Retrieve deterministic findings for a trace."""
        return await get_trace_findings_handler(trace_id=trace_id)

    # --------------------------------------------------------------------------
    # 4. investigate_trace
    # --------------------------------------------------------------------------
    @server.tool(
        name="investigate_trace",
        description=(
            "Perform AI-powered root-cause investigation for a trace_id. "
            "Returns earliest failure, root-cause explanation, supporting evidence, downstream effects, and recommended fixes."
        ),
    )
    async def investigate_trace(trace_id: str) -> Dict[str, Any]:
        """Perform AI root-cause failure investigation."""
        return await investigate_trace_handler(trace_id=trace_id)

    # --------------------------------------------------------------------------
    # 5. compare_traces
    # --------------------------------------------------------------------------
    @server.tool(
        name="compare_traces",
        description=(
            "Compare two completed execution traces side-by-side (trace_a vs trace_b). "
            "Returns structural diffs, execution metric differences, timeline alignment, and divergence points."
        ),
    )
    async def compare_traces(trace_a: str, trace_b: str) -> Dict[str, Any]:
        """Compare two traces side-by-side."""
        return await compare_traces_handler(trace_a=trace_a, trace_b=trace_b)

    # --------------------------------------------------------------------------
    # 6. search_historical_failures
    # --------------------------------------------------------------------------
    @server.tool(
        name="search_historical_failures",
        description=(
            "Search historical AgentLens failures using natural language semantic similarity (pgvector). "
            "Returns matching previous failures ranked by cosine similarity score."
        ),
    )
    async def search_historical_failures(
        query: str,
        limit: int = 10,
        severity: Optional[str] = None,
        rule: Optional[str] = None,
        project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search historical failures by semantic similarity."""
        return await search_historical_failures_handler(
            query=query,
            limit=limit,
            severity=severity,
            rule=rule,
            project=project,
        )

    # --------------------------------------------------------------------------
    # 7. list_recent_traces
    # --------------------------------------------------------------------------
    @server.tool(
        name="list_recent_traces",
        description=(
            "Retrieve a list of recent lightweight trace summaries with optional project filtering and pagination."
        ),
    )
    async def list_recent_traces(
        project: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List recent trace summaries."""
        return await list_recent_traces_handler(
            project=project,
            limit=limit,
            offset=offset,
        )

    # --------------------------------------------------------------------------
    # Optional Read-Only Resource: agentlens://traces/{trace_id}
    # --------------------------------------------------------------------------
    @server.resource("agentlens://traces/{trace_id}")
    async def trace_resource(trace_id: str) -> str:
        """Resource template to read a trace summary directly as JSON."""
        data = await get_trace_handler(trace_id=trace_id)
        return json.dumps(data, indent=2)

    return server


# Global default server instance
mcp_server = create_mcp_server()


async def run_server() -> None:
    """Run the MCP server over standard input/output (stdio transport)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # IMPORTANT: Logs must go to stderr, stdout is reserved for JSON-RPC MCP
    )
    logger.info("Starting AgentLens MCP Server over stdio...")
    await mcp_server.run_stdio_async()


def main() -> None:
    """CLI entrypoint."""
    try:
        asyncio.run(run_server())
    except (KeyboardInterrupt, SystemExit):
        logger.info("AgentLens MCP Server stopped.")


if __name__ == "__main__":
    main()
