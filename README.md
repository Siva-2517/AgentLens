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
- **Docker** and **Docker Compose**
- **Git**

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

Edit `.env` and add your API keys for Gemini and Groq.

### 2. Start Infrastructure (PostgreSQL + Redis)

```bash
docker-compose up -d postgres redis
```

### 3. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend will run at: http://localhost:8000

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at: http://localhost:5173

### 5. SDK Development

```bash
cd sdk
pip install -e .
```

## Development

### Backend Development

The backend uses:
- **FastAPI** for API routes
- **Pydantic** for data validation
- **asyncpg** for PostgreSQL
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

## Docker Compose Services

- **postgres**: PostgreSQL database (port 5432)
- **redis**: Redis cache (port 6379)
- **backend**: FastAPI backend (port 8000) - *to be configured*
- **frontend**: React frontend (port 5173) - *to be configured*

## Environment Variables

See `.env.example` for all required configuration options.

**Important**: Never commit your `.env` file. It contains secrets.

## Development Phases

This project follows a 16-phase incremental development strategy:

1. ✅ **Phase 1**: Project foundation
2. **Phase 2**: AgentLens Python SDK
3. **Phase 3**: FastAPI event ingestion
4. **Phase 4**: PostgreSQL event storage
5. **Phase 5**: Demo AI agent
6. **Phase 6**: End-to-end tracing
7. **Phase 7**: Trace reconstruction engine
8. **Phase 8**: Execution graph
9. **Phase 9**: React dashboard
10. **Phase 10**: Real-time monitoring
11. **Phase 11**: Failure detection
12. **Phase 12**: AI root-cause investigation
13. **Phase 13**: Replay and comparison
14. **Phase 14**: Historical failure search
15. **Phase 15**: MCP integration
16. **Phase 16**: Security hardening

See `CLAUDE.md` for detailed development guidelines.

## Contributing

Read `CLAUDE.md` for:
- Coding standards
- Architecture principles
- Development workflow
- Testing strategy

## Security

- Never commit API keys or secrets
- Always use environment variables
- Sensitive data is redacted from traces
- Input validation on all API endpoints

## License

*To be determined*
