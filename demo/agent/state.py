"""Agent state schema for LangGraph workflow."""

from typing import Literal, Optional
from typing_extensions import TypedDict


class CustomerSupportState(TypedDict):
    """State for customer support agent."""

    # User input
    user_input: str

    # Tool results
    customers: Optional[dict[str, any]]
    orders: Optional[dict[str, any]]
    payments: Optional[dict[str, any]]
    ticket: Optional[dict[str, any]]

    # Tool selection - which tools to call
    user_needs_customer: Literal["yes", "no", "unsure"]
    user_needs_order: Literal["yes", "no", "unsure"]
    user_needs_payment_check: Literal["yes", "no", "unsure"]
    user_needs_support_ticket: Literal["yes", "no", "unsure"]

    # Customer order ID if extracted
    customer_order_id: Optional[str]

    # Agent reasoning
    agent_thought: Optional[str]

    # Final output
    final_response: str


CustomerSupportState.__doc__ = """State for customer support agent workflow.

The agent manages customer queries about orders, payment status, and support tickets.
"""