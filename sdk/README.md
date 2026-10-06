# AgentLens Python SDK

Python SDK for integrating AgentLens observability into AI agents.

## Installation

```bash
pip install -e .
```

## Development Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from agentlens import AgentLens, EventType

# Initialize the SDK
lens = AgentLens(
    api_url="http://localhost:8000",
    project_name="my-ai-agent",
)

# Use context manager for automatic trace management
with lens.trace("customer-support-agent"):
    # Your agent code here
    user_input = "How do I reset my password?"
    
    # Log LLM calls
    lens.create_event(
        EventType.LLM_CALL,
        data={
            "model": "gpt-4",
            "prompt": user_input,
        }
    )
    
    # Agent processes...
    response = "To reset your password, visit..."
    
    lens.create_event(
        EventType.LLM_RESPONSE,
        data={"response": response}
    )
    
    # Log tool calls
    lens.create_event(
        EventType.TOOL_CALL,
        data={
            "tool": "search_knowledge_base",
            "query": "password reset",
        }
    )
    
    lens.create_event(
        EventType.TOOL_RESPONSE,
        data={"results": ["article_1", "article_2"]}
    )

# Trace automatically ends and events are flushed
```

## Features

### Event Types

The SDK supports the following event types:

- `AGENT_START` - Agent execution begins
- `LLM_CALL` - LLM API call initiated
- `LLM_RESPONSE` - LLM response received
- `TOOL_CALL` - Tool/function call initiated
- `TOOL_RESPONSE` - Tool response received
- `STATE_CHANGE` - Agent state changed
- `RETRY` - Operation retry attempted
- `ERROR` - Error occurred
- `AGENT_END` - Agent execution completed

### Automatic Trace Management

Use the context manager for automatic trace lifecycle:

```python
with lens.trace("agent-name") as trace_id:
    # AGENT_START event created automatically
    # Your code here
    pass
    # AGENT_END event created automatically
    # Events flushed automatically
```

### Manual Trace Management

For more control:

```python
trace = lens.create_trace("manual-trace")

lens.create_event(
    EventType.LLM_CALL,
    trace_id=trace.trace_id,
    data={"model": "gpt-4"}
)

lens.end_trace(trace.trace_id, status="completed")
lens.flush()
```

### Error Handling

Errors are automatically captured:

```python
with lens.trace("agent-with-error"):
    try:
        # Your code
        risky_operation()
    except Exception as e:
        lens.create_event(
            EventType.ERROR,
            data={
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        )
        raise
# Trace status automatically set to "failed"
```

### Configuration

```python
from agentlens import AgentLens, AgentLensConfig

config = AgentLensConfig(
    api_url="http://localhost:8000",
    api_key="your_api_key",  # Optional
    project_name="my-project",
    enabled=True,  # Set to False to disable telemetry
    batch_size=100,  # Events before auto-flush
    timeout=5,  # HTTP timeout in seconds
)

lens = AgentLens(**config.model_dump())
```

### Disable Telemetry

```python
# Disable for testing or local development
lens = AgentLens(enabled=False)
```

### Nested Events

Track parent-child relationships:

```python
with lens.trace("main-agent"):
    parent_event = lens.create_event(
        EventType.TOOL_CALL,
        data={"tool": "orchestrator"}
    )
    
    # Child event
    lens.create_event(
        EventType.LLM_CALL,
        parent_event_id=parent_event.event_id,
        data={"model": "gpt-4"}
    )
```

## API Reference

### AgentLens

Main client class for the SDK.

**Methods:**

- `create_trace(name, trace_id=None, metadata=None)` - Create a new trace
- `end_trace(trace_id, status="completed")` - End a trace
- `create_event(event_type, data=None, trace_id=None, parent_event_id=None, metadata=None)` - Create an event
- `trace(name, trace_id=None, metadata=None)` - Context manager for tracing
- `flush()` - Manually flush pending events
- `close()` - Close client and flush events

### Event Types

All available event types are in the `EventType` enum:

```python
from agentlens import EventType

EventType.AGENT_START
EventType.LLM_CALL
EventType.LLM_RESPONSE
EventType.TOOL_CALL
EventType.TOOL_RESPONSE
EventType.STATE_CHANGE
EventType.RETRY
EventType.ERROR
EventType.AGENT_END
```

## Testing

Run tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=agentlens --cov-report=html
```

## Architecture

The SDK is designed to be lightweight and non-intrusive:

1. **Client** (`AgentLens`) - Main interface for creating traces and events
2. **Types** - Pydantic models for traces and events
3. **Context** - Thread-safe context management for traces
4. **Exporter** - HTTP client for sending data to AgentLens API
5. **Config** - Configuration management

## Requirements

- Python 3.11+
- httpx
- pydantic

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Format code:

```bash
black agentlens tests
```

Lint:

```bash
ruff check agentlens tests
```

## License

*To be determined*
