# AgentLens

AI-powered observability and failure investigation platform for AI agents.

## Overview

AgentLens continuously captures agent execution telemetry (user requests, LLM calls, tool calls, state changes, errors) and reconstructs them into traces and execution graphs. It uses AI to investigate failures, identify root causes, and recommend fixes.

## Architecture

```
Demo/External AI Agent
        ↓
AgentLens SDK
        ↓
AgentLens API (FastAPI)
        ↓
PostgreSQL + Redis
        ↓
Trace Engine
        ↓
AI Root Cause Investigator
        ↓
Dashboard (React) / MCP
```

## Prerequisites

- **Python** 3.11+
- **Node.js** 18+
- **Docker** and **Docker Compose** (for Redis)
- **Git**
- **Neon PostgreSQL** account (free tier available at https://neon.tech)

## Project Structure

```
AgentLens/
├── backend/          # FastAPI backend
├── frontend/         # React + TypeScript dashboard
├── sdk/              # Python SDK for agent integration
├── demo/             # Demo AI agent
├── docker-compose.yml
├── .env.example
└── CLAUDE.md        # Development instructions
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd AgentLens
cp .env.example .env
```

### 2. Set Up Neon PostgreSQL

1. Create a free account at https://neon.tech
2. Create a new project
3. Copy your connection string from the Neon dashboard
4. Edit `.env` and set `DATABASE_URL` to your Neon connection string
5. Add your API keys for Gemini and Groq

### 3. Start Redis

```bash
docker-compose up -d redis
```

### 4. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend will run at: http://localhost:8000

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at: http://localhost:5173

### 6. SDK Development

```bash
cd sdk
pip install -e .
```

## Development

### Backend Development

The backend uses:
- **FastAPI** for API routes
- **Pydantic** for data validation
- **asyncpg** for PostgreSQL (connects to Neon)
- **Redis** for caching/queues

Run tests:
```bash
cd backend
pytest
```

### Frontend Development

The frontend uses:
- **React** with TypeScript
- **Vite** for fast builds
- **Tailwind CSS** for styling
- **React Flow** for graph visualization

Run tests:
```bash
cd frontend
npm test
```

### SDK Development

The SDK is a lightweight Python package for integrating AgentLens into AI agents.

Run tests:
```bash
cd sdk
pytest
```

## Infrastructure

- **Neon PostgreSQL**: Cloud PostgreSQL database with pgvector support
- **Redis** (Docker): Cache and queue service (port 6379)
- **Backend**: FastAPI backend (port 8000) - *to be configured*
- **Frontend**: React frontend (port 5173) - *to be configured*

## Environment Variables

See `.env.example` for all required configuration options.

**Important**: Never commit your `.env` file. It contains secrets.

## Development Phases

This project follows an incremental development strategy:

1. ✅ **Phase 1**: Project foundation
2. ✅ **Phase 2**: AgentLens Python SDK
3. ✅ **Phase 3**: FastAPI event ingestion
4. ✅ **Phase 4**: PostgreSQL event storage
5. ✅ **Phase 5**: Demo AI agent
6. ✅ **Phase 6**: End-to-end tracing
7. ✅ **Phase 7**: Trace reconstruction engine
8. ✅ **Phase 8**: Execution graph
9. ✅ **Phase 9**: React dashboard
10. ✅ **Phase 10**: Real-time monitoring
11. ✅ **Phase 11**: Failure detection
12. ✅ **Phase 12**: AI root-cause investigation
13. ✅ **Phase 13**: Investigation dashboard
14. ✅ **Phase 14**: Replay and comparison
15. ✅ **Phase 15**: Historical failure search (pgvector)
16. ✅ **Phase 16**: Model Context Protocol (MCP) server
17. ✅ **Phase 17**: Security hardening

See `CLAUDE.md` for detailed architectural guidelines.

## Security

AgentLens is security-hardened for its current architecture:
- **Authentication**: Constant-time verification (`secrets.compare_digest`) across configured API keys (`AGENTLENS_API_KEYS`).
- **Input Validation**: Strict bounds on batch sizes (max 1000), search queries (max 1000 chars), trace IDs, and pagination limits.
- **Data Redaction**: Centralized recursive redaction of credentials, bearer tokens, API keys, and connection strings while preserving telemetry metrics.
- **AI Boundaries**: Telemetry wrapped in untrusted data delimiters with prompt injection guardrails.
- **MCP Guarantees**: Strictly read-only tools; no arbitrary SQL, filesystem, or shell execution.
- **Security Headers**: Standard headers attached (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection`).
- **Error Safety**: Database exceptions and stack traces are masked from external API responses.
- **Architectural Limitation**: The React dashboard uses `VITE_AGENTLENS_API_KEY` in browser JavaScript; for production environments, use an authenticated reverse proxy or internal network isolation.

## License

MIT License
