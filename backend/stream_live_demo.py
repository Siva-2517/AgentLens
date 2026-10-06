"""Stream live agent execution events for browser verification."""

import asyncio
import json
import time
import urllib.request
import uuid

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "test_api_key_123"

def http_post(endpoint: str, data: dict | list):
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "X-AgentLens-Project": "realtime-demo",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

async def run_live_stream():
    trace_id = f"live-trace-{uuid.uuid4().hex[:8]}"
    print(f"TRACE_ID: {trace_id}")

    # 1. Start Trace
    start_payload = {
        "trace_id": trace_id,
        "name": "Live Support Agent Execution",
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "running",
        "metadata": {"environment": "production"},
    }
    http_post("/traces", start_payload)
    print("Trace started.")

    # Pause to allow browser to connect to the trace
    await asyncio.sleep(4)

    # 2. Agent Start
    e1_id = f"evt-start-{uuid.uuid4().hex[:6]}"
    http_post("/events", [{
        "event_id": e1_id,
        "trace_id": trace_id,
        "event_type": "AGENT_START",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {"query": "Track expedited shipment ORD-9988"},
        "metadata": {},
    }])
    print("Sent: AGENT_START")
    await asyncio.sleep(1.5)

    # 3. LLM Call
    e2_id = f"evt-llm-{uuid.uuid4().hex[:6]}"
    http_post("/events", [{
        "event_id": e2_id,
        "trace_id": trace_id,
        "parent_event_id": e1_id,
        "event_type": "LLM_CALL",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {"model": "llama3-70b-8192", "prompt": "Extract order ID and determine tool to call"},
        "metadata": {"tokens": 128},
    }])
    print("Sent: LLM_CALL")
    await asyncio.sleep(1.5)

    # 4. Tool Call
    e3_id = f"evt-tool-{uuid.uuid4().hex[:6]}"
    http_post("/events", [{
        "event_id": e3_id,
        "trace_id": trace_id,
        "parent_event_id": e2_id,
        "event_type": "TOOL_CALL",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {"tool": "get_shipping_status", "order_id": "ORD-9988"},
        "metadata": {},
    }])
    print("Sent: TOOL_CALL")
    await asyncio.sleep(1.5)

    # 5. Tool Response
    e4_id = f"evt-toolres-{uuid.uuid4().hex[:6]}"
    http_post("/events", [{
        "event_id": e4_id,
        "trace_id": trace_id,
        "parent_event_id": e3_id,
        "event_type": "TOOL_RESPONSE",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {"status": "in_transit", "carrier": "FedEx", "eta": "Tomorrow by 3 PM"},
        "metadata": {"cache_hit": False},
    }])
    print("Sent: TOOL_RESPONSE")
    await asyncio.sleep(1.5)

    # 6. LLM Response
    e5_id = f"evt-llmres-{uuid.uuid4().hex[:6]}"
    http_post("/events", [{
        "event_id": e5_id,
        "trace_id": trace_id,
        "parent_event_id": e2_id,
        "event_type": "LLM_RESPONSE",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {"content": "Your order ORD-9988 is currently in transit with FedEx and scheduled for delivery tomorrow by 3 PM."},
        "metadata": {"completion_tokens": 42},
    }])
    print("Sent: LLM_RESPONSE")
    await asyncio.sleep(1.5)

    # 7. Agent End
    e6_id = f"evt-end-{uuid.uuid4().hex[:6]}"
    http_post("/events", [{
        "event_id": e6_id,
        "trace_id": trace_id,
        "parent_event_id": e1_id,
        "event_type": "AGENT_END",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {"status": "completed", "output": "Order delivery update delivered to customer."},
        "metadata": {},
    }])
    print("Sent: AGENT_END")

    # Complete trace
    http_post("/traces", {
        "trace_id": trace_id,
        "name": "Live Support Agent Execution",
        "start_time": start_payload["start_time"],
        "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "completed",
        "metadata": {"environment": "production", "total_steps": 6},
    })
    print("Trace completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_live_stream())
