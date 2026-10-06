"""Example usage of the AgentLens SDK."""

from agentlens import AgentLens, EventType


def simple_agent_example():
    """Simple example of using AgentLens SDK."""
    # Initialize the SDK
    lens = AgentLens(
        api_url="http://localhost:8000",
        project_name="example-agent",
        enabled=False,  # Disabled for this example
    )

    # Use context manager for automatic trace management
    with lens.trace("customer-support-agent") as trace_id:
        print(f"Started trace: {trace_id}")

        # Simulate LLM call
        user_input = "How do I reset my password?"
        print(f"User: {user_input}")

        lens.create_event(
            EventType.LLM_CALL,
            data={
                "model": "gpt-4",
                "prompt": user_input,
                "temperature": 0.7,
            },
        )

        # Simulate agent processing
        response = "To reset your password, visit the settings page..."
        print(f"Agent: {response}")

        lens.create_event(
            EventType.LLM_RESPONSE,
            data={
                "response": response,
                "tokens": 150,
            },
        )

        # Simulate tool call
        lens.create_event(
            EventType.TOOL_CALL,
            data={
                "tool": "search_knowledge_base",
                "query": "password reset procedures",
            },
        )

        lens.create_event(
            EventType.TOOL_RESPONSE,
            data={
                "results": [
                    {"title": "Password Reset Guide", "relevance": 0.95},
                    {"title": "Account Security", "relevance": 0.78},
                ]
            },
        )

        print("Trace completed successfully!")


def error_handling_example():
    """Example of error handling with AgentLens."""
    lens = AgentLens(enabled=False)

    try:
        with lens.trace("agent-with-error"):
            lens.create_event(
                EventType.LLM_CALL,
                data={"model": "gpt-4", "prompt": "test"},
            )

            # Simulate an error
            raise ValueError("Simulated error")

    except ValueError as e:
        print(f"Caught error: {e}")
        print("Error was automatically logged to trace")


def manual_trace_example():
    """Example of manual trace management."""
    lens = AgentLens(enabled=False)

    # Create trace manually
    trace = lens.create_trace("manual-agent", metadata={"version": "1.0"})
    print(f"Created trace: {trace.trace_id}")

    # Create events
    lens.create_event(
        EventType.AGENT_START,
        trace_id=trace.trace_id,
        data={"input": "Hello, world!"},
    )

    lens.create_event(
        EventType.STATE_CHANGE,
        trace_id=trace.trace_id,
        data={"state": "processing"},
    )

    lens.create_event(
        EventType.AGENT_END,
        trace_id=trace.trace_id,
        data={"output": "Task completed"},
    )

    # End trace
    lens.end_trace(trace.trace_id, status="completed")

    # Flush events
    lens.flush()
    print("Manual trace completed")

    # Close client
    lens.close()


if __name__ == "__main__":
    print("=== Simple Agent Example ===")
    simple_agent_example()

    print("\n=== Error Handling Example ===")
    error_handling_example()

    print("\n=== Manual Trace Example ===")
    manual_trace_example()
