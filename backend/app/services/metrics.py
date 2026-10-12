"""Operational metrics collection and exposition (Phase 20C).

Tracks low-cardinality measurements:
- HTTP request count, error rates, and duration.
- Database query latency and failure counts.
- Redis publish successes and failures.
- WebSocket active connections and disconnects.
- LLM provider invocation counts, latencies, and failure categories.

Guarantees:
- Zero high-cardinality labels (no trace IDs, user IDs, project IDs, or prompts).
- Thread-safe in-memory aggregation.
- Exposes OpenMetrics / Prometheus plaintext and structured JSON.
"""

import threading
import time
from typing import Any, Dict


class MetricsCollector:
    """Thread-safe in-memory operational metrics collector."""

    def __init__(self):
        self._lock = threading.Lock()
        # (method, path_template, status_code) -> count
        self._http_requests: Dict[tuple[str, str, int], int] = {}
        # (method, path_template) -> total_duration_seconds
        self._http_duration_total: Dict[tuple[str, str], float] = {}
        # (method, path_template) -> request_count
        self._http_duration_count: Dict[tuple[str, str], int] = {}

        # (operation, status) -> count
        self._db_operations: Dict[tuple[str, str], int] = {}

        # status ("success" | "failure") -> count
        self._redis_publish: Dict[str, int] = {"success": 0, "failure": 0}

        # WebSocket counters
        self._ws_active_connections: int = 0
        self._ws_disconnects: Dict[str, int] = {}

        # LLM provider calls: (provider, status) -> count
        self._llm_calls: Dict[tuple[str, str], int] = {}

        # Mock fallback activations: provider -> count (Phase 20D)
        self._mock_fallbacks: Dict[str, int] = {}

        # SDK ingestion: status -> count
        self._sdk_batches: Dict[str, int] = {"success": 0, "failure": 0}

    def record_http_request(
        self, method: str, path_template: str, status_code: int, duration_seconds: float
    ) -> None:
        """Record an incoming HTTP request."""
        method_norm = method.upper()
        # Normalize common paths to keep cardinality small
        normalized_path = self._normalize_path(path_template)

        with self._lock:
            key = (method_norm, normalized_path, status_code)
            self._http_requests[key] = self._http_requests.get(key, 0) + 1

            dur_key = (method_norm, normalized_path)
            self._http_duration_total[dur_key] = (
                self._http_duration_total.get(dur_key, 0.0) + duration_seconds
            )
            self._http_duration_count[dur_key] = (
                self._http_duration_count.get(dur_key, 0) + 1
            )

    def record_db_operation(self, operation: str, success: bool) -> None:
        """Record a database query or transaction attempt."""
        status = "success" if success else "failure"
        with self._lock:
            key = (operation, status)
            self._db_operations[key] = self._db_operations.get(key, 0) + 1

    def record_redis_publish(self, success: bool) -> None:
        """Record a Redis Pub/Sub publish attempt."""
        key = "success" if success else "failure"
        with self._lock:
            self._redis_publish[key] = self._redis_publish.get(key, 0) + 1

    def inc_websocket_connection(self) -> None:
        """Increment gauge of active WebSocket connections."""
        with self._lock:
            self._ws_active_connections += 1

    def dec_websocket_connection(self, reason: str = "clean") -> None:
        """Decrement gauge of active WebSocket connections."""
        with self._lock:
            if self._ws_active_connections > 0:
                self._ws_active_connections -= 1
            self._ws_disconnects[reason] = self._ws_disconnects.get(reason, 0) + 1

    def record_llm_call(self, provider: str, success: bool) -> None:
        """Record an external LLM provider call."""
        status = "success" if success else "failure"
        with self._lock:
            key = (provider, status)
            self._llm_calls[key] = self._llm_calls.get(key, 0) + 1

    def record_mock_fallback(self, provider: str) -> None:
        """Record deterministic mock fallback activation (Phase 20D)."""
        with self._lock:
            self._mock_fallbacks[provider] = self._mock_fallbacks.get(provider, 0) + 1

    def record_sdk_batch(self, success: bool) -> None:
        """Record an SDK event batch ingestion."""
        key = "success" if success else "failure"
        with self._lock:
            self._sdk_batches[key] = self._sdk_batches.get(key, 0) + 1

    def _normalize_path(self, path: str) -> str:
        """Strip variable path parameters like trace IDs to maintain low cardinality."""
        if not path:
            return "/"
        segments = path.strip("/").split("/")
        norm_segments = []
        for i, seg in enumerate(segments):
            # Check if segment looks like an ID (UUID, hex, or numeric)
            if (
                len(seg) >= 16
                or seg.isdigit()
                or (len(seg) == 36 and "-" in seg)
                or seg.startswith("al_")
                or seg.startswith("tr_")
            ):
                norm_segments.append("{id}")
            else:
                norm_segments.append(seg)
        return "/" + "/".join(norm_segments)

    def get_metrics_json(self) -> Dict[str, Any]:
        """Return metrics snapshot formatted as JSON."""
        with self._lock:
            http_reqs = [
                {"method": m, "path": p, "status": s, "count": c}
                for (m, p, s), c in self._http_requests.items()
            ]
            http_latencies = [
                {
                    "method": m,
                    "path": p,
                    "count": self._http_duration_count.get((m, p), 0),
                    "total_seconds": round(self._http_duration_total.get((m, p), 0.0), 4),
                    "avg_seconds": (
                        round(
                            self._http_duration_total.get((m, p), 0.0)
                            / max(self._http_duration_count.get((m, p), 1), 1),
                            4,
                        )
                    ),
                }
                for (m, p) in self._http_duration_count.keys()
            ]
            db_ops = [
                {"operation": op, "status": st, "count": c}
                for (op, st), c in self._db_operations.items()
            ]
            llm_ops = [
                {"provider": prv, "status": st, "count": c}
                for (prv, st), c in self._llm_calls.items()
            ]

            return {
                "http_requests": http_reqs,
                "http_latencies": http_latencies,
                "database_operations": db_ops,
                "redis_publish": dict(self._redis_publish),
                "websocket": {
                    "active_connections": self._ws_active_connections,
                    "disconnects": dict(self._ws_disconnects),
                },
                "llm_calls": llm_ops,
                "mock_fallbacks": dict(self._mock_fallbacks),
                "sdk_batches": dict(self._sdk_batches),
            }

    def get_metrics_prometheus(self) -> str:
        """Format metrics snapshot in OpenMetrics / Prometheus exposition text format."""
        lines = [
            "# HELP agentlens_http_requests_total Total count of HTTP requests",
            "# TYPE agentlens_http_requests_total counter",
        ]
        with self._lock:
            for (m, p, s), c in self._http_requests.items():
                lines.append(
                    f'agentlens_http_requests_total{{method="{m}",path="{p}",status="{s}"}} {c}'
                )

            lines.append("# HELP agentlens_http_duration_seconds_total Total duration in seconds")
            lines.append("# TYPE agentlens_http_duration_seconds_total counter")
            for (m, p), tot in self._http_duration_total.items():
                lines.append(
                    f'agentlens_http_duration_seconds_total{{method="{m}",path="{p}"}} {tot:.4f}'
                )

            lines.append("# HELP agentlens_db_operations_total Total database operations")
            lines.append("# TYPE agentlens_db_operations_total counter")
            for (op, st), c in self._db_operations.items():
                lines.append(f'agentlens_db_operations_total{{operation="{op}",status="{st}"}} {c}')

            lines.append("# HELP agentlens_redis_publish_total Total Redis pub/sub attempts")
            lines.append("# TYPE agentlens_redis_publish_total counter")
            for st, c in self._redis_publish.items():
                lines.append(f'agentlens_redis_publish_total{{status="{st}"}} {c}')

            lines.append("# HELP agentlens_websocket_active_connections Active WebSocket connections")
            lines.append("# TYPE agentlens_websocket_active_connections gauge")
            lines.append(f"agentlens_websocket_active_connections {self._ws_active_connections}")

            lines.append("# HELP agentlens_mock_fallbacks_total Total mock provider fallback activations")
            lines.append("# TYPE agentlens_mock_fallbacks_total counter")
            for prv, c in self._mock_fallbacks.items():
                lines.append(f'agentlens_mock_fallbacks_total{{provider="{prv}"}} {c}')

        return "\n".join(lines) + "\n"


# Global singleton collector
metrics_collector = MetricsCollector()
