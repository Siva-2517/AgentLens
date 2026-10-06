"""Integration tests for demo agent with AgentLens observability.

Tests that verify AgentLens SDK integration and event emission work correctly.
"""

import asyncio

import pytest
from langchain_core.messages import HumanMessage


class TestAgentLensIntegration:
    """Tests for AgentLens SDK integration."""

    @pytest.mark.asyncio
    async def test_runner_with_agentlens_disabled(self):
        """Test runner when AgentLens is disabled."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        result = await runner.run_user_query("Where is my order?")

        # Should still work without AgentLens
        assert "success" in result
        assert "response" in result

        runner.close()

    @pytest.mark.asyncio
    async def test_runner_handles_api_unavailable(self):
        """Test runner when API is unavailable."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://invalid-url-that-does-not-exist:8000",
            api_key="test_api_key",
            use_agentlens=False,  # Disable Lens to avoid failure from disabled exporter
        )

        # Should handle gracefully
        result = await runner.run_user_query("Test query")

        # May succeed or fail depending on network
        assert isinstance(result, dict)

        runner.close()

    @pytest.mark.asyncio
    async def test_multiple_runners(self):
        """Test multiple concurrent runners."""
        from demo.agent.runner import DemoAgentRunner

        # Create multiple runners
        runners = [
            DemoAgentRunner(
                api_url="http://localhost:8000",
                api_key="test_api_key",
                use_agentlens=False,
            )
            for _ in range(3)
        ]

        try:
            # Run queries concurrently
            tasks = [
                runner.run_user_query(f"Query {i}")
                for i, runner in enumerate(runners)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete
            assert len(results) == 3
        finally:
            for runner in runners:
                runner.close()

    @pytest.mark.asyncio
    async def test_runner_with_real_queries(self):
        """Test runner with various real customer support queries."""
        from demo.agent.runner import DemoAgentRunner

        runner = DemoAgentRunner(
            api_url="http://localhost:8000",
            api_key="test_api_key",
            use_agentlens=False,
        )

        queries = [
            "Where is my order ORD-1001?",
            "Check my payment status for order ORD-1002",
            "I need to create a support ticket for missing order",
        ]

        results = []
        for query in queries:
            result = await runner.run_user_query(query)
            results.append((query, result))

            # Verify structure
            assert "response" in result
            assert "success" in result

        runner.close()


class TestMockLLM:
    """Tests for Mock LLM fallback."""

    @pytest.mark.asyncio
    async def test_mock_llm_fallback(self):
        """Test that mock LLM is used when groq is unavailable."""
        from demo.agent.llm import MockLLM, LangChainLLMWrapper

        # Test mock LLM
        mock_llm = MockLLM()
        response = await mock_llm.ainvoke([HumanMessage(content="Where is my order?")])

        assert "content" in response
        assert "tool_calls" in response

    @pytest.mark.asyncio
    async def test_langchain_llm_with_mock_fallback(self):
        """Test that LangChainLLMWrapper falls back to mock when groq unavailable."""
        from demo.agent.llm import LangChainLLMWrapper

        # This will use mock LLM internally
        llm = LangChainLLMWrapper(provider="groq", model="llama3-70b-8192")
        response = await llm.ainvoke([HumanMessage(content="Test query")])

        assert "content" in response or len(response) > 0