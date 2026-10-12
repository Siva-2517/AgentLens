# AgentLens Operational Recovery, Monitoring & Reliability Guide

## 1. Health and Readiness Semantics

AgentLens provides distinct probes designed for container orchestrators (Kubernetes, Docker Swarm, Cloud Run, ECS):

| Endpoint | Type | Purpose | Timeout | Success Code | Failure Code |
|---|---|---|---|---|---|
| `GET /health/live` | **Liveness Probe** | Verifies the FastAPI application event loop is alive. | N/A | `200 OK` (`{"status": "alive"}`) | Process dead / unresponsive |
| `GET /health/ready` | **Readiness Probe** | Verifies datastore and cache connectivity before routing traffic. | Bounded (2.0s) | `200 OK` (`{"status": "healthy"}`) or `200 OK` (`{"status": "degraded"}`) | `503 Service Unavailable` |
| `GET /health` | **General Health** | Mirrors readiness probe with operational service breakdown. | Bounded (2.0s) | `200 OK` | `503 Service Unavailable` |

### Readiness Decision Matrix
- **Database Connected + Redis Connected**: Returns `200 OK` with `status: "healthy"`, `ready: true`.
- **Database Connected + Redis Disconnected**: 
  - In single-instance deployment, returns `200 OK` with `status: "degraded"`, `ready: true`, and `services.redis: "degraded (local fallback active)"`. Ingestion and local WebSockets operate normally via in-memory broadcast.
- **Database Disconnected**: Returns `503 Service Unavailable` with `status: "unhealthy"`, `ready: false`. No traffic should be routed to this instance.

> [!IMPORTANT]
> Health check responses never disclose connection strings, passwords, hostnames, or exception tracebacks.

---

## 2. Redis Pub/Sub Semantics & Delivery Guarantees

### Delivery Model
Redis Pub/Sub in AgentLens operates on an **at-most-once, fire-and-forget** delivery model:
1. **Not a Durable Queue**: Messages published to `agentlens:trace:{trace_id}` are delivered strictly to active subscribers connected at the moment of publication. Redis does not buffer messages for disconnected clients.
2. **Persistence Source of Truth**: Durable trace storage, anomaly findings, and event history are stored exclusively in PostgreSQL. Clients reconnecting after network drops fetch the authoritative historical state from the REST API (`/api/v1/traces/{trace_id}`).
3. **Single vs. Multi-Instance Deployment**:
   - **Single-Instance**: Even if Redis fails or is unconfigured, `RealtimePublisher` falls back to `broadcast_locally()`, streaming events in-memory to all WebSockets connected to that server.
   - **Multi-Instance (Clustered)**: Shared Redis is required to fan out events across distinct backend server instances. If Redis drops in a cluster, instances continue servicing local subscribers while attempting reconnection with bounded backoff.

---

## 3. Database Outage Response & Recovery

### Failure Behavior
- If Neon PostgreSQL encounters network partitioning, SSL drops, or maintenance:
  1. Active queries fail fast via `command_timeout=30s` and `pool_timeout=15s`.
  2. The connection pool automatically tests connections before checkout using `pool_pre_ping=True`. Stale idle connections are recycled every 30 minutes (`pool_recycle=1800s`).
  3. HTTP state-changing requests roll back transactions cleanly and return `HTTP 500` with generic details: `{"detail": "Internal server error occurred."}`.
  4. The `/health/ready` endpoint flips to `HTTP 503`, signaling load balancers to withhold traffic.

### Recovery Procedure
1. Verify database availability via Neon Console or CLI.
2. Once the database resumes responding to `SELECT 1`, the connection pool automatically re-establishes healthy sessions.
3. Check `GET /health/ready` until `services.database == "connected"`.

---

## 4. Safe Restart Procedure

When cycling containers or updating releases:

1. **Send `SIGTERM`**:
   - The FastAPI `lifespan` manager intercepts the termination signal.
2. **WebSocket Drainage**:
   - `realtime_service.close_all()` sends close code `1001` ("Server shutting down") to all active WebSockets.
   - Cancels all active background Redis subscriber tasks (`asyncio.Task`).
3. **Cache & Pool Disposal**:
   - `realtime_publisher.close()` closes async Redis connection pools.
   - `close_db()` disposes of the SQLAlchemy async engine, awaiting active session terminations.
4. **Grace Period**:
   - Allow a minimum 10-second termination grace period in container orchestrators.

---

## 5. Database Backup and Restore Verification

### Neon Point-in-Time Recovery (PITR)
Neon PostgreSQL maintains automated continuous WAL backups and instant branching:
1. **Create Branch / Snapshot**:
   ```bash
   neon branches create --project-id <project_id> --name recovery-test
   ```
2. **Verify Schema Post-Restore**:
   Ensure `pgvector` extension and HNSW cosine indexes are active:
   ```sql
   SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
   SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'failure_embeddings';
   ```
3. **Smoke Verification**:
   Run `pytest tests/test_postgres_integration.py` against the restored staging database.

---

## 6. Credential Rotation Implications

| Credential | Rotation Method | Downtime / User Impact |
|---|---|---|
| `JWT_SECRET_KEY` | Update environment variable and trigger restart. | **Zero Downtime**: Immediately invalidates all outstanding JWT access and refresh tokens. Active users will receive 401 and must log in again. |
| Ingestion API Keys (`al_live_...`) | Issue new project API key in dashboard; revoke old key. | **Zero Downtime**: The system stores SHA-256 key hashes. Both keys remain valid during transition until the old key is revoked. |
| `DATABASE_URL` | Update environment variable and perform rolling restart. | **Zero Downtime**: Pre-ping connection pool switches to new credentials without connection pool leakage. |
| `REDIS_URL` | Update environment variable and perform rolling restart. | **Zero Downtime**: Temporary fallback to local in-memory broadcast during container replacement. |

---

## 7. Structured Logging & Secret Redaction

### Architecture
- All log records pass through `RedactingFilter` in [logging_config.py](file:///D:/AgentLens/backend/app/services/logging_config.py).
- Masks:
  - Database URLs (`postgresql://`, `postgresql+asyncpg://`, `mysql://`, `rediss://`, `redis://`)
  - JWT Tokens (`eyJhbGci...`)
  - Authorization headers (`Bearer ...`)
  - AgentLens API keys (`al_live_...`, `al_test_...`)
  - External keys (`sk-...`, `AIzaSy...`, `gsk_...`)
  - Key-value credentials (`password=...`, `jwt_secret_key=...`)
- **Correlation ID**: Every HTTP request receives an `X-Request-ID` / `X-Correlation-ID` header, propagated through `correlation_id_ctx` into structured JSON logs.
- **MCP Server Stdio Separation**: The Model Context Protocol server logs exclusively to `sys.stderr`, ensuring `sys.stdout` remains pristine for JSON-RPC messages.

---

## 8. Operational Metrics & Observability

Low-cardinality metrics are exposed without third-party vendor dependencies:

### Endpoints
- **Prometheus Text Format**: `GET /metrics`
- **JSON Snapshot**: `GET /api/v1/metrics`

### Metric Dictionary
- `agentlens_http_requests_total{method, path, status}`: Cumulative request count partitioned by method, template path, and status code.
- `agentlens_http_duration_seconds_total{method, path}`: Cumulative request latency for calculating average latency.
- `agentlens_db_operations_total{operation, status}`: Database transaction success/failure counts.
- `agentlens_redis_publish_total{status}`: Redis Pub/Sub successes and failures.
- `agentlens_websocket_active_connections`: Gauge of currently connected WebSockets.
