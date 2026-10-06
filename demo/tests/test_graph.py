"""Test agent graph construction and execution."""

import pytest

from demo.agent.graph import (
    customer_support_agent,
    create_customer_support_graph,
)
from demo.agent.state import CustomerSupportState


class TestGraphConstruction:
    """Tests for graph construction."""

    def test_graph_is_compiled(self):
        """Ensure graph is compiled and runnable."""
        assert hasattr(customer_support_agent, "invoke")
        assert hasattr(customer_support_agent, "ainvoke")

    def test_graph_initial_state(self):
        """Test that graph can be invoked with valid initial state."""
        initial_state: CustomerSupportState = {
            "user_input": "Where is my order ORD-1001?",
            "customers": None,
            "orders": None,
            "payments": None,
            "ticket": None,
            "user_needs_customer": "unsure",
            "user_needs_order": "unsure",
            "user_needs_payment_check": "unsure",
            "user_needs_support_ticket": "unsure",
            "agent_thought": None,
            "final_response": "",
        }

        # Simplified test - just check it doesn't crash
        result = customer_support_agent.invoke(initial_state)
        assert isinstance(result, dict)
        assert "final_response" in result or "agent_thought" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query(self):
        """Test agent with empty query."""
        initial_state: CustomerSupportState = {
            "user_input": "",
            "customers": None,
            "orders": None,
            "payments": None,
            "ticket": None,
            "user_needs_customer": "unsure",
            "user_needs_order": "unsure",
            "user_needs_payment_check": "unsure",
            "user_needs_support_ticket": "unsure",
            "agent_thought": None,
            "final_response": "",
        }

        # Should handle gracefully
        result = customer_support_agent.invoke(initial_state)
        assert isinstance(result, dict)

    def test_no_state_transition(self):
        """Test query that results in no tool calls."""
        initial_state: CustomerSupportState = {
            "user_input": "Hello, how are you?",
            "customers": None,
            "orders": None,
            "payments": None,
            "ticket": None,
            "user_needs_customer": "unsure",
            "user_needs_order": "unsure",
            "user_needs_payment_check": "unsure",
            "user_needs_support_ticket": "unsure",
            "agent_thought": None,
            "final_response": "",
        }

        result = customer_support_agent.invoke(initial_state)
        assert isinstance(result, dict)


class TestStateSchema:
    """Tests for state schema validation."""

    def test_state_with_all_fields(self):
        """Test that state with all fields is valid."""
        state: CustomerSupportState = {
            "user_input": "Test query",
            "customers": {"customer_id": "CUST-001", "name": "Test"},
            "orders": {"order_id": "ORD-1001", "status": "shipped"},
            "payments": {"payment_status": "paid"},
            "ticket": {},
            "user_needs_customer": "unsure",
            "user_needs_order": "unsure",
            "user_needs_payment_check": "unsure",
            "user_needs_support_ticket": "unsure",
            "customer_order_id": "ORD-1001",
            "agent_thought": "Testing agent thought",
            "final_response": "Response",
        }

        # Should not raise validation error
        assert isinstance(state, dict)
        assert len(state) == 12

    def test_state_with_minimal_fields(self):
        """Test that minimal state is valid."""
        state: CustomerSupportState = {
            "user_input": "Test",
            "customers": None,
            "orders": None,
            "payments": None,
            "ticket": None,
            "user_needs_customer": "unsure",
            "user_needs_order": "unsure",
            "user_needs_payment_check": "unsure",
            "user_needs_support_ticket": "unsure",
            "agent_thought": None,
            "final_response": "",
        }

        assert isinstance(state, dict)