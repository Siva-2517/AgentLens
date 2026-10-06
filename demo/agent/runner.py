"""Runner for demo agent with AgentLens integration."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphInterrupt

from agentlens import AgentLens, EventType
from agentlens.context import (
    clear_context,
    get_current_trace_id,
    get_parent_event_id,
    set_current_trace_id,
    set_parent_event_id,
)
from demo.agent.state import CustomerSupportState
from demo.agent.graph import customer_support_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DemoAgentRunner:
    """Runner for customer support demo agent with AgentLens observability."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        project_name: Optional[str] = None,
        use_agentlens: bool = True,
    ):
        """Initialize demo agent runner.

        Args:
            api_url: AgentLens API URL.
            api_key: AgentLens API key for authentication.
            project_name: Project name for multi-tenancy.
            use_agentlens: Whether to enable AgentLens observability.
        """
        self.api_url = api_url
        self.api_key = api_key
        self.project_name = project_name
        self.use_agentlens = use_agentlens

        # Initialize AgentLens if enabled
        if self.use_agentlens:
            try:
                self.lens = AgentLens(
                    api_url=api_url,
                    api_key=api_key,
                    project_name=project_name,
                )
                logger.info(f"AgentLens initialized: api_url={api_url}")
            except Exception as e:
                logger.warning(f"Could not initialize AgentLens: {e}")
                logger.warning("Continuing without AgentLens observability")
                self.lens = None
        else:
            self.lens = None

        # Current trace context
        self.current_trace_id: Optional[str] = None
        self.current_parent_event_id: Optional[str] = None

    def _agent_lens_event(
        self,
        event_type: EventType,
        event_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        data: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Create and optionally send AgentLens event.

        Args:
            event_type: Event type.
            event_id: Event ID (auto-generated if not provided).
            trace_id: Trace ID (uses current trace if not provided).
            Event data.
            metaEvent metadata.

        Returns:
            Event ID if sent, None if AgentLens disabled or failed.
        """
        if not self.lens:
            return None

        # Use current context if IDs not provided
        event_id = event_id or self.lens._generate_event_id()
        trace_id = trace_id or self.current_trace_id

        # Create event
        try:
            event = self.lens.create_event(
                event_type=event_type,
                data=data or {},
                trace_id=trace_id,
                metadata=metadata or {},
            )
            logger.debug(f"AgentLens event created: {event_type} (ID: {event.event_id})")
            return event.event_id
        except Exception as e:
            logger.error(f"Failed to create AgentLens event {event_type}: {e}")
            return None

    async def run_user_query(
        self,
        user_input: str,
        trace_name: Optional[str] = None,
    ) -> dict[str, str]:
        """Run user query through the agent with observability.

        Args:
            user_input: User's natural language query.
            trace_name: Optional trace name (auto-generated if not provided).

        Returns:
            Dictionary with final response and trace metadata.
        """
        trace_id = None

        try:
            # Start trace with AgentLens if enabled
            if self.lens:
                trace_name = trace_name or f"customer-support-{uuid.uuid4().hex[:8]}"

                # Create a trace and set trace context
                trace_obj = self.lens.create_trace(
                    name=trace_name,
                    metadata={"title": trace_name},
                )
                trace_id = trace_obj.trace_id
                self.current_trace_id = trace_id
                self.current_parent_event_id = None

                # Create AGENT_START event
                self._agent_lens_event(
                    EventType.AGENT_START,
                    trace_id=trace_id,
                    data={"query": user_input, "timestamp": datetime.utcnow().isoformat()},
                    metadata={"title": trace_name},
                )

            # Initialize state
            state: CustomerSupportState = {
                "user_input": user_input,
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

            # Log LLM_CALL event
            self._agent_lens_event(
                EventType.LLM_CALL,
                data={"model": "llama3-70b-8192", "query": user_input},
                metadata={"machine_reading": "Yes", "industry": "Customer Support"},
            )

            # Run agent graph
            logger.info(f"Running agent query: {user_input}")
            result = await customer_support_agent.ainvoke(state)

            # Generate LLM_RESPONSE event
            if self.lens:
                response_data = {
                    "machine_reading": "Yes",
                    "industry": "Customer Support",
                    "tool_calls": []
                    if "tool_call" not in result
                    else [
                        result["tool_call"]["name"],
                    ],
                }
                self._agent_lens_event(
                    EventType.LLM_RESPONSE,
                    data=response_data,
                )

            # Poll for FINAL_RESPONSE state
            final_response = result.get("final_response", "Response generation failed")
            logger.info(f"Agent produced response: {final_response[:100]}...")

            # Create REASONING event
            agent_thought = result.get("agent_thought")
            if agent_thought:
                if self.lens:
                    self._agent_lens_event(
                        EventType.STATE_CHANGE,
                        data={"thought": agent_thought},
                        metadata={"state_type": "REASONING"},
                    )

            # End trace with success
            if self.lens and self.current_trace_id:
                self._agent_lens_event(
                    EventType.AGENT_END,
                    data={"status": "completed"},
                    trace_id=self.current_trace_id,
                )

                # Send STATE_CHANGE events for tool results
                if result.get("customers"):
                    self._agent_lens_event(
                        EventType.STATE_CHANGE,
                        data={
                            "customer_id": result["customers"]["customer_id"],
                            "customer_name": result["customers"]["name"],
                        },
                        metadata={"source": "tool_execution"},
                    )

                if result.get("orders"):
                    self._agent_lens_event(
                        EventType.STATE_CHANGE,
                        data={
                            "order_id": result["orders"]["order_id"],
                            "status": result["orders"]["status"],
                        },
                        metadata={"source": "tool_execution"},
                    )

                # Flush events
                self.lens.flush()

            return {
                "success": True,
                "response": final_response,
                "trace_id": self.current_trace_id,
                "state": result,
            }

        except GraphInterrupt as e:
            # Graph interrupted for human input
            logger.warning(f"Graph interrupted: {e}")
            return {
                "success": False,
                "error": "Graph interrupted",
            }
        except Exception as e:
            # Error occurred
            logger.error(f"Agent execution failed: {e}", exc_info=True)

            # Create ERROR event if AgentLens enabled
            if self.lens and self.current_trace_id:
                self._agent_lens_event(
                    EventType.ERROR,
                    data={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "trace_id": self.current_trace_id,
                    },
                    trace_id=self.current_trace_id,
                )

                # End trace with failure
                if self.lens:
                    self.lens.create_event(
                        EventType.AGENT_END,
                        data={"status": "failed"},
                        trace_id=self.current_trace_id,
                    )
                    self.lens.flush()

            return {
                "success": False,
                "error": str(e),
                "trace_id": self.current_trace_id,
            }

    def close(self) -> None:
        """Close the agent runner and flush events."""
        if self.lens:
            self.lens.flush()
            self.lens.close()
            logger.info("AgentLens client closed")


async def main():
    """Example usage of the demo agent."""
    # Initialize runner
    runner = DemoAgentRunner(
        api_url="http://localhost:8000",
        api_key="test_api_key_123",
        project_name="demo-project",
        use_agentlens=True,
    )

    # Example queries to demonstrate agent capabilities
    examples = [
        "Where is my order ORD-1001?",
        "I paid for my order but it hasn't arrived yet.",
        "Check the payment status for order ORD-1002.",
        "I need to create a support ticket for a missing order.",
    ]

    print("=" * 60)
    print("AGENTLENS DEMO AGENT - Customer Support")
    print("=" * 60)
    print()

    for query in examples:
        print(f"\n👤 User: {query}")
        print("-" * 60)

        result = await runner.run_user_query(query, trace_name=query[:50])

        if result["success"]:
            print(f"🤖 Agent: {result['response']}")
            print(f"📦 Trace ID: {result['trace_id']}")
        else:
            print(f"❌ Error: {result['error']}")

        # Small delay between queries
        await asyncio.sleep(1)

    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)

    runner.close()


if __name__ == "__main__":
    # Run main async function
    asyncio.run(main())