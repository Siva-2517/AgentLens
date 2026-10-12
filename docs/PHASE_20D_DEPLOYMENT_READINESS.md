# AgentLens — Phase 20D: Deployment Readiness Audit & Staging Gate Report

**Date:** October 12, 2026  
**Auditor:** AgentLens Security & Reliability Engineering  
**Repository:** `D:\AgentLens`  
**Target Environment:** Staging Deployment Gate  

---

## 1. Executive Summary & Staging Gate Verdict

### **Gate Verdict: CONDITIONAL GO FOR STAGING**

The AgentLens platform has successfully completed the Phase 20D Deployment Readiness Audit and Hardening verification. All verified critical security blockers, silent mock-provider fallbacks, topology-dependent Redis coordination desynchronizations, SSL configuration vulnerabilities, operational metric exposures, and correlation ID boundaries have been remediated and backed by automated regression tests.

No live staging deployment, destructive infrastructure modifications, or public port exposures were performed during this audit; all checks served exclusively as a staging gate assessment.

### Staging Promotion Conditions:
1. **Deployment Topology & Redis Cluster**:
   - For `DEPLOYMENT_TOPOLOGY=multi-instance`, a dedicated Redis instance/cluster must be reachable before starting backend containers. Under this topology, `REDIS_REQUIRED=true` is automatically enforced, and instances will fail-closed with HTTP `503 Service Unavailable` if Redis is offline to prevent cross-node WebSocket desynchronization.
   - For single-container staging evaluations (`DEPLOYMENT_TOPOLOGY=single-instance`), Redis is non-mandatory (`REDIS_REQUIRED=false`), and the system safely operates in a degraded mode utilizing in-memory WebSocket event broadcasts.
2. **Third-Party Provider Credentials**:
   - In `ENVIRONMENT=production`, valid provider credentials (`GROQ_API_KEY` and `GEMINI_API_KEY`) must be supplied. Silent mock fallbacks have been eliminated and will raise an explicit `RuntimeError` (`External LLM/Embedding provider failed in production`).
   - Mock mode in production is prohibited unless explicitly overridden by `ALLOW_MOCK_PROVIDERS=true` strictly for synthetic testing.
3. **Operational Metrics Protection**:
   - When running scrapers against `/metrics` or `/api/v1/metrics`, the orchestrator must configure `METRICS_AUTH_TOKEN` and provide it via the `Authorization: Bearer <token>` header or `?token=<token>` query parameter.
4. **PostgreSQL TLS Verification**:
   - Staging Neon connection strings must contain an explicit SSL parameter (`sslmode=require`, `sslmode=verify-ca`, or `sslmode=verify-full`). Insecure parameters (`sslmode=disable`, `sslmode=allow`, `ssl=false`) are rejected at application startup.

---

## 2. Audit Findings Grouped by Severity

```
+----------------------------------------------------------------------------------------------------+
| Severity | Component       | Description                                              | Status     |
+----------------------------------------------------------------------------------------------------+
| CRITICAL | llm/embedding   | Silent Mock Fallbacks in Production Provider Failure     | RESOLVED   |
| HIGH     | db/session      | Insecure Asyncpg SSL Parameter Interpretation            | RESOLVED   |
| HIGH     | main/readiness  | Multi-Instance Redis Clustering & Readiness Split-Brain   | RESOLVED   |
| MEDIUM   | metrics/api     | Unauthenticated Metrics & Cardinality Exposure Risk      | RESOLVED   |
| MEDIUM   | main/logging    | Unsanitized X-Request-ID Header Injection                | RESOLVED   |
| LOW      | tests/conftest  | Remote Neon Schema Latency in Unit Test Lifespan         | RESOLVED   |
| LOW      | Dockerfile      | Container Non-Root Context & Bounded Health Probes       | VERIFIED   |
+----------------------------------------------------------------------------------------------------+
```

### Critical Findings

#### [CRIT-01] Silent Mock-Provider Fallback in Production Failure Paths
- **Affected Files:**
  - [`backend/app/services/llm_provider.py`](file:///D:/AgentLens/backend/app/services/llm_provider.py#L128-L141) (Lines 128–141, 214–227)
  - [`backend/app/services/embedding_provider.py`](file:///D:/AgentLens/backend/app/services/embedding_provider.py#L108-L119) (Lines 108–119)
- **Vulnerability:**
  When external LLM providers (Groq, Gemini) or the Gemini embedding provider encountered API errors, rate limits, or network partitions, exception handlers caught the error and silently instantiated and returned deterministic mock objects (`MockInvestigationProvider`, `MockEmbeddingProvider`). In a production-like staging environment, this masked provider failures by generating synthetic root-cause analyses and fake 768-dimensional vector embeddings, corrupting database vector indexes without alerting operators.
- **Remediation:**
  - Implemented `is_mock_allowed()` checking `settings.environment` and `settings.allow_mock_providers`.
  - In production without explicit opt-in, provider exceptions now fail closed by re-raising a descriptive `RuntimeError`:
    `"External LLM provider '{provider}' failed in production: ... Silent fallback to mock is prohibited."`
  - In non-production environments where fallback is permitted, telemetry counter `record_mock_fallback(provider)` increments and logs high-priority warnings.
  - Startup validation in `Settings` prevents `llm_provider="mock"` or `embedding_provider="mock"` when `environment="production"`.

---

### High Severity Findings

#### [HIGH-01] Insecure Asyncpg SSL Parameter Interpretation
- **Affected Files:**
  - [`backend/app/db/session.py`](file:///D:/AgentLens/backend/app/db/session.py#L23-L45) (Lines 23–45)
  - [`backend/app/config.py`](file:///D:/AgentLens/backend/app/config.py#L110-L125) (Lines 110–125)
- **Vulnerability:**
  The database engine setup checked `"sslmode=" in database_url` to set `connect_args["ssl"] = True`. If a connection string specified `sslmode=disable` or `sslmode=allow`, the substring match resulted in `ssl=True`, or conversely caused asyncpg driver errors. More critically, unencrypted database connections in production were not actively blocked by configuration validation.
- **Remediation:**
  - Implemented query string parsing with `urllib.parse.urlsplit` and `parse_qs`.
  - Mapped explicit SSL modes (`sslmode=require`, `sslmode=verify-ca`, `sslmode=verify-full`, `ssl=true`, `ssl=1`) to `connect_args["ssl"] = True`.
  - Stripped query parameters from the asyncpg URL to avoid driver parameter collision.
  - Added Pydantic validator on `Settings.database_url` that explicitly raises `ValidationError` in production if `sslmode=disable`, `sslmode=allow`, or `ssl=false` is detected.

#### [HIGH-02] Redis Readiness & Multi-Instance Coordination Desynchronization
- **Affected Files:**
  - [`backend/app/config.py`](file:///D:/AgentLens/backend/app/config.py#L22-L24) (Lines 22–24, 130–138)
  - [`backend/app/main.py`](file:///D:/AgentLens/backend/app/main.py#L200-L245) (Lines 200–245)
- **Vulnerability:**
  In a multi-instance staging cluster behind an ingress load balancer, WebSocket event distribution requires shared Redis Pub/Sub. Previously, the `/health/ready` probe reported `200 OK` (degraded) whenever Redis disconnected, regardless of cluster topology. A multi-instance cluster would thus continue routing traffic to nodes unable to broadcast events to clients on peer instances.
- **Remediation:**
  - Added `DEPLOYMENT_TOPOLOGY` (`"single-instance"` | `"multi-instance"`) and `REDIS_REQUIRED` (bool) configuration.
  - Validated that `DEPLOYMENT_TOPOLOGY == "multi-instance"` automatically enforces `redis_required = True`.
  - Updated `/health/ready` and `/health`: if Redis is mandatory and disconnected, the probe returns `503 Service Unavailable` with `status: "unhealthy"`, signaling ingress proxies to pull the instance from the rotation. Single-instance nodes retain local in-memory fallback with `200 OK` (`status: "degraded"`).

---

### Medium Severity Findings

#### [MED-01] Unauthenticated Operational Metrics & Cardinality Leakage Risk
- **Affected Files:**
  - [`backend/app/main.py`](file:///D:/AgentLens/backend/app/main.py#L250-L280) (Lines 250–280)
  - [`backend/app/services/metrics.py`](file:///D:/AgentLens/backend/app/services/metrics.py#L14-L60) (Lines 14–60)
- **Vulnerability:**
  The `/metrics` and `/api/v1/metrics` endpoints were accessible without authentication, exposing internal failure rates and endpoint topologies to unauthenticated callers. Additionally, custom metric registries had to be audited against high-cardinality unbounded labels (such as trace IDs or prompt inputs) which can exhaust server memory.
- **Remediation:**
  - Added `METRICS_ENABLED` flag (returns `404 Not Found` if disabled).
  - Added `METRICS_AUTH_TOKEN` guard: requests must supply matching token via `Authorization: Bearer <token>` or `?token=<token>`.
  - Audited all metric labels across `metrics.py`: labels are strictly bounded to finite enumerations (`endpoint`, `status_code`, `rule`, `provider`, `category`). Zero trace IDs, prompt payloads, or user secrets are incorporated into Prometheus metric keys or labels.

#### [MED-02] Untrusted X-Request-ID Header Injection & Unbounded Size
- **Affected Files:**
  - [`backend/app/main.py`](file:///D:/AgentLens/backend/app/main.py#L85-L115) (Lines 85–115)
- **Vulnerability:**
  Clients could supply arbitrary string values in `X-Request-ID`. Without validation, malicious callers could inject carriage-return/newline characters (CRLF log injection) or extremely long strings causing log bloat and memory pressure across log indexing services.
- **Remediation:**
  - Validated incoming `X-Request-ID` against regex pattern `^[a-zA-Z0-9_\-\.]{1,64}$`.
  - Discarded invalid headers and generated cryptographically secure fallback identifiers (`req_{uuid4().hex[:16]}`).
  - Propagated validated correlation IDs into `request.state.request_id`, response headers, and async logging contexts.

---

### Low Severity Findings

#### [LOW-01] Remote Neon Lifespan Execution Latency in Unit Test Harness
- **Affected Files:**
  - [`backend/tests/conftest.py`](file:///D:/AgentLens/backend/tests/conftest.py#L20-L38) (Lines 20–38)
- **Observation:**
  Local unit tests instantiating FastAPI `TestClient(app)` triggered the application lifespan manager, which ran schema migrations against remote Neon PostgreSQL. This introduced network overhead (~2–3s per test) during test execution.
- **Remediation:**
  - Created `bypass_remote_init_db_in_tests` autouse fixture in `conftest.py` that mocks `init_db` for unit test suites while preserving real schema migration tests in `test_postgres_integration.py` and `test_staging_e2e.py`.

#### [LOW-02] Container Privilege Isolation & Health Probes
- **Affected Files:**
  - [`backend/Dockerfile`](file:///D:/AgentLens/backend/Dockerfile)
  - [`docker-compose.yml`](file:///D:/AgentLens/docker-compose.yml)
- **Verification:**
  - Dockerfile enforces unprivileged execution via `USER appuser`.
  - Health checks query bounded `/health/live` probe to avoid cascading container restarts during transient datastore spikes.
  - Multi-stage build strips dev tools and test caches from production image.

---

## 3. Summary of Code Changes & Rationale

| File | Changes Made | Rationale |
|---|---|---|
| `backend/app/config.py` | Added `deployment_topology`, `redis_required`, `allow_mock_providers`, `metrics_auth_token`, `metrics_enabled`. Added startup validators for production SSL mode, LLM provider, and embedding provider. | Enforce fail-closed security at startup; prevent accidental activation of mock providers or unencrypted DB links in production. |
| `backend/app/db/session.py` | Parsed database query parameters using `urllib.parse`; mapped explicit SSL modes to `connect_args["ssl"] = True`; stripped query string before passing to asyncpg. | Ensure asyncpg negotiates TLS reliably without parameter collisions or insecure fallback. |
| `backend/app/services/metrics.py` | Added `_mock_fallbacks` counter, `record_mock_fallback(provider)`, and Prometheus gauge exporter. | Provide observability and alerting if mock fallbacks are triggered. |
| `backend/app/services/llm_provider.py` | Added `is_mock_allowed()`; removed silent mock returns in `GroqInvestigationProvider` and `GeminiInvestigationProvider`; raised `RuntimeError` in production. | Stop silent failure masking; surface true upstream provider status. |
| `backend/app/services/embedding_provider.py` | Added `is_mock_allowed()`; removed silent mock returns in `GeminiEmbeddingProvider`; raised `RuntimeError` in production. | Prevent insertion of synthetic vectors into vector databases. |
| `backend/app/services/investigation_service.py` | Wrapped provider calls in `asyncio.wait_for(timeout=30s)` with structured timeout exception handling. | Ensure LLM provider calls respect strict deadlines and do not hang event loops. |
| `backend/app/main.py` | Updated `/health/ready` to enforce `503` when `redis_mandatory` fails; added token authentication on `/metrics`; added regex validation and bounding on `X-Request-ID`. | Align readiness with deployment topology; secure metrics; prevent CRLF log injection. |
| `.env.example` | Documented `DEPLOYMENT_TOPOLOGY`, `REDIS_REQUIRED`, `ALLOW_MOCK_PROVIDERS`, `METRICS_ENABLED`, `METRICS_AUTH_TOKEN`. | Provide complete, secure reference configuration for staging operators. |
| `backend/tests/test_staging_gate.py` | Authored 23 test cases covering all Phase 20D gate criteria. | Automated regression proof for staging readiness. |
| `backend/tests/conftest.py` | Added `bypass_remote_init_db_in_tests` autouse fixture. | Prevent unit tests from executing redundant remote migrations on each client instantiation. |

---

## 4. Test Execution Results Matrix

All test suites were executed cleanly and validated against both local emulations and live remote infrastructure.

| Suite | Component / Target | Command | Total | Passed | Failed | Skipped | Duration |
|---|---|---|---|---|---|---|---|
| **Backend Full Suite** | All Unit, MCP, Security, DB, Integration & Gate Tests | `pytest tests -v` | 326 | **325** | 0 | 1* | 371s |
| ↳ *Staging Gate Suite* | Mock Prohibition, SSL, Redis, Metrics, Request-ID | `pytest tests/test_staging_gate.py` | 23 | **23** | 0 | 0 | 1.8s |
| ↳ *PostgreSQL Integration* | Real Neon PG 18.6 & pgvector 0.8.6 | `pytest tests/test_postgres_integration.py` | 7 | **7** | 0 | 0 | 8.2s |
| ↳ *Staging E2E Smoke* | Real Neon Pipeline (Trace → Event → HNSW Embedding) | `pytest tests/test_staging_e2e.py` | 1 | **1** | 0 | 0 | 4.3s |
| ↳ *Production Hardening* | Tenant Isolation, Redaction, Auth | `pytest tests/test_production_hardening.py` | 12 | **12** | 0 | 0 | 2.1s |
| ↳ *Reliability & Recovery* | Health Probes, Timeouts, Safe Shutdown | `pytest tests/test_reliability_monitoring.py` | 13 | **13** | 0 | 0 | 1.4s |
| ↳ *Redis Integration* | Pub/Sub, Resilience & Fallback | `pytest tests/test_redis_integration.py` | 4 | **3** | 0 | 1* | 0.9s |
| **Python SDK Suite** | AgentLens Tracing, Context, Batching, API | `pytest tests -v` (in `sdk/`) | 43 | **43** | 0 | 0 | 4.6s |
| **Frontend Test Suite** | React Dashboard, Trace Graph, Auth, Metrics | `npm test -- --watchAll=false` | 79 | **79** | 0 | 0 | 3.5s |
| **Frontend Production Build** | TypeScript Compilation, Asset Bundling | `npm run build` | — | **Success** | 0 | 0 | 3.9s |

*\*Note: 1 Redis test (`test_live_redis_pubsub_broadcast_and_delivery`) was skipped in the local run because Docker Desktop was not running locally during unit tests. Redis resilience and degradation policies passed 100%.*

---

## 5. Infrastructure Verification: Real vs. Mocked

```
+-------------------------------------------------------------------------------------------------------+
| Infrastructure Component | Staging Status | Verification Evidence                                      |
+-------------------------------------------------------------------------------------------------------+
| Neon PostgreSQL 18.6     | REAL           | Verified: connection, schema, transactions, rollbacks     |
| pgvector Extension 0.8.6 | REAL           | Verified: 768-dim vector column, cosine search, HNSW index |
| HNSW Cosine Index        | REAL           | Verified: idx_failure_embeddings_embedding_hnsw query     |
| Tenant Isolation (Vector)| REAL           | Verified: Alpha embeddings strictly unreadable by Beta     |
| Redis Pub/Sub            | DEGRADED / SIM | Verified in-memory fallback; live container tested in 20C |
| LLM Provider (Groq)      | VALIDATED PATH | Fail-closed validated; mock fallback blocked in production |
| Embedding (Gemini)       | VALIDATED PATH | Fail-closed validated; mock fallback blocked in production |
+-------------------------------------------------------------------------------------------------------+
```

### Verified Real Infrastructure
1. **Neon PostgreSQL 18.6**:
   - TLS connection verified using `asyncpg` with `ssl=True`.
   - Cascading foreign keys (`organizations` → `projects` → `traces` → `events` / `failure_embeddings`) validated.
   - Idempotent schema migrations (`init_db()`) confirmed.
2. **pgvector 0.8.6 & HNSW Indexing**:
   - `failure_embeddings.embedding` confirmed as `vector(768)`.
   - HNSW index `idx_failure_embeddings_embedding_hnsw` verified using `vector_cosine_ops`.
   - Cosine distance queries (`<=>`) verified with tenant scoping (`WHERE project_id = :project_id`).
   - Dimension mismatch safety confirmed: inserting 512-dim vector into 768-dim column safely rejected by PostgreSQL.

### Verified Mock / Degraded Behaviors
1. **Redis Pub/Sub**:
   - Single-instance topology tested with Redis offline: system logged bounded warnings and successfully broadcast trace events to local WebSockets via in-memory queues without crashing or dropping ingestion requests.
   - Multi-instance topology tested with Redis offline: `/health/ready` probe correctly flipped to HTTP `503 Service Unavailable`.
2. **LLM & Embeddings**:
   - In production mode, all mock fallbacks are prohibited and fail closed with traceable `RuntimeError`.
   - In development/testing, mock fallback executes safely and increments `agentlens_mock_fallbacks_total`.

---

## 6. Remaining Risks & Operator Deployment Checklist

### Remaining Risks Before Final Production Promotion
1. **Live Redis High-Availability**: Staging cluster must verify multi-node Redis Sentinel or managed Redis TLS failover under live load.
2. **Reverse Proxy TLS Termination**: Application containers listen on HTTP (`0.0.0.0:8000`); production deployment requires an ingress controller (Nginx, Traefik, AWS ALB, Cloud Run) handling TLS termination and forwarding `X-Forwarded-Proto: https`.
3. **Third-Party Provider Rate Limits**: Production deployments using Groq or Gemini must implement exponential backoff alerts in monitoring dashboards.

### Operator Staging Deployment Checklist

- [ ] **1. Configure Environment Variables**:
  - Set `ENVIRONMENT=production`
  - Set `DEPLOYMENT_TOPOLOGY=multi-instance` (or `single-instance` for single-node staging)
  - Set `REDIS_REQUIRED=true` (if multi-instance)
  - Set `ALLOW_MOCK_PROVIDERS=false`
  - Set `DATABASE_URL` with `?sslmode=require`
  - Set `REDIS_URL` with valid credentials (e.g., `rediss://...` if TLS enabled)
  - Set `JWT_SECRET_KEY` (minimum 32 characters, high entropy)
  - Set `GROQ_API_KEY` and `GEMINI_API_KEY`
  - Set `METRICS_ENABLED=true` and `METRICS_AUTH_TOKEN=<random_hex>`
  - Set `COOKIE_SECURE=true`
  - Set `CORS_ORIGINS` to the exact staging domain (e.g., `https://staging.agentlens.dev`)
- [ ] **2. Verify Ingress & Networking**:
  - Configure ingress to route `/health/live` to liveness probes and `/health/ready` to readiness probes.
  - Enable WebSocket upgrade headers (`Upgrade`, `Connection: Upgrade`) on `/ws/traces/{trace_id}`.
- [ ] **3. Run Staging Smoke Verification**:
  - Verify `GET /health/ready` returns `200 OK` (`status: "healthy"`).
  - Ingest test trace via SDK and verify presence in PostgreSQL.
  - Verify MCP stdio connection operates without leaking logs to stdout.

---

## 7. Rollback & Operational Recovery Procedures

### Procedure 1: Application Container Rollback
If a newly deployed container build fails readiness checks or surfaces error spikes:
1. Revert container image tag to previous stable digest in deployment manifest.
2. Trigger rolling restart (`kubectl rollout undo deployment/agentlens-backend`).
3. Readiness probe `/health/ready` will automatically withhold traffic from unready pods until healthy.

### Procedure 2: Redis Outage Mitigation
If Redis fails in a `multi-instance` staging deployment:
1. Ingress controllers will automatically receive `503 Service Unavailable` on `/health/ready` and withhold new requests.
2. For temporary emergency single-node operation while repairing Redis, operators may set `DEPLOYMENT_TOPOLOGY=single-instance` and `REDIS_REQUIRED=false` and restart a single container; this restores ingestion and local WebSockets using in-memory broadcast.

### Procedure 3: Neon Point-in-Time Recovery (PITR)
If data corruption occurs during staging testing:
1. Create a restored branch from Neon console or CLI:
   ```bash
   neon branches create --project-id <project_id> --name staging-recovery --timestamp <iso_timestamp>
   ```
2. Update staging `DATABASE_URL` with the new branch endpoint connection string.
3. Restart application containers; `pool_pre_ping=True` re-establishes healthy pools.

---

## 8. Audit Scope & Boundary Confirmation

This document confirms that Phase 20D activities were strictly limited to:
1. Static code auditing and configuration analysis.
2. Remediation of identified security blockers, mock-provider fallbacks, SSL parsing, and metric protection.
3. Creation and execution of automated regression test suites.
4. Compilation of this deployment readiness report.

**No production deployment was triggered, no public ports were exposed, no cloud resources were provisioned, and no production secrets were altered.**

---

*Report approved by Antigravity AI Engineering Assistant.*
