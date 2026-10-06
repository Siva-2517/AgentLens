"""Test agent runner."""

import asyncio

import pytest


class TestAgentRunner:
    """Tests for DemoAgentRunner."""

    @pytest.mark.asyncio
    async def test_runner_initialization(self):
        """Test runner initialization."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,  # Disable Lens for unit tests
        )

        assert runner.api_url == "http://localhost:8000"
        assert runner.api_key == "test_api_key"
        assert runner.use_agentlens is False

        runner.close()

    @pytest.mark.asyncio
    async def test_runner_query(self):
        """Test runner with a simple query."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        result = await runner.run_user_query("Where is my order ORD-1001?")

        assert "success" in result
        assert isinstance(result["success"], bool)

        runner.close()

    @pytest.mark.asyncio
    async def test_multiple_queries(self):
        """Test multiple consecutive queries."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        queries = [
            "Where is my order?",
            "Check my payment status",
            "I need a support ticket",
        ]

        results = []
        for query in queries:
            result = await runner.run_user_query(query)
            results.append(result["success"])
            await asyncio.sleep(0.1)

        # At least some queries should succeed
        assert any(results)

        runner.close()

    @pytest.mark.asyncio
    async def test_query_with_trace_name(self):
        """Test query with custom trace name."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        result = await runner.run_user_query(
            "Where is my order ORD-1002?",
            trace_name="Order-inquiry-query",
        )

        assert "success" in result

        runner.close()

    def test_runner_close(self):
        """Test runner close method."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        # Should not raise
        runner.close()


class TestRunnerIntegration:
    """Integration tests with actual agent execution."""

    @pytest.mark.asyncio
    async def test_agent_executes_query(self):
        """Test that agent can execute a real query."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        result = await runner.run_user_query("Where is my order ORD-1001?")

        # Should get a response
        assert "response" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

        # Should have trace information
        assert "trace_id" in result
        assert result["trace_id"] is None

        runner.close()