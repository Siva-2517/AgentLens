# 🔍 AgentLens — AI-Powered Observability & Root-Cause Investigation Platform for AI Agents

AgentLens is a production-grade, full-stack observability, telemetry reconstruction, and AI-assisted root-cause investigation platform for autonomous AI agents. It continuously captures agent decision streams, reconstructs execution graphs, detects anomalies deterministically, diagnoses failures with AI, supports side-by-side run comparisons, enables historical semantic failure search with `pgvector`, and exposes read-only analytical tools through the Model Context Protocol (MCP).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)
![React](https://img.shields.io/badge/React-18%2B-cyan.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)
![PostgreSQL](https://img.shields.io/badge/Neon%20PostgreSQL-pgvector-00e699.svg)
![Redis](https://img.shields.io/badge/Redis-7%20Alpine-red.svg)
![Groq](https://img.shields.io/badge/Groq-Llama%203.3%2070B-orange.svg)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-blue.svg)
![MCP](https://img.shields.io/badge/MCP-2.0+-purple.svg)

---

## 🚀 Live Demo & Links

- 🌐 **Repository**: [GitHub — Siva-2517/AgentLens](https://github.com/Siva-2517/AgentLens)
- 🖥️ **Interactive Dashboard**: `http://localhost:5173` (React + Vite)
- 🔗 **Backend API & Swagger Docs**: `http://localhost:8000/docs` (FastAPI)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [AgentLens Pipeline & Architecture](#-agentlens-pipeline--architecture)
- [Database Schema & Entity Relationships](#-database-schema--entity-relationships)
- [Technology Stack](#-technology-stack)
- [Data Security & Validation](#-data-security--validation)
- [Installation & Quick Start](#-installation--quick-start)
- [Environment Variables](#-environment-variables)
- [API Endpoints Specification](#-api-endpoints-specification)
- [Model Context Protocol (MCP)](#-model-context-protocol-mcp)
- [Project Structure](#-project-structure)
- [Verification & Automated Test Suite](#-verification--automated-test-suite)
- [License & Author](#-license--author)

---

## 🎯 Overview

AI agents increasingly execute complex multi-step reasoning loops involving multiple LLM calls, internal tool executions, database operations, and external API requests. When an agent fails, traditional application performance monitoring (APM) tools only capture HTTP status codes and terminal exceptions, failing to explain **why** an agent took an erroneous path or where the earliest incorrect decision originated.

### The Problem We Solve
- **Silent Tool Failures**: Tools returning empty arrays, permission errors, or timeouts that cause agents to hallucinate downstream.
- **Infinite Decision Loops**: Agents getting stuck repeating identical tool calls with circular arguments.
- **Lost Causal Context**: A single invalid tool call at Step 2 causing a cascade of failures 10 steps later.
- **Tedious Post-Mortems**: Engineers spending hours manually sifting through raw JSON logs to trace decision trees.

### Our Solution
AgentLens provides continuous, automated, multi-tiered observability:
1. **Lightweight Telemetry SDK**: Non-blocking asynchronous client captures `AGENT_START`, `LLM_CALL`, `TOOL_CALL`, `STATE_CHANGE`, and `ERROR` events without latency overhead.
2. **Deterministic Tree Reconstruction**: Rebuilds parent-child execution hierarchies, measuring latency, token consumption, and tree depths.
3. **Execution Graph Engine**: Computes directed acyclic execution graphs with waterfall topological layouts.
4. **Deterministic Anomaly Detector**: 8 rules flag infinite loops, missing tool completions, retry exhaustion, and invalid lifecycles.
5. **AI Root-Cause Investigator**: Dual-provider AI reasoning engine (Groq Llama 3.3 70B & Gemini 2.5 Flash) isolates the earliest root cause, gathers supporting evidence, and provides actionable engineering remedies.
6. **Vector Failure Search**: Uses PostgreSQL `pgvector` to index failure embeddings and discover similar historical incidents via natural language semantic queries.
7. **Model Context Protocol (MCP)**: Exposes 7 read-only debugging and investigation tools directly to AI assistants like Claude Desktop and Cursor.

---

## ✨ Key Features

### 📊 Real-Time Execution Monitoring
* **Redis Pub/Sub Fan-out**: Real-time event streaming to connected WebSocket clients (`/api/v1/ws/traces/{trace_id}`).
* **Live Graph Animation**: New execution steps animate onto the React Flow canvas in real time without refreshing the page.
* **Graceful Degradation**: If Redis is temporarily unreachable, event ingestion continues uninterrupted with direct PostgreSQL persistence.

### 🌳 Deterministic Failure & Anomaly Detection
* **Explicit Error Capture**: Detects runtime exceptions and tool rejections.
* **Missing Tool & LLM Responses**: Flags initiated calls that never received completion telemetry.
* **Unresolved Retries**: Identifies retry loops that never successfully completed.
* **Execution Loops**: Flags recursive tool calls with identical parameters exceeding configurable thresholds.
* **Invalid Lifecycles**: Identifies runs missing initial start markers or ungracefully terminated.

### 🤖 AI Root-Cause Investigation
* **Earliest Fault Discrimination**: Isolates the initial faulty step from downstream cascade symptoms.
* **Hallucination Prevention**: Strict validation ensures the AI only cites verified, persisted event IDs as evidence.
* **Actionable Remediation**: Produces tailored engineering fix recommendations (prompt improvements, tool schema fixes, timeout adjustments).
* **Dual-Provider Fallback**: Automatically falls back between Groq, Gemini, and deterministic mock providers for high availability.

### ⚖️ Run Comparison & Replay
* **Side-by-Side Analysis**: Compare two execution traces side-by-side to understand divergence.
* **Structural Diffing**: Aligns topological steps, highlighting duration discrepancies and finding mismatches.
* **Zero Host Re-execution**: Compares historical stored telemetry safely without invoking production agents or external APIs.

### 🧠 Semantic Historical Search (`pgvector`)
* **Vector Embeddings**: Synthesizes structured failure summaries into 768-dimensional embeddings using Gemini / Vector models.
* **Cosine Similarity**: Surfaces past similar failures across all indexed traces using native PostgreSQL `pgvector` operators.
* **Similarity Badging**: Transparently displays mathematical similarity percentages rather than misleading confidence estimates.

### 🔌 Model Context Protocol (MCP) Server
* **7 Read-Only Tools**: Allows Claude Desktop or Cursor to query traces, inspect execution graphs, run investigations, compare runs, and search historical failures over stdio.
* **Zero Write Tools**: Strictly read-only surface with zero autonomous remediation or code modification capabilities.

---

## 🏗️ AgentLens Pipeline & Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                             TELEMETRY LAYER                                │
│   Demo AI Agent / Website / LangGraph / LangChain / Autonomous Agent       │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │ AgentLens Python SDK / REST API
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       FASTAPI INGESTION ENGINE (:8000)                     │
│  ┌───────────────────────┐                  ┌───────────────────────────┐  │
│  │   Auth & Validation   │                  │  Recursive Redaction      │  │
│  │ (Bearer Keys, Limits) │                  │ (API Keys, Passwords, URI)│  │
│  └──────────┬────────────┘                  └─────────────┬─────────────┘  │
└─────────────┼─────────────────────────────────────────────┼────────────────┘
              │                                             │
              ▼                                             ▼
┌───────────────────────────────────┐         ┌──────────────────────────────┐
│       NEON POSTGRESQL + PGVECTOR  │         │       REDIS PUB/SUB          │
│   Traces, Events, Vector Embeddings│         │    WebSocket Event Fan-out   │
└─────────────────┬─────────────────┘         └──────────────┬───────────────┘
                  │                                          │
                  ▼                                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         CORE REASONING SERVICES                            │
│  ┌────────────────────────┐  ┌───────────────────────┐  ┌───────────────┐  │
│  │  Trace Reconstruction  │  │   Execution Graph     │  │ Deterministic │  │
│  │   (Tree & Depth Calc)  │  │  (Nodes & Edges Map)  │  │ Anomaly Rules │  │
│  └──────────┬─────────────┘  └───────────┬───────────┘  └───────┬───────┘  │
│             └────────────────────────────┼──────────────────────┘          │
│                                          ▼                                 │
│                       AI Root-Cause Investigation Engine                   │
│                    (Dual-LLM: Groq Llama 3.3 + Gemini Flash)               │
└──────────────────────────────────────────┬─────────────────────────────────┘
                                           │
                      ┌────────────────────┴────────────────────┐
                      ▼                                         ▼
┌───────────────────────────────────────────┐ ┌──────────────────────────────┐
│       REACT OBSERVABILITY DASHBOARD       │ │       MCP SERVER (:stdio)    │
│  - Real-Time React Flow Execution Graph   │ │  - 7 Read-Only Debug Tools   │
│  - Root-Cause Investigation Panel         │ │  - Claude Desktop / Cursor   │
│  - Side-by-Side Run Comparison View       │ │  - Structured Error Guards   │
│  - pgvector Historical Failure Search     │ │  - Redacted Context Outputs  │
└───────────────────────────────────────────┘ └──────────────────────────────┘
```

---

## 🗄️ Database Schema & Entity Relationships

```
┌─────────────────────────────────┐
│             TRACES              │
├─────────────────────────────────┤
│ trace_id (PK, VARCHAR)          │
│ name (VARCHAR)                  │
│ project_name (VARCHAR, Indexed) │
│ status (VARCHAR, Indexed)       │
│ start_time (TIMESTAMP, Indexed) │
│ end_time (TIMESTAMP, Nullable)  │
│ metadata (JSONB)                │
│ created_at (TIMESTAMP)          │
└───────────────┬─────────────────┘
                │ 1
                │
                │ N
┌───────────────▼─────────────────┐         ┌─────────────────────────────────┐
│             EVENTS              │         │       FAILURE_EMBEDDINGS        │
├─────────────────────────────────┤         ├─────────────────────────────────┤
│ event_id (PK, VARCHAR)          │         │ id (PK, VARCHAR)                │
│ trace_id (FK, Indexed)          │         │ trace_id (FK, Indexed)          │
│ parent_event_id (Nullable)      │         │ finding_id (VARCHAR)            │
│ event_type (VARCHAR, Indexed)   │         │ rule (VARCHAR, Indexed)         │
│ timestamp (TIMESTAMP, Indexed)  │         │ failure_text (TEXT)             │
│ data (JSONB)                    │         │ embedding (VECTOR[768], Indexed)│
│ metadata (JSONB)                │         │ created_at (TIMESTAMP)          │
└─────────────────────────────────┘         └─────────────────────────────────┘
```

---

## 🛠️ Technology Stack

### Backend & Core Services
- **Python 3.11+**
- **FastAPI 0.115+** (Asynchronous REST API framework)
- **SQLAlchemy 2.0+ & asyncpg** (Asynchronous PostgreSQL ORM)
- **Pydantic v2** (Type validation and schema contracts)
- **Uvicorn** (ASGI production server)

### Storage & Real-Time Messaging
- **Neon PostgreSQL**: Cloud serverless PostgreSQL with native SSL.
- **pgvector**: High-performance PostgreSQL extension for HNSW/IVFFlat vector similarity search.
- **Redis 7 (Alpine)**: In-memory Pub/Sub message broker for WebSocket streams.

### AI & Reasoning Layer
- **Groq SDK** (`llama-3.3-70b-versatile` for ultra-low latency root-cause inference)
- **Google GenAI SDK** (`gemini-2.5-flash` for reasoning & text embeddings)
- **Model Context Protocol (MCP 2.0+)**: Standard stdio interface for agent-to-agent observability.

### Frontend Dashboard
- **React 18/19 & TypeScript 5.6**
- **Vite 5** (Fast ES module bundler)
- **Tailwind CSS** (Cosmic dark glassmorphism design system)
- **@xyflow/react (React Flow 12)** (Interactive node-based execution graph with custom controls)
- **Vitest & React Testing Library** (Frontend unit and component test suites)

### Python SDK
- **agentlens**: Lightweight zero-dependency core client featuring background daemon flushing, exponential backoff, and thread-safe context stacks.

---

## 🔒 Data Security & Validation

AgentLens is built with security hardening (Phase 17):
- **Constant-Time Authentication**: Uses `secrets.compare_digest` across configured API keys (`AGENTLENS_API_KEYS`).
- **Recursive Credential Redaction**: Automatically scrubs Bearer tokens, passwords, database URIs, and private API keys from telemetry payloads before storage and before passing context to LLMs.
- **Strict Ingestion Limits**: Rejects oversized payloads (maximum 1,000 events or 2MB per batch, max 256 chars for IDs).
- **Prompt Injection Delimiters**: Telemetry injected into LLM analysis prompts is sanitized and wrapped within structured XML delimiters (`<telemetry_context>`) with strict instructions preventing prompt escapes.
- **Read-Only MCP Boundaries**: The MCP server contains **zero write tools** — it cannot modify code, alter database records, or execute arbitrary bash/SQL commands.
- **OWASP Security Headers**: Sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and restrictive CORS headers.

---

## 🚀 Installation & Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**
- **Docker** and **Docker Compose**
- Free **Neon PostgreSQL** account ([neon.tech](https://neon.tech))

### 1. Clone the Repository
```bash
git clone https://github.com/Siva-2517/AgentLens.git
cd AgentLens
```

### 2. Configure Environment
```bash
cp .env.example .env
```
Open `.env` and fill in your Neon database connection string and optional LLM keys:
```env
DATABASE_URL=postgresql+asyncpg://<username>:<password>@<ep-name>.neon.tech/agentlens?sslmode=require
REDIS_URL=redis://localhost:6379/0
AGENTLENS_API_KEYS=test_api_key_123,development_secret_key
GROQ_API_KEY=gsk_your_groq_api_key
GEMINI_API_KEY=AIzaSy_your_gemini_api_key
```

### 3. Start Redis
```bash
docker-compose up -d redis
```

### 4. Start the Backend API
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate      # On Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 5. Start the React Frontend Dashboard
Open a new terminal:
```powershell
cd frontend
npm install
npm run dev
```
- Open your browser at: `http://localhost:5173`

### 6. Run the Customer Support Demo Agent
Generate live telemetry to populate the dashboard:
```powershell
# From the project root
python demo/demo.py
```

### 7. Stream Real-Time Events (Live Animation Test)
Stream execution events step-by-step with 1.5-second pauses to observe live WebSocket node animations:
```powershell
python backend/stream_live_demo.py
```

---

## 📡 Environment Variables

### Backend (`.env`)
| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | Neon PostgreSQL connection string (asyncpg) | `postgresql+asyncpg://user:pass@ep-name.neon.tech/agentlens?sslmode=require` |
| `REDIS_URL` | **Yes** | Redis connection URL for Pub/Sub | `redis://localhost:6379/0` |
| `AGENTLENS_API_KEYS`| **Yes** | Comma-separated valid API authorization keys | `test_api_key_123,dev_key` |
| `GROQ_API_KEY` | Optional| API key for Groq LLM investigations | `gsk_...` (falls back to mock if omitted) |
| `GEMINI_API_KEY` | Optional| API key for Gemini LLM and pgvector embeddings | `AIzaSy...` (falls back to mock if omitted) |
| `CORS_ORIGINS` | Optional| Allowed browser origins | `http://localhost:5173,http://localhost:3000` |
| `MAX_EVENT_BATCH_SIZE`| Optional| Maximum allowed events per HTTP request | `1000` |

### Frontend (`frontend/.env`)
| Variable | Required | Description | Default |
|---|---|---|---|
| `VITE_API_URL` | Optional| Backend API base URL | `http://localhost:8000` |
| `VITE_WS_URL` | Optional| Backend WebSocket base URL | `ws://localhost:8000` |
| `VITE_AGENTLENS_API_KEY`| Optional| API authentication key sent by browser | `test_api_key_123` |

---

## 📡 API Endpoints Specification

### Traces & Ingestion (`/api/v1`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/v1/traces` | Protected | Create or start a new execution trace |
| GET | `/api/v1/traces` | Protected | List traces with pagination, status, and project filters |
| GET | `/api/v1/traces/{trace_id}` | Protected | Fetch reconstructed trace tree with depth & duration metrics |
| POST | `/api/v1/events` | Protected | Ingest batch of execution events (up to 1,000) |

### Graph, Findings & Investigation (`/api/v1`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/v1/traces/{trace_id}/graph` | Protected | Get directed execution graph (nodes, edges, layout metrics) |
| GET | `/api/v1/traces/{trace_id}/findings` | Protected | Evaluate trace against 8 deterministic anomaly rules |
| GET | `/api/v1/traces/{trace_id}/investigation` | Protected | Run AI root-cause investigation with verified evidence |

### Comparison & Historical Search (`/api/v1`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/v1/traces/compare` | Protected | Compare two runs side-by-side (`?trace_a=...&trace_b=...`) |
| POST | `/api/v1/traces/{trace_id}/index` | Protected | Compute 768-dim embeddings and index failures into pgvector |
| GET | `/api/v1/failures/search` | Protected | Natural language semantic failure search (`?query=...&limit=5`) |

### Real-Time Streaming (`/api/v1`)
| Protocol | Endpoint | Access | Description |
|---|---|---|---|
| WS | `/api/v1/ws/traces/{trace_id}?token=...` | Protected | Subscribe to live Redis event updates for an active trace |

---

## 🔌 Model Context Protocol (MCP)

AgentLens exposes a fully compliant Model Context Protocol server over standard `stdio`.

### Start the Server:
```powershell
python -m app.mcp.server
```

### The 7 Read-Only MCP Tools:
| MCP Tool Name | Description | Parameters |
|---|---|---|
| `get_trace` | Fetches complete reconstructed trace hierarchy | `trace_id` (string) |
| `get_execution_graph` | Returns nodes, directed edges, and waterfall order | `trace_id` (string) |
| `get_trace_findings` | Returns deterministic failure findings | `trace_id` (string) |
| `investigate_trace` | Runs AI root-cause investigation | `trace_id` (string) |
| `compare_traces` | Performs topological comparison between two runs | `trace_a` (string), `trace_b` (string) |
| `search_historical_failures` | Executes cosine similarity search over past incidents | `query` (string), `limit` (int) |
| `list_recent_traces` | Lists recent agent runs with metadata | `limit` (int), `status` (string) |

---

## 📁 Project Structure

```
AgentLens/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routers (v1 traces, events, websockets, dependencies)
│   │   ├── db/              # SQLAlchemy models, repositories, session manager
│   │   ├── mcp/             # Model Context Protocol server, tools, and redaction
│   │   ├── models/          # Pydantic schemas (trace, event, graph, investigation, etc.)
│   │   ├── services/        # 13 core business services (reconstruction, detector, AI, search)
│   │   ├── config.py        # Centralized settings & environment loader
│   │   └── main.py          # FastAPI application entry point & lifecycle hooks
│   ├── tests/               # 13 backend pytest test files (210 automated tests)
│   ├── init_db.py           # CLI database tables initialization utility
│   ├── stream_live_demo.py  # Interactive real-time event streaming script
│   ├── validate_phase18.py  # 21-point comprehensive end-to-end validator
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React components (TraceGraph, InvestigationPanel, TraceComparison, etc.)
│   │   ├── services/        # API client and WebSocket real-time subscription service
│   │   ├── types/           # TypeScript contracts matching backend Pydantic models
│   │   ├── utils/           # Graph adapters, formatters, and color utilities
│   │   ├── App.tsx          # Main dashboard shell, state management, and split-pane layout
│   │   └── main.tsx         # React entry point
│   ├── src/__tests__/       # 11 Vitest frontend component test suites (59 tests)
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── sdk/
│   ├── agentlens/           # Python SDK source (client, context, exporter, types)
│   ├── examples/            # usage_example.py (reference implementation)
│   ├── tests/               # SDK pytest test suites (43 tests)
│   └── setup.py
│
├── demo/
│   ├── agent/               # Customer Support Demo Agent (LangGraph, state, runner, tools)
│   ├── tests/               # Demo agent pytest test suites (34 tests)
│   ├── demo.py              # Main interactive customer support demo runner
│   ├── quick_test.py        # Fast offline tool and graph smoke tester
│   └── pytest.ini
│
├── docker-compose.yml       # Production-aligned Redis 7 container
├── .env.example             # Sanitized environment variable template
├── CLAUDE.md                # Engineering principles and architectural guide
└── README.md
```

---

## 🧪 Verification & Automated Test Suite

AgentLens maintains high test coverage with **346 total automated tests** across all tiers:

```powershell
# 1. Run Backend Pytest Suite (210 tests)
python -m pytest backend/tests/ -q

# 2. Run Python SDK Pytest Suite (43 tests)
python -m pytest sdk/tests/ -q

# 3. Run Demo Agent Pytest Suite (34 tests)
python -m pytest demo/ -q

# 4. Run Frontend Vitest Suite (59 tests)
npm --prefix frontend test -- --run

# 5. Build Production Frontend Bundle
npm --prefix frontend run build

# 6. Run Complete End-to-End System Validation (Phase 18)
python backend/validate_phase18.py
```

---

## 📄 License & Author

Distributed under the **MIT License**.

**Author**: [Siva](https://github.com/Siva-2517)  
**Project**: [AgentLens — AI-Powered Agent Observability](https://github.com/Siva-2517/AgentLens)

<p align="center">
  Built with ❤️ for Transparent, Reliable, and Debuggable AI Agents
</p>
