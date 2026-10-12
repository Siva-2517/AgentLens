#!/usr/bin/env python
"""AgentLens Real-Time Telemetry Streamer.

Simulates a live, multi-step AI agent execution by posting events step-by-step
with configurable pauses (default 1.5s). Connect your browser to the AgentLens
frontend dashboard to watch nodes, links, and logs animate in real time!

Usage:
    # Run standard successful agent workflow (1.5s step delay)
    python backend/stream_live_demo.py

    # Run with a failure to test AI Root Cause Analysis & pgvector matching
    python backend/stream_live_demo.py --simulate-failure

    # Customize step delay
    python backend/stream_live_demo.py --interval 2.0
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure UTF-8 console output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def find_and_load_env() -> None:
    """Load configuration from demo/.env or backend/.env if available."""
    try:
        from dotenv import load_dotenv

        current_dir = Path(__file__).resolve().parent
        demo_env = current_dir.parent / "demo" / ".env"
        backend_env = current_dir / ".env"

        if demo_env.is_file():
            load_dotenv(demo_env)
        if backend_env.is_file():
            load_dotenv(backend_env, override=False)
    except ImportError:
        pass


def make_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
) -> Dict[str, Any]:
    """Perform an HTTP request using Python's standard library urllib."""
    req_headers = {"User-Agent": "AgentLens-LiveStreamer/1.0"}
    if headers:
        req_headers.update(headers)

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            content = response.read().decode("utf-8")
            if content:
                try:
                    return {"status": status_code, "body": json.loads(content)}
                except json.JSONDecodeError:
                    return {"status": status_code, "body": content}
            return {"status": status_code, "body": None}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(error_body)
        except Exception:
            parsed = error_body
        return {"status": e.code, "error": parsed}
    except Exception as e:
        return {"status": 0, "error": str(e)}


def main():
    find_and_load_env()

    parser = argparse.ArgumentParser(
        description="Stream real-time agent execution events to AgentLens dashboard."
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("AGENTLENS_API_URL", "http://localhost:8000"),
        help="Target AgentLens API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("AGENTLENS_API_KEY", ""),
        help="AgentLens Ingestion API Key (al_live_... or legacy test key)",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("AGENTLENS_PROJECT_NAME", "Default Project"),
        help="Project name to bind traces to (default: Default Project)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.5,
        help="Delay in seconds between streaming each event (default: 1.5)",
    )
    parser.add_argument(
        "--simulate-failure",
        action="store_true",
        help="Simulate an unhandled agent failure to test Root Cause Analysis",
    )
    args = parser.parse_args()

    api_base = args.api_url.rstrip("/")
    api_key = args.api_key or os.getenv("AGENTLENS_API_KEY", "") or "test_api_key_123"
    project_name = args.project
    interval = args.interval
    simulate_failure = args.simulate_failure

    timestamp_str = datetime.now().strftime("%H%M%S")
    suffix = uuid.uuid4().hex[:4]
    trace_id = f"live-stream-{timestamp_str}-{suffix}"
    trace_name = (
        "Live Failure Root Cause Stream"
        if simulate_failure
        else "Real-Time Agent Execution (Live Demo)"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-AgentLens-Project": project_name,
    }

    print("\n" + "=" * 70)
    print("🚀 AGENTLENS REAL-TIME EXECUTION STREAMER")
    print("=" * 70)
    print(f"Target API     : {api_base}")
    print(f"Target Project : {project_name}")
    print(f"Trace ID       : {trace_id}")
    print(f"Trace Name     : {trace_name}")
    print(f"Step Interval  : {interval:.1f}s")
    print(f"Mode           : {'Simulated Error / Failure' if simulate_failure else 'Normal Resolution'}")
    print("-" * 70)
    print("👀 HOW TO WATCH LIVE IN DASHBOARD:")
    print("   1. Open: http://localhost:5173")
    print("   2. Log in and open your project dashboard")
    print(f"   3. Click on Trace '{trace_id}' once it appears")
    print("   4. Watch the nodes link, animate, and update in real time!")
    print("=" * 70 + "\n")

    # Step 1: Create the Trace
    print(f"[*] Initializing trace: {trace_id}...")
    trace_payload = {
        "trace_id": trace_id,
        "name": trace_name,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "metadata": {
            "environment": "live_demo",
            "stream_interval_seconds": interval,
            "agent_version": "1.4.2",
            "simulator": "stream_live_demo.py",
        },
    }

    trace_resp = make_request(
        f"{api_base}/api/v1/traces",
        method="POST",
        headers=headers,
        data=trace_payload,
    )

    if trace_resp.get("status") not in (200, 201):
        # In case the key is invalid or backend returned error
        print(f"[!] Warning creating trace ({trace_resp.get('status')}): {trace_resp.get('error')}")
        print("    Proceeding to event streaming (trace will auto-provision on first event)...")
    else:
        print(f"[✓] Trace initialized successfully: {trace_id}")

    time.sleep(1.0)

    # Define Event Sequence
    events_sequence = [
        {
            "step": 1,
            "name": "Customer Support Session Initialized",
            "type": "AGENT_START",
            "data": {
                "query": "Where is my replacement headset #ORD-7749 and what is its warranty status?",
                "customer_id": "cust_99214",
                "priority": "normal",
                "channel": "web_chat",
            },
            "parent_index": None,
        },
        {
            "step": 2,
            "name": "Supervisor Router: Intent Classification",
            "type": "STATE_CHANGE",
            "data": {
                "previous_state": "idle",
                "current_state": "routing",
                "route_decision": "parallel_lookup",
                "intent": "order_tracking_and_warranty",
                "confidence": 0.98,
            },
            "parent_index": 0,
        },
        {
            "step": 3,
            "name": "Tool Call: query_order_warehouse",
            "type": "TOOL_CALL",
            "data": {
                "tool_name": "query_order_warehouse",
                "parameters": {"order_id": "ORD-7749", "include_carrier_telemetry": True},
            },
            "parent_index": 1,
        },
        {
            "step": 4,
            "name": "Tool Response: Order Telemetry Received",
            "type": "TOOL_RESPONSE",
            "data": {
                "order_id": "ORD-7749",
                "item": "Quantum ANC Pro Headset",
                "status": "Out for Delivery",
                "carrier": "FedEx Express",
                "tracking_number": "FX-882194129",
                "estimated_delivery": "Today by 4:30 PM",
            },
            "parent_index": 2,
        },
        {
            "step": 5,
            "name": "Tool Call: check_warranty_status",
            "type": "TOOL_CALL",
            "data": {
                "tool_name": "check_warranty_status",
                "parameters": {"customer_id": "cust_99214", "product_code": "Q-ANC-PRO"},
            },
            "parent_index": 1,
        },
    ]

    if simulate_failure:
        events_sequence.extend([
            {
                "step": 6,
                "name": "Tool Response: Warranty Service Timeout",
                "type": "ERROR",
                "data": {
                    "error_type": "UpstreamServiceTimeoutError",
                    "status_code": 504,
                    "service": "warranty-microservice.internal",
                    "message": "Gateway timeout: warranty-microservice failed to respond within 5000ms",
                    "retries_attempted": 3,
                },
                "parent_index": 4,
            },
            {
                "step": 7,
                "name": "Workflow Failed",
                "type": "AGENT_END",
                "data": {
                    "final_status": "failed",
                    "unresolved_errors": ["UpstreamServiceTimeoutError: 504 Gateway Timeout"],
                    "duration_ms": 7800,
                },
                "parent_index": 0,
            },
        ])
    else:
        events_sequence.extend([
            {
                "step": 6,
                "name": "Tool Response: Warranty Verified",
                "type": "TOOL_RESPONSE",
                "data": {
                    "warranty_active": True,
                    "tier": "Premium Platinum",
                    "valid_until": "2027-11-30",
                    "coverage": "Full accidental damage & battery replacement",
                },
                "parent_index": 4,
            },
            {
                "step": 7,
                "name": "LLM Synthesis: LLaMA 3 70B Reasoning",
                "type": "LLM_CALL",
                "data": {
                    "model": "llama-3.3-70b-versatile",
                    "provider": "Groq",
                    "prompt_tokens": 420,
                    "temperature": 0.1,
                    "prompt_preview": "Synthesize order tracking and warranty details into a helpful response...",
                },
                "parent_index": 1,
            },
            {
                "step": 8,
                "name": "LLM Generation: Response Formatted",
                "type": "LLM_RESPONSE",
                "data": {
                    "completion_tokens": 78,
                    "total_tokens": 498,
                    "latency_ms": 382,
                    "response_text": (
                        "Hello! Your Quantum ANC Pro Headset (#ORD-7749) is currently out for "
                        "delivery with FedEx Express (Tracking #FX-882194129) and will arrive today by 4:30 PM. "
                        "Furthermore, your Premium Platinum warranty remains active through November 2027."
                    ),
                },
                "parent_index": 6,
            },
            {
                "step": 9,
                "name": "Session Complete: Customer Inquiry Resolved",
                "type": "AGENT_END",
                "data": {
                    "final_status": "completed",
                    "duration_ms": 9400,
                    "total_tokens_consumed": 498,
                    "satisfaction_prediction": 0.99,
                },
                "parent_index": 0,
            },
        ])

    created_event_ids = []

    for item in events_sequence:
        step_num = item["step"]
        total_steps = len(events_sequence)
        event_name = item["name"]
        event_type = item["type"]
        parent_idx = item["parent_index"]
        parent_id = created_event_ids[parent_idx] if parent_idx is not None else None

        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        created_event_ids.append(event_id)

        event_payload = {
            "event_id": event_id,
            "trace_id": trace_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parent_event_id": parent_id,
            "data": item["data"],
            "metadata": {
                "step_name": event_name,
                "sequence_order": step_num,
                "source": "stream_live_demo",
            },
        }

        # Post single event to /api/v1/events/single or batch /api/v1/events
        post_resp = make_request(
            f"{api_base}/api/v1/events",
            method="POST",
            headers=headers,
            data=[event_payload],
        )

        status_code = post_resp.get("status")
        if status_code in (200, 201):
            status_icon = "✓"
        else:
            status_icon = "✗"
            print(f"    [Error details]: {post_resp.get('error')}")

        print(
            f"[{step_num}/{total_steps}] {status_icon} Streamed {event_type:<14} "
            f"| {event_name[:38]:<38} (ID: {event_id[:12]})"
        )

        # Wait the requested interval so the user can observe live WebSocket node animation
        if step_num < total_steps:
            time.sleep(interval)

    # Final trace update
    final_status = "failed" if simulate_failure else "completed"
    print(f"\n[*] Finalizing trace status -> '{final_status}'...")
    end_payload = {
        "end_time": datetime.now(timezone.utc).isoformat(),
        "status": final_status,
    }
    make_request(
        f"{api_base}/api/v1/traces/{trace_id}",
        method="PATCH",
        headers=headers,
        data=end_payload,
    )

    print("\n" + "=" * 70)
    print("🎉 REAL-TIME STREAMING EXECUTION COMPLETE!")
    print(f"Total Events Sent : {len(events_sequence)}")
    print(f"Trace Identifier  : {trace_id}")
    print(f"Final State       : {final_status.upper()}")
    print("-" * 70)
    print("Check your dashboard at http://localhost:5173 to review the execution graph,")
    print("timelines, latency breakdowns, and root-cause telemetry.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
