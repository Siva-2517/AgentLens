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
- **Database**: PostgreSQL
- **Cache/queues**: Redis
- **AI/Agents**: LangGraph + LangChain
- **LLM providers**: Gemini and Groq
- **Frontend**: React + TypeScript
- **Styling**: Tailwind CSS
- **Graph visualization**: React Flow
- **Vector search**: pgvector
- **Integration**: Python SDK + MCP
- **Infrastructure**: Docker
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

The project has just started.

**Do not assume that components are already implemented.**

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

## Notes for Future Development

- **Phase dependencies**: Each phase may depend on previous phases. Do not skip ahead.
- **Incremental testing**: Test each phase before moving to the next.
- **Architecture evolution**: The architecture may evolve as requirements become clearer. Document major changes here.
- **Performance considerations**: Address performance optimizations after core functionality works.
- **Scalability**: Design with scalability in mind, but don't over-optimize prematurely.
