"""AgentLens Ingestion Performance Benchmark.

Posts 1,000-event batches to local backend 20 times (20,000 events total).
Measures and records events per second and p95 request time.
"""

import time
import uuid
import numpy as np
import requests
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8000"
HEADERS = {
    "Authorization": "Bearer test_api_key_123",
    "Content-Type": "application/json",
    "X-AgentLens-Project": "Default Project",
}

NUM_BATCHES = 20
BATCH_SIZE = 1000
TOTAL_EVENTS = NUM_BATCHES * BATCH_SIZE


def run_benchmark():
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Verify backend health
    health_res = session.get(f"{BASE_URL}/health")
    if health_res.status_code != 200:
        raise RuntimeError(f"Backend is not healthy: {health_res.text}")
    print(f"Backend health verified: {health_res.json()}")

    # 2. Provision benchmark trace
    trace_id = f"bench-trace-{uuid.uuid4().hex[:12]}"
    trace_payload = {
        "trace_id": trace_id,
        "name": "Ingestion Benchmark Trace",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "metadata_": {"benchmark": True, "batch_size": BATCH_SIZE, "batches": NUM_BATCHES},
    }
    trace_res = session.post(f"{BASE_URL}/api/v1/traces", json=trace_payload)
    if trace_res.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create benchmark trace: {trace_res.status_code} - {trace_res.text}")
    print(f"Provisioned benchmark trace: {trace_id}")

    # 3. Pre-generate all 20 batches to isolate backend ingestion from payload serialization time
    print(f"\nGenerating {NUM_BATCHES} batches of {BATCH_SIZE:,} events ({TOTAL_EVENTS:,} total events)...")
    t_gen_start = time.perf_counter()
    batches = []
    for b_idx in range(NUM_BATCHES):
        batch = []
        for i in range(BATCH_SIZE):
            batch.append({
                "event_id": str(uuid.uuid4()),
                "trace_id": trace_id,
                "event_type": "LLM_CALL" if i % 2 == 0 else "TOOL_CALL",
                "name": f"benchmark-event-{b_idx}-{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"batch": b_idx, "index": i, "payload": "benchmark_telemetry_event"},
            })
        batches.append(batch)
    t_gen_end = time.perf_counter()
    print(f"Payload generation completed in {t_gen_end - t_gen_start:.2f}s")

    # 4. Execute ingestion benchmark
    print(f"\nExecuting ingestion benchmark (20 requests x 1,000 events)...")
    latencies_ms = []

    wall_start = time.perf_counter()
    for b_idx, batch in enumerate(batches, start=1):
        t0 = time.perf_counter()
        res = session.post(f"{BASE_URL}/api/v1/events", json=batch)
        t1 = time.perf_counter()

        if res.status_code != 201:
            raise RuntimeError(f"Batch {b_idx} failed with {res.status_code}: {res.text}")

        batch_time_ms = (t1 - t0) * 1000.0
        latencies_ms.append(batch_time_ms)
        batch_events_per_sec = BATCH_SIZE / (t1 - t0)
        print(f"  Batch {b_idx:02d}/20: {batch_time_ms:7.2f} ms ({batch_events_per_sec:7.1f} events/s)", flush=True)

    wall_end = time.perf_counter()
    total_wall_time_s = wall_end - wall_start
    total_request_time_s = sum(latencies_ms) / 1000.0

    # 5. Compute performance statistics
    events_per_sec_wall = TOTAL_EVENTS / total_wall_time_s
    events_per_sec_pure = TOTAL_EVENTS / total_request_time_s

    p50 = np.percentile(latencies_ms, 50)
    p90 = np.percentile(latencies_ms, 90)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)
    min_time = np.min(latencies_ms)
    max_time = np.max(latencies_ms)
    mean_time = np.mean(latencies_ms)

    print("\n" + "=" * 60)
    print("           AGENTLENS INGESTION BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total Batches Ingested    : {NUM_BATCHES}")
    print(f"Batch Size                : {BATCH_SIZE:,} events/batch")
    print(f"Total Events Ingested     : {TOTAL_EVENTS:,} events")
    print(f"Total Wall Time           : {total_wall_time_s:.3f} s")
    print(f"Total Request Time (Sum)  : {total_request_time_s:.3f} s")
    print("-" * 60)
    print(f"Throughput (Wall Clock)   : {events_per_sec_wall:,.2f} events/second")
    print(f"Throughput (Request Time) : {events_per_sec_pure:,.2f} events/second")
    print("-" * 60)
    print(f"Mean Batch Request Time   : {mean_time:7.2f} ms")
    print(f"Min Batch Request Time    : {min_time:7.2f} ms")
    print(f"p50 Batch Request Time    : {p50:7.2f} ms")
    print(f"p90 Batch Request Time    : {p90:7.2f} ms")
    print(f"p95 Batch Request Time    : {p95:7.2f} ms (p95 request time)")
    print(f"p99 Batch Request Time    : {p99:7.2f} ms")
    print(f"Max Batch Request Time    : {max_time:7.2f} ms")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
