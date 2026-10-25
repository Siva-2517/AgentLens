"""AgentLens Live Path and Investigation Performance Benchmark.

Measures:
1. Live Path Latency: Time from posting an event to receiving it on an active WebSocket client.
2. Investigation Latency: Execution time across 10 sequential AI investigation runs.
"""

import asyncio
import json
import time
import uuid
import httpx
import numpy as np
import websockets
from datetime import datetime, timezone

BASE_HTTP = "http://127.0.0.1:8000"
BASE_WS = "ws://127.0.0.1:8000"
HEADERS = {
    "Authorization": "Bearer test_api_key_123",
    "Content-Type": "application/json",
    "X-AgentLens-Project": "Default Project",
}


async def measure_live_path(num_trials: int = 10) -> list[float]:
    """Measure latency from HTTP event post to WebSocket reception."""
    print("\n" + "=" * 65)
    print("      PART 1: LIVE PATH LATENCY (HTTP POST -> WEBSOCKET RECEIVE)")
    print("=" * 65)

    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
        # 1. Provision a dedicated trace
        trace_id = f"live-path-trace-{uuid.uuid4().hex[:10]}"
        trace_data = {
            "trace_id": trace_id,
            "name": "Live Path Benchmark Trace",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        res = await client.post(f"{BASE_HTTP}/api/v1/traces", json=trace_data)
        if res.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create trace: {res.text}")
        print(f"Created live-path trace: {trace_id}")

        # 2. Connect WebSocket client
        ws_url = f"{BASE_WS}/api/v1/ws/traces/{trace_id}?token=test_api_key_123"
        print(f"Connecting WebSocket client to: {ws_url}...")

        async with websockets.connect(ws_url) as ws:
            # Ping/Pong handshake verification
            await ws.send("ping")
            pong = await ws.recv()
            assert pong == "pong", f"Expected pong, got {pong}"
            print("WebSocket handshake verified (ping/pong ok)\n")

            latencies_ms = []

            for i in range(1, num_trials + 1):
                target_event_id = f"evt-live-{uuid.uuid4().hex[:8]}"
                event_payload = {
                    "event_id": target_event_id,
                    "trace_id": trace_id,
                    "event_type": "TOOL_CALL" if i % 2 == 0 else "LLM_CALL",
                    "name": f"benchmark-live-event-{i}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {"trial": i, "timestamp_epoch": time.time()},
                }

                # Start listening on websocket before posting event
                receive_future = asyncio.ensure_future(ws.recv())

                # Post event and record start time
                t0 = time.perf_counter()
                post_res = await client.post(f"{BASE_HTTP}/api/v1/events/single", json=event_payload)
                if post_res.status_code != 201:
                    raise RuntimeError(f"Failed to post event: {post_res.text}")

                # Wait for websocket frame
                msg = await receive_future
                t1 = time.perf_counter()

                latency_ms = (t1 - t0) * 1000.0
                latencies_ms.append(latency_ms)

                # Verify payload identity
                try:
                    parsed = json.loads(msg)
                    rec_event_id = parsed.get("event", {}).get("event_id") or parsed.get("event_id")
                    match_str = "[OK] verified" if rec_event_id == target_event_id else f"(recv {rec_event_id})"
                except Exception:
                    match_str = "(raw frame)"

                print(f"  Trial {i:02d}/{num_trials}: {latency_ms:6.2f} ms  {match_str}")
                await asyncio.sleep(0.05)  # Brief breathing space

    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    mean_val = np.mean(latencies_ms)
    min_val = np.min(latencies_ms)
    max_val = np.max(latencies_ms)

    print("-" * 65)
    print(f"Live Path Latency Summary ({num_trials} trials):")
    print(f"  Min:  {min_val:6.2f} ms")
    print(f"  Mean: {mean_val:6.2f} ms")
    print(f"  p50:  {p50:6.2f} ms")
    print(f"  p95:  {p95:6.2f} ms")
    print(f"  Max:  {max_val:6.2f} ms")
    print("=" * 65)

    return latencies_ms


async def measure_investigations(num_runs: int = 10) -> list[float]:
    """Measure execution duration across 10 sequential AI investigation runs."""
    print("\n" + "=" * 65)
    print(f"      PART 2: INVESTIGATION LATENCY ({num_runs} SEQUENTIAL RUNS)")
    print("=" * 65)

    async with httpx.AsyncClient(headers=HEADERS, timeout=60.0) as client:
        # Provision a rich trace with agent lifecycle, tool call, and retry events
        trace_id = f"investigation-trace-{uuid.uuid4().hex[:10]}"
        trace_data = {
            "trace_id": trace_id,
            "name": "Customer Support Agent Workflow",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        await client.post(f"{BASE_HTTP}/api/v1/traces", json=trace_data)

        # Seed events: AGENT_START -> TOOL_CALL -> ERROR -> RETRY -> AGENT_END
        seed_events = [
            {
                "event_id": f"evt-inv-1-{uuid.uuid4().hex[:6]}",
                "trace_id": trace_id,
                "event_type": "AGENT_START",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"query": "Check order status for user #4092"},
            },
            {
                "event_id": f"evt-inv-2-{uuid.uuid4().hex[:6]}",
                "trace_id": trace_id,
                "event_type": "TOOL_CALL",
                "name": "lookup_database_order",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"tool": "lookup_database_order", "params": {"order_id": "ORD-4092"}},
            },
            {
                "event_id": f"evt-inv-3-{uuid.uuid4().hex[:6]}",
                "trace_id": trace_id,
                "event_type": "ERROR",
                "name": "DatabaseTimeout",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"error": "Connection timed out to inventory replica", "code": 504},
            },
            {
                "event_id": f"evt-inv-4-{uuid.uuid4().hex[:6]}",
                "trace_id": trace_id,
                "event_type": "RETRY",
                "name": "retry_lookup_database_order",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"attempt": 2, "backoff_ms": 500},
            },
            {
                "event_id": f"evt-inv-5-{uuid.uuid4().hex[:6]}",
                "trace_id": trace_id,
                "event_type": "AGENT_END",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"status": "failed", "final_error": "Order lookup failed after retry"},
            },
        ]
        await client.post(f"{BASE_HTTP}/api/v1/events", json=seed_events)
        print(f"Provisioned investigation trace with 5 lifecycle events: {trace_id}\n")

        investigation_latencies = []

        for r in range(1, num_runs + 1):
            t0 = time.perf_counter()
            inv_res = await client.get(f"{BASE_HTTP}/api/v1/traces/{trace_id}/investigation")
            t1 = time.perf_counter()

            if inv_res.status_code != 200:
                raise RuntimeError(f"Investigation run {r} failed with {inv_res.status_code}: {inv_res.text}")

            run_time_s = t1 - t0
            run_time_ms = run_time_s * 1000.0
            investigation_latencies.append(run_time_ms)

            inv_data = inv_res.json()
            status_val = inv_data.get("status")
            root_cause_desc = (inv_data.get("root_cause") or {}).get("description", "N/A")
            if len(root_cause_desc) > 35:
                root_cause_desc = root_cause_desc[:32] + "..."

            print(f"  Run {r:02d}/{num_runs}: {run_time_ms:7.2f} ms ({run_time_s:5.2f} s) | Status: {status_val:12s} | Root Cause: {root_cause_desc}")

    p50 = np.percentile(investigation_latencies, 50)
    p95 = np.percentile(investigation_latencies, 95)
    mean_val = np.mean(investigation_latencies)
    min_val = np.min(investigation_latencies)
    max_val = np.max(investigation_latencies)

    print("-" * 65)
    print(f"Investigation Latency Summary ({num_runs} runs):")
    print(f"  Min:  {min_val:7.2f} ms ({min_val/1000:.2f} s)")
    print(f"  Mean: {mean_val:7.2f} ms ({mean_val/1000:.2f} s)")
    print(f"  p50:  {p50:7.2f} ms ({p50/1000:.2f} s)")
    print(f"  p95:  {p95:7.2f} ms ({p95/1000:.2f} s)")
    print(f"  Max:  {max_val:7.2f} ms ({max_val/1000:.2f} s)")
    print("=" * 65)

    return investigation_latencies


async def main():
    await measure_live_path(num_trials=10)
    await measure_investigations(num_runs=10)


if __name__ == "__main__":
    asyncio.run(main())
