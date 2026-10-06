"""LangGraph agent definition for customer support workflow."""

import logging
from datetime import datetime
from typing import Annotated, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from demo.agent.state import CustomerSupportState
from demo.agent.tools import (
    check_payment,
    create_support_ticket,
    get_customer,
    get_order,
)
from demo.agent.llm import get_llm
from agentlens.types import EventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def should_call_customer(state: CustomerSupportState) -> Literal["yes", "no", "unsure"]:
    """Determine if customer lookup is needed.

    Args:
        state: Current agent state.

    Returns:
        Tool selection decision.
    """
    if state.get("user_needs_customer", "unsure") == "yes":
        return "yes"
    return "no"


def should_call_order(state: CustomerSupportState) -> Literal["yes", "no", "unsure"]:
    """Determine if order lookup is needed.

    Args:
        state: Current agent state.

    Returns:
        Tool selection decision.
    """
    if state.get("user_needs_order", "unsure") == "yes":
        # Only if we have a customer ID
        if state.get("customers"):
            return "yes"
    return "no"


def should_call_payment(state: CustomerSupportState) -> Literal["yes", "no", "unsure"]:
    """Determine if payment check is needed.

    Args:
        state: Current agent state.

    Returns:
        Tool selection decision.
    """
    if state.get("user_needs_payment_check", "unsure") == "yes":
        # Only if we have an order ID
        if state.get("orders") or state.get("customer_order_id"):
            return "yes"
    return "no"


def should_call_ticket(state: CustomerSupportState) -> Literal["yes", "no", "unsure"]:
    """Determine if support ticket creation is needed.

    Args:
        state: Current agent state.

    Returns:
        Tool selection decision.
    """
    if state.get("user_needs_support_ticket", "unsure") == "yes":
        # Has customer and has an issue (user input contains keywords)
        if state.get("customers") and state.get("user_input", ""):
            return "yes"
    return "no"


def agent_thought_node(state: CustomerSupportState) -> CustomerSupportState:
    """Generate agent thought about query.

    Args:
        state: Current agent state.

    Returns:
        Updated state with agent thought.
    """
    # Simple heuristic for thought generation
    thought = f"Analyzing customer query: {state['user_input']}"

    if state.get("ordered"):
        thought += f" Customer has {len(state['ordered'])} order(s)."
    if state.get("payments"):
        thought += f" Order(s) payment status: {list(state['payments'].keys())}"

    state["agent_thought"] = thought

    return state


def llm_call_node(
    state: CustomerSupportState,
    config: Optional[RunnableConfig] = None,
) -> CustomerSupportState:
    """LLM node for tool selection.

    Args:
        state: Current agent state.
        config: Runnable configuration.

    Returns:
        Updated state with tool selection.
    """
    # Use mock LLM for deterministic behavior
    llm = get_llm()

    # Build system message
    system_prompt = """You are a customer support assistant.

Your job is to determine which tools the user needs to answer their question.

Available tools:
1. get_customer(customer_id) - Get customer information
2. get_order(order_id) - Get order information
3. check_payment(order_id) - Get payment status for an order
4. create_support_ticket(customer_id, issue) - Create a support ticket

ANALYSIS INSTRUCTIONS:
1. Read the user's query carefully
2. Determine which information the user needs
3. Select only the necessary tools
4. If no tools are needed, respond directly

Example user queries:
- "Where is my order ORD-1001?" → get_order
- "Check my payment status" → check_payment
- "I need to report a shipping issue" → create_support_ticket
- "Who can I talk to about my order?" → get_order

Return ONLY the tool name that should be called. Do not include reasoning.
"""

    messages = [SystemMessage(content=system_prompt)]

    # Add user message if exists
    user_input_val = state.get("user_input")
    if user_input_val:
        if isinstance(user_input_val, list):
            msg_text = user_input_val[-1].content if hasattr(user_input_val[-1], "content") else str(user_input_val[-1])
        elif hasattr(user_input_val, "content"):
            msg_text = user_input_val.content
        else:
            msg_text = str(user_input_val)
        messages.append(HumanMessage(content=msg_text))

    logger.info(f"LLM called with messages: {len(messages)}")

    try:
        response = llm.invoke(messages)
        logger.info(f"LLM response: {response}")

        # Extract tool selection
        thought = "I'll analyze your query and determine the best course of action."

        # Parse tool selection from response
        if hasattr(response, "content") and response.content:
            thought += f" Based on your query: {response.content}"

        state["agent_thought"] = thought

        # Extract tool name from response (simplified for example)
        tool_name = "get_customer"  # Default
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_name = response.tool_calls[0]["name"]
            logger.info(f"LLM selected tool: {tool_name}")

            # Update state with tool decision
            if tool_name == "get_order":
                state["user_needs_order"] = "yes"
                # Extract order_id from question (simplified)
                user_str = str(state.get("user_input", ""))
                if "ORD-" in user_str:
                    state["customer_order_id"] = user_str.split("ORD-")[1].split()[0]
            elif tool_name == "check_payment":
                state["user_needs_payment_check"] = "yes"
            elif tool_name == "create_support_ticket":
                state["user_needs_support_ticket"] = "yes"
            elif tool_name == "get_customer":
                state["user_needs_customer"] = "yes"

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        thought = f"Error calling LLM: {e}. Using fallback tool selection."
        state["agent_thought"] = thought
        # Default to getting customer
        state["user_needs_customer"] = "yes"

    return state


def tool_execution_node(state: CustomerSupportState) -> CustomerSupportState:
    """Execute tools selected by LLM.

    Args:
        state: Current agent state.

    Returns:
        Updated state with tool results.
    """
    logger.info("Executing tools...")

    # Execute customer lookup if needed
    if state.get("user_needs_customer", "unsure") == "yes":
        logger.info("Calling get_customer")
        try:
            customer = get_customer("CUST-001")
            if customer:
                state["customers"] = customer
                logger.info(f"Customer found: {customer['name']}")
        except Exception as e:
            logger.error(f"Failed to get customer: {e}")

    # Execute order lookup if needed
    if state.get("user_needs_order", "unsure") == "yes":
        order_id = state.get("customer_order_id") or "ORD-1001"
        logger.info(f"Calling get_order: {order_id}")
        try:
            order = get_order(order_id)
            if order:
                state["orders"] = order
                state["customer_order_id"] = order_id
        except Exception as e:
            logger.error(f"Failed to get order: {e}")

    # Execute payment check if needed
    if state.get("user_needs_payment_check", "unsure") == "yes":
        order_id = state.get("customer_order_id") or "ORD-1001"
        logger.info(f"Calling check_payment: {order_id}")
        try:
            payment = check_payment(order_id)
            if payment:
                state["payments"] = {order_id: payment}
        except Exception as e:
            logger.error(f"Failed to check payment: {e}")

    # Execute ticket creation if needed
    if state.get("user_needs_support_ticket", "unsure") == "yes":
        logger.info("Calling create_support_ticket")
        try:
            ticket = create_support_ticket("CUST-001", state["user_input"])
            if ticket:
                state["ticket"] = ticket
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")

    return state


def response_node(state: CustomerSupportState) -> CustomerSupportState:
    """Generate final response to user.

    Args:
        state: Current agent state.

    Returns:
        Updated state with final response.
    """
    response_text = ""

    # Generate helpful response
    if state.get("ticket"):
        ticket_id = state["ticket"]["ticket_id"]
        response_text = (
            f"Thank you for contacting support. A ticket has been created with ID: {ticket_id}. "
            f"Our team will review your issue and get back to you shortly."
        )
    elif state.get("orders"):
        order = state["orders"]
        response_text = (
            f"Here's your order information:\n\n"
            f"Order ID: {order['order_id']}\n"
            f"Status: {order['status']}\n"
            f"Estimated Delivery: {order.get('estimated_delivery', 'TBD')}\n"
        )
    elif state.get("payments"):
        payment = list(state["payments"].values())[0]
        response_text = (
            f"Payment Status: {payment['payment_status']}\n"
            f"Payment Method: {payment['method']}\n"
        )
    elif state.get("customers"):
        customer = state["customers"]
        response_text = (
            f"Thank you, {customer['name']}! What can I help you with today?"
        )
    else:
        response_text = "I understand you have a question. Let me help you find the information you need."

    state["final_response"] = response_text

    logger.info(f"Final response: {response_text}")

    return state


def create_customer_support_graph(
    llm_provider: str = "groq",
    llm_model: str = "llama3-70b-8192",
) -> StateGraph:
    """Create LangGraph workflow for customer support agent.

    Args:
        llm_provider: LLM provider ("groq" or "gemini").
        llm_model: LLM model name.

    Returns:
        Compiled LangGraph workflow.
    """
    workflow = StateGraph(CustomerSupportState)

    # Add nodes
    workflow.add_node("agent_thought", agent_thought_node)
    workflow.add_node("llm_call", llm_call_node)
    workflow.add_node("tool_execution", tool_execution_node)
    workflow.add_node("response", response_node)

    # Add edges
    workflow.set_entry_point("agent_thought")
    workflow.add_edge("agent_thought", "llm_call")
    workflow.add_edge("llm_call", "tool_execution")
    workflow.add_edge("tool_execution", "response")
    workflow.add_edge("response", END)

    # Compile graph
    graph = workflow.compile()

    logger.info(f"Customer support graph created with LLM provider: {llm_provider}")

    return graph


# Global graph instance
customer_support_agent = create_customer_support_graph()

CustomerSupportState.__doc__ = """State for customer support agent."""