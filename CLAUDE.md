# AgentLens

## Project Purpose

AgentLens is an AI-powered observability and failure investigation platform for AI agents.

It continuously captures agent execution telemetry such as:
- User requests
- LLM calls and responses
- Tool calls and responses
- State changes
- Retries
- Errors
- Final responses

It reconstructs executions into traces and execution graphs and uses AI to investigate failures, identify root causes, provide evidence, explain downstream effects, and recommend fixes.

## Planned Stack

- **Backend**: Python + FastAPI
- **Database**: PostgreSQL (Neon cloud)
- **Cache/queues**: Redis (Docker)
- **AI/Agents**: LangGraph + LangChain
- **LLM providers**: Gemini and Groq
- **Frontend**: React + TypeScript
- **Styling**: Tailwind CSS
- **Graph visualization**: React Flow
- **Vector search**: pgvector (available in Neon)
- **Integration**: Python SDK + MCP
- **Infrastructure**: Docker (Redis only)
- **Testing**: pytest for Python, Vitest/React Testing Library for frontend

## Architecture

The planned architecture is:

```
Demo/External AI Agent
        ↓
AgentLens SDK / Integration
        ↓
AgentLens API
        ↓
Trace/Event Storage
        ↓
Trace Engine
        ↓
Failure Detection
        ↓
AI Root Cause Investigator
        ↓
Dashboard / MCP
```

## Core Principles

1. **AI must be central to the problem**, not an AI feature added to a traditional CRUD application.
2. **Build incrementally** and keep each milestone working.
3. **Prefer simple architecture** before introducing complexity.
4. **Do not over-engineer**.
5. Keep backend business logic **independent from the frontend**.
6. Keep the **SDK lightweight**.
7. Keep **LLM providers replaceable**.
8. **Never hardcode API keys or secrets**.
9. **Never expose secrets** in traces, logs, embeddings, or API responses.
10. **Validate all external input**.
11. **Add tests** for important functionality.
12. **Preserve backwards compatibility** when extending existing components.
13. **Do not rewrite working components** without a clear reason.
14. **Do not add unnecessary dependencies**.
15. **Explain significant architectural changes** before implementing them.

## Development Strategy

Build in this order:

**Phase 1**: Project foundation and development environment.

**Phase 2**: AgentLens Python SDK.

**Phase 3**: FastAPI event ingestion.

**Phase 4**: PostgreSQL event storage.

**Phase 5**: Demo AI agent.

**Phase 6**: End-to-end SDK → API → PostgreSQL tracing.

**Phase 7**: Trace reconstruction engine.

**Phase 8**: Execution graph.

**Phase 9**: React dashboard.

**Phase 10**: Real-time monitoring.

**Phase 11**: Deterministic failure and anomaly detection.

**Phase 12**: AI root-cause investigation.

**Phase 13**: Replay and run comparison.

**Phase 14**: Historical failure search with pgvector.

**Phase 15**: MCP integration.

**Phase 16**: Security hardening and final testing.

## Current Status

Phases 1 through 12 are complete and verified:
- **Phase 1-6**: Foundation, AgentLens SDK, Event ingestion, PostgreSQL (Neon) storage, Demo AI agent, and End-to-end tracing verified.
- **Phase 7**: Trace Reconstruction Engine (`ReconstructedTrace`, ordered event tree, execution metrics, `GET /api/v1/traces/{trace_id}`).
- **Phase 8**: Execution Graph (`ExecutionGraph`, deterministic nodes and edges, `GET /api/v1/traces/{trace_id}/graph`).
- **Phase 9**: React Observability Dashboard (`GET /api/v1/traces` summary listing, React Flow execution graph with waterfall layout, event details panel, developer-tool UI, 158 backend/sdk/demo tests + 23 frontend tests passing).
- **Phase 10**: Real-Time Agent Execution Monitoring (Redis Pub/Sub event fan-out, WebSocket endpoint `WS /api/v1/ws/traces/{trace_id}` with token auth, post-persistence delivery with graceful degradation, React frontend live updates with incremental graph updates and preserved selection, `● Live` status indicator, 168 backend/sdk/demo tests + 29 frontend tests passing, verified with live Redis container, Neon PostgreSQL, and browser demo).
- **Phase 11**: Deterministic Failure & Anomaly Detection (`FailureDetectionService`, 8 deterministic detection rules: explicit errors, unresolved retries, repeated tool calls, missing tool responses, missing LLM responses, invalid lifecycle, execution loops, high retry counts; configurable thresholds via `DetectionConfig`; `GET /api/v1/traces/{trace_id}/findings` endpoint; 194 backend/sdk/demo tests + 29 frontend tests passing).
- **Phase 12**: AI Root-Cause Investigation (`AIInvestigationService`, `InvestigationLLMProvider` abstraction supporting Groq, Gemini, and Mock providers; compact sanitized context building; strict hallucination validation against ground-truth trace event and finding IDs; discrimination of earliest root cause from downstream symptoms; `GET /api/v1/traces/{trace_id}/investigation` endpoint; 217 backend/sdk/demo tests + 29 frontend tests passing).
- **Phase 13**: Investigation Dashboard (Dedicated investigation panel with root-cause visual focus, confidence badge, interactive evidence inspection with cross-linking to execution graph, failure timeline, and actionable remediation recommendations).
- **Phase 14**: Replay / Run Comparison (`TraceComparisonService`, side-by-side run comparison, structural and topological alignment, duration/status diffs, findings diffs, unified timeline, `GET /api/v1/traces/compare` endpoint, 49 frontend tests passing).
- **Phase 15**: Historical Failure Search with pgvector (`FailureEmbeddingModel` in PostgreSQL/Neon, 768-dim embeddings via `EmbeddingProvider` abstraction supporting Gemini `models/text-embedding-004` and deterministic `MockEmbeddingProvider`, credential redaction on vector synthesis, `POST /api/v1/traces/{trace_id}/index` idempotent indexing, `GET /api/v1/failures/search` pgvector cosine similarity search, `HistoricalSearchView` React component with natural language queries, similarity badges, and trace navigation, 167 backend tests and 59 frontend tests passing).
- **Phase 16**: Model Context Protocol (MCP) (`app.mcp.server`, standard stdio transport using official `mcp>=2.0.0` SDK, 7 read-only observability tools: `get_trace`, `get_execution_graph`, `get_trace_findings`, `investigate_trace`, `compare_traces`, `search_historical_failures`, `list_recent_traces`; read-only resource `agentlens://traces/{trace_id}`; zero logic duplication delegating directly to existing core services; recursive secret redaction; 192 backend tests, 43 SDK tests, and 59 frontend tests passing).
- **Phase 17**: Security Hardening (Production API key validation, payload limits [max 500 events, 2MB body], identifier length constraints [max 256 chars], recursive secret redaction for env vars, connection strings, and tokens, CORS origin restrictions, OWASP security headers, prompt-injection isolation with XML delimiter guards; 210 backend tests, 43 SDK tests, and 59 frontend tests passing).
- **Phase 18**: Final Testing & Validation (End-to-end multi-tier validation across live Neon PostgreSQL, pgvector cosine search, Redis Pub/Sub, Demo customer-support agent, controlled failure scenarios Cases A through F, trace reconstruction, execution graph, React dashboard flows, 7-tool MCP server, and Python SDK. Verified all 210 backend tests, 43 SDK tests, 59 frontend tests, 34 demo tests, and production build with zero blocking defects).

## Coding Rules

### Python Backend

- Use **Python type hints** everywhere.
- Use **Pydantic models** for API schemas and validation.
- Keep **FastAPI routes thin** — they should validate input and delegate to services.
- Put **business logic in services**, not routes.
- Keep **database access separated** from API routes — use repository pattern or data access layer.
- Use **async code** where appropriate (database calls, HTTP requests, I/O operations).
- Use **environment variables** for configuration and secrets.
- Keep **configuration centralized** (e.g., `config.py` or similar).
- Write **readable production-quality code**.
- Avoid **unnecessary abstractions**.
- Add **tests alongside important features**.

### Frontend

- Use **TypeScript** with strict mode enabled.
- Use **functional components** with hooks.
- Keep **components focused** — one responsibility per component.
- Use **Tailwind CSS** for styling — avoid custom CSS unless necessary.
- Keep **API calls in separate service files**, not directly in components.
- Use **React Flow** for graph visualizations.
- Handle **loading and error states** explicitly.
- Make the UI **accessible** (ARIA labels, keyboard navigation, semantic HTML).

### General

- **No hardcoded secrets** — use `.env` files (gitignored) and environment variables.
- **Sanitize sensitive data** before storing or displaying it.
- **Validate all external input** at API boundaries.
- **Write tests** for critical paths.
- **Document non-obvious decisions** in code comments.
- Keep **dependencies minimal** and well-justified.

## Claude Code Behavior

Before implementing a major feature:

1. **Inspect the existing code** to understand what's already there.
2. **Understand the current architecture** and patterns.
3. **Explain the proposed approach** clearly.
4. **Identify files that will change**.
5. **Implement the smallest reasonable solution** that solves the problem.
6. **Run relevant tests**.
7. **Fix failures** before marking the work complete.
8. **Summarize what changed** concisely.

### Important Rules

- **Do not implement future phases prematurely**. Build only what is needed for the current phase.
- **Do not build the entire project in one step**. Work incrementally.
- When requirements are **ambiguous, ask for clarification** rather than inventing major architectural decisions.
- **Do not refactor working code** unless explicitly asked or necessary for the current task.
- **Do not add features** that weren't requested.
- **Verify changes work** before presenting them as complete.

## Directory Structure

```
AgentLens/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── models/       # Pydantic models and database schemas
│   │   ├── services/     # Business logic
│   │   ├── db/           # Database setup and repositories
│   │   └── config.py     # Configuration
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/     # API client
│   │   └── types/        # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── sdk/
│   ├── agentlens/        # Python SDK package
│   ├── tests/
│   └── setup.py
├── demo/                 # Demo AI agent
├── docker-compose.yml
├── .env.example
└── README.md
```

This structure will evolve as the project grows.

## Testing Strategy

- **Unit tests** for business logic and utilities.
- **Integration tests** for API endpoints with database.
- **End-to-end tests** for critical user flows (SDK → API → storage → dashboard).
- **Tests should be fast** and runnable locally without external dependencies when possible.
- Use **fixtures and factories** to create test data.
- **Mock external services** (LLM providers) in tests.

## Security Considerations

- **Never log or store** API keys, tokens, or passwords in plain text.
- **Redact sensitive information** from traces before storing them.
- Use **parameterized queries** or ORM to prevent SQL injection.
- **Validate and sanitize** all user input.
- Use **HTTPS** in production.
- Implement **rate limiting** on API endpoints.
- Use **environment-specific configurations** (dev, staging, prod).
- Store secrets in **environment variables** or a secret manager, never in code or git.

## Development Workflow

1. **Create a feature branch** for each phase or feature.
2. **Implement the feature** following the coding rules.
3. **Write tests** for the new functionality.
4. **Run tests** and ensure they pass.
5. **Test manually** if applicable (e.g., API endpoints, UI changes).
6. **Document significant changes** in code or README.
7. **Commit with clear messages** describing what changed and why.

## Dependencies Management

- **Pin versions** in `requirements.txt` and `package.json` for reproducibility.
- **Review dependencies** before adding them — prefer well-maintained, popular libraries.
- **Keep dependencies updated** to get security patches.
- **Audit dependencies** for known vulnerabilities periodically.

## Environment Variables

The project uses environment variables for configuration. Create a `.env` file (gitignored) based on `.env.example`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/agentlens

# Redis
REDIS_URL=redis://localhost:6379

# LLM Providers
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

# API
API_HOST=0.0.0.0
API_PORT=8000
```

**Never commit `.env` to git.**

## Running the Project

(To be filled in as components are built)

- **Backend**: `cd backend && uvicorn app.main:app --reload`
- **Frontend**: `cd frontend && npm run dev`
- **Full stack**: `docker-compose up`

## Phase 16: Model Context Protocol (MCP)

AgentLens exposes its observability and failure investigation capabilities through an official MCP server using standard stdio transport.

### Running the MCP Server
```bash
python -m app.mcp.server
```
*(Run from the `backend/` directory or with `PYTHONPATH=backend`)*

### Available MCP Tools
All tools are strictly **read-only** and scrub sensitive tokens, credentials, and secrets:
1. `get_trace(trace_id: str)`: Reconstructed trace summary, event counts, metadata, and ordered event sequence.
2. `get_execution_graph(trace_id: str)`: Execution graph nodes and directed edges (lifecycle, LLM, tool calls, errors).
3. `get_trace_findings(trace_id: str)`: Phase 11 deterministic failure and anomaly findings.
4. `investigate_trace(trace_id: str)`: Phase 12 AI root-cause analysis, earliest failure, evidence, and recommended actions.
5. `compare_traces(trace_a: str, trace_b: str)`: Phase 14 side-by-side run comparison, structural diffs, and aligned timeline.
6. `search_historical_failures(query: str, limit: int, severity: str, rule: str, project: str)`: Phase 15 pgvector semantic search over historical failures.
7. `list_recent_traces(project: str, limit: int, offset: int)`: Lightweight trace listing and pagination.

### Connecting an MCP Client (e.g. Claude Desktop / Claude Code)
```json
{
  "mcpServers": {
    "agentlens": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/AgentLens/backend",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://...",
        "AGENTLENS_API_KEY": "test_api_key_123"
      }
    }
  }
}
```

## Phase 17: Security Hardening

AgentLens is security-hardened for its current architecture across API ingestion, WebSocket monitoring, MCP tools, database persistence, and AI investigation boundaries:

### 1. Authentication & Timing-Safe Verification
- Endpoints enforce bearer token authentication (`Authorization: Bearer <key>`).
- API keys are verified using constant-time comparison (`secrets.compare_digest`) to prevent timing attacks.
- Configurable via `AGENTLENS_API_KEYS` environment variable (comma-separated).
- WebSocket endpoints authenticate via query token (`?token=`) using constant-time verification.

### 2. Input Validation & Request Bounding
- Event ingestion enforces maximum batch sizes (`MAX_EVENT_BATCH_SIZE = 1000`).
- String identifier fields (`trace_id`, `event_id`, `parent_event_id`, `name`) enforce strict length bounds (`<= 256` chars).
- WebSocket trace IDs must match alphanumeric/safe regex `^[a-zA-Z0-9_\-\.]{1,128}$` to prevent channel injection.
- Search queries are capped at 1000 characters and limit parameters bounded (1-50 for search, 1-500 for trace listings).

### 3. Centralized Sensitive Data Redaction
- Recursive redaction utility in `backend/app/services/redaction.py` automatically scrubs:
  - Secrets, API keys (`sk-...`), Bearer tokens, passwords, and client secrets.
  - Database connection strings (`postgresql://`, `postgres://`, `redis://`, etc.).
- Normal operational metrics (e.g., `prompt_tokens`, `completion_tokens`, `total_tokens`, `token_count`, `cache_key`) are preserved.
- Applied across telemetry ingestion, MCP responses, search synthesis, and error reporting.

### 4. AI & Prompt Injection Security Boundaries
- All external telemetry ingested into AI root-cause investigation is treated as untrusted data.
- Telemetry context is wrapped in `<untrusted_telemetry_context>` delimiters.
- System prompt instructs LLMs to never interpret embedded user prompts, tool outputs, or error messages as system directives or prompt overrides.

### 5. Error Masking & Exception Safety
- Internal database connection errors and stack traces are masked from HTTP responses.
- Responses return generic 500 error messages while logging sanitized details internally.
- MCP `_format_error` automatically sanitizes detail payloads.

### 6. Security Headers & Configurable CORS
- Standard defense headers added to all API responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `X-XSS-Protection: 1; mode=block`
- Configurable CORS via `CORS_ORIGINS` environment variable (disallowing wildcard `*` when credentials are used).

### 7. Known Architectural Limitations
- **Frontend SPA API Key**: `VITE_AGENTLENS_API_KEY` in the React frontend is compiled into client-side JavaScript bundles and is publicly inspectable in user browsers. In production deployments, client dashboards should either authenticate through user session cookies via a backend reverse proxy or operate within a trusted internal network.

## Notes for Future Development

- **Phase dependencies**: Each phase may depend on previous phases. Do not skip ahead.
- **Incremental testing**: Test each phase before moving to the next.
- **Architecture evolution**: The architecture may evolve as requirements become clearer. Document major changes here.
- **Performance considerations**: Address performance optimizations after core functionality works.
- **Scalability**: Design with scalability in mind, but don't over-optimize prematurely.
