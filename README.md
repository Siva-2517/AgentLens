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

## 🚀 Live Production Deployments & Links

- 🌐 **Live Web Dashboard**: [https://agent-lens-kappa.vercel.app](https://agent-lens-kappa.vercel.app) *(Hosted on Vercel)*
- ⚡ **Production Backend API**: [https://agentlens-backend-ofqg.onrender.com](https://agentlens-backend-ofqg.onrender.com) *(Hosted on Render)*
- 📚 **Interactive Swagger API Docs**: [https://agentlens-backend-ofqg.onrender.com/docs](https://agentlens-backend-ofqg.onrender.com/docs)
- 🐙 **GitHub Repository**: [GitHub — Siva-2517/AgentLens](https://github.com/Siva-2517/AgentLens)
- 🖥️ **Local Dashboard**: `http://localhost:5173` *(React + Vite)*
- 🔗 **Local Backend API**: `http://localhost:8000/docs` *(FastAPI)*

---

## 📋 Table of Contents

- [Overview](#-overview)
- [How to Use AgentLens in Your Project](#-how-to-use-agentlens-in-your-project)
- [Key Features](#-key-features)
- [AgentLens Pipeline & Architecture](#-agentlens-pipeline--architecture)
- [Database Schema & Entity Relationships](#-database-schema--entity-relationships)
- [Technology Stack](#-technology-stack)
- [Data Security & Validation](#-data-security--validation)
- [Installation & Quick Start (Local Setup)](#-installation--quick-start)
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

## 📦 How to Use AgentLens in Your Project

Follow these steps to observe, trace, and debug your AI agents in real time using the live deployment:

### 1. Get Your API Key & Project Identifier
1. Open the live dashboard: **[https://agent-lens-kappa.vercel.app](https://agent-lens-kappa.vercel.app)**
2. Sign in or register a new account.
3. In the top navigation bar, click **API Keys**.
4. Click **Create New Key** and copy your generated key (`al_live_...`).
5. Note your **Project Slug** (e.g. `default-project`) from the project selector.

### 2. Install the AgentLens Python SDK
Install the SDK from PyPI:

```bash
pip install agentlensx
```

Or directly from GitHub into your agent's virtual environment:

```bash
pip install git+https://github.com/Siva-2517/AgentLens.git#subdirectory=sdk
```

*(Alternatively, if you cloned the repository locally: `pip install -e ./sdk`)*

### 3. Instrument Your Agent Code
Wrap your agent run with `lens.trace(...)` and log LLM decisions, tool calls, and state transitions:

```python
import os
from agentlensx import AgentLens, EventType

# 1. Initialize the SDK pointing to the live production backend
lens = AgentLens(
    api_url="https://agentlens-backend-ofqg.onrender.com",  # Or http://localhost:8000 for local dev
    api_key=os.getenv("AGENTLENS_API_KEY", "al_live_your_api_key_here"),
    project_name="my-first-agent"                           # Matches your project in the dashboard
)

# 2. Use the context manager to automatically manage trace lifecycles
with lens.trace("Customer Support Assistant") as trace_id:
    print(f"Tracking agent execution live! Trace ID: {trace_id}")

    # Record LLM reasoning / prompt
    lens.create_event(
        EventType.LLM_CALL,
        data={
            "model": "gpt-4o",
            "prompt": "User query: Where is my order #ORD-1001?",
        }
    )

    # Record tool execution (e.g., database lookup, external API call)
    lens.create_event(
        EventType.TOOL_CALL,
        data={
            "tool": "check_order_status",
            "input": {"order_id": "ORD-1001"},
        }
    )

    # Record tool response
    lens.create_event(
        EventType.TOOL_RESPONSE,
        data={
            "status": "in_transit",
            "carrier": "FedEx",
            "expected_delivery": "Tomorrow by 5 PM"
        }
    )

    # Record LLM final response
    lens.create_event(
        EventType.LLM_RESPONSE,
        data={"response": "Your order #ORD-1001 is in transit via FedEx and will arrive tomorrow."}
    )

# When the context block exits:
# - An AGENT_END event is automatically dispatched
# - The trace is marked as 'completed' (or 'failed' if an unhandled exception occurred)
# - All telemetry is safely flushed
```

### 4. Watch Live Real-Time Telemetry & AI Diagnosis
1. Return to the dashboard at **[https://agent-lens-kappa.vercel.app](https://agent-lens-kappa.vercel.app)**.
2. Select your project from the top bar.
3. Your new trace will appear in the **Traces** list with a yellow `running` badge.
4. Click on the trace to watch nodes, edges, latency, and payloads animate **live in real time** via WebSockets!
5. If an agent crashes or encounters an anomaly, click **Investigate with AI** to view a root-cause diagnosis, cited evidence IDs, and recommended code fixes powered by Groq Llama 3.3 and Gemini Flash.

### 5. Alternative: Direct REST API (For Node.js, Go, LangChain JS, or cURL)
If you prefer not to use the Python SDK, you can send HTTP POST requests directly to the backend:

```bash
# 1. Initialize a Trace
curl -X POST https://agentlens-backend-ofqg.onrender.com/api/v1/traces \
  -H "Authorization: Bearer al_live_your_key" \
  -H "X-AgentLens-Project: my-first-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "trace_id": "custom-trace-001",
    "name": "Order Tracking Workflow",
    "status": "running"
  }'

# 2. Ingest an Event
curl -X POST https://agentlens-backend-ofqg.onrender.com/api/v1/events/single \
  -H "Authorization: Bearer al_live_your_key" \
  -H "X-AgentLens-Project: my-first-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt-001",
    "trace_id": "custom-trace-001",
    "event_type": "LLM_CALL",
    "timestamp": "2026-10-14T12:00:00Z",
    "data": {"model": "gpt-4o", "prompt": "Process user input"}
  }'
```

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
- **agentlensx**: Lightweight zero-dependency core client featuring background daemon flushing, exponential backoff, and thread-safe context stacks.

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
- Free **Neon PostgreSQL** account ([neon.tech](https://neon.tech))
- Free **Redis Cloud** account ([redis.io](https://redis.io))

### 1. Clone the Repository
```bash
git clone https://github.com/Siva-2517/AgentLens.git
cd AgentLens
```

### 2. Configure Dedicated Environments
Each service is fully decoupled with its own dedicated `.env` file:
```bash
# 1. Backend environment
cp backend/.env.example backend/.env

# 2. Frontend environment
cp frontend/.env.example frontend/.env

# 3. Demo agent environment (optional, for running live demo agent)
cp demo/.env.example demo/.env
```
Fill in your Neon database connection string and Redis Cloud endpoint in `backend/.env`:
```env
DATABASE_URL=postgresql+asyncpg://<username>:<password>@<ep-name>.neon.tech/agentlens?sslmode=require
REDIS_URL=redis://default:<password>@<host>:<port>
GROQ_API_KEY=gsk_your_groq_api_key
GEMINI_API_KEY=AIzaSy_your_gemini_api_key
```

### 3. Verify Cloud Infrastructure
Test your Neon PostgreSQL and Redis Cloud endpoints directly:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate      # On Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python verify_neon.py        # Verifies Neon PostgreSQL & pgvector
python verify_redis.py       # Verifies Redis Cloud connection & Pub/Sub
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
Stream execution events step-by-step with 1.5-second pauses to observe live WebSocket node animations in the dashboard:
```powershell
# Standard live stream (from project root)
python backend/stream_live_demo.py

# Or run from the demo directory
cd demo
python stream_live_demo.py

# Simulate an error/timeout to test AI Root Cause Analysis & pgvector search:
python backend/stream_live_demo.py --simulate-failure

# Customize step pause duration (e.g. 2.0 seconds):
python backend/stream_live_demo.py --interval 2.0
```
Open **`http://localhost:5173`** and click the generated trace ID to observe nodes, links, and logs animating live in real time.

---

## 📡 Environment Variables

### Backend (`backend/.env`)
| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | Neon PostgreSQL connection string (asyncpg) | `postgresql+asyncpg://user:pass@ep-name.neon.tech/agentlens?sslmode=require` |
| `REDIS_URL` | **Yes** | Redis connection URL for Pub/Sub | `redis://default:pass@host:port` |
| `GROQ_API_KEY` | Optional| API key for Groq LLM investigations | `gsk_...` (falls back to mock if omitted) |
| `GEMINI_API_KEY` | Optional| API key for Gemini LLM and pgvector embeddings | `AIzaSy...` (falls back to mock if omitted) |
| `CORS_ORIGINS` | Optional| Allowed browser origins | `http://localhost:5173,http://localhost:3000` |
| `MAX_EVENT_BATCH_SIZE`| Optional| Maximum allowed events per HTTP request | `1000` |

### Frontend (`frontend/.env`)
| Variable | Required | Description | Default |
|---|---|---|---|
| `VITE_API_BASE_URL` | Optional| Backend REST API base URL | `/api/v1` or `http://localhost:8000/api/v1` |
| `VITE_WS_BASE_URL` | Optional| Backend WebSocket base URL | `ws://localhost:8000/api/v1/ws` |

### Demo Agent (`demo/.env`)
| Variable | Required | Description | Default |
|---|---|---|---|
| `AGENTLENS_API_URL` | **Yes** | Target AgentLens API server URL | `http://localhost:8000` |
| `AGENTLENS_API_KEY` | **Yes** | Live API Key created in Dashboard (`al_live_...`) | `al_live_...` |
| `AGENTLENS_PROJECT_NAME` | Optional| Project to attach traces to | `Default Project` |

### Python SDK (`agentlensx`)
The SDK is a pure library that does not depend on any `.env` file on disk. Configure via constructor parameters or process environment variables:
```python
from agentlensx import AgentLens

# Constructor parameters (recommended):
client = AgentLens(
    api_url="http://localhost:8000",
    api_key="al_live_...",
    project_name="Customer Support"
)
```

---

## 📡 API Endpoints Specification

### Traces & Ingestion (`/api/v1`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/v1/traces` | Protected | Create or start a new execution trace |
| GET | `/api/v1/traces` | Protected | List traces with pagination, status, and project filters |
| GET | `/api/v1/traces/{trace_id}` | Protected | Fetch reconstructed trace tree with depth & duration metrics |
| POST | `/api/v1/events` | Protected | Ingest batch of execution events (up to 1,000) |
| POST | `/api/v1/events/single` | Protected | Ingest a single execution event |

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
│   ├── tests/               # 25 backend pytest test files (324 automated tests)
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
│   ├── src/__tests__/       # 15 Vitest frontend component test suites (83 tests)
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── sdk/
│   ├── agentlensx/          # Python SDK source (client, context, exporter, types)
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
├── .env.example             # Sanitized environment variable template
├── CLAUDE.md                # Engineering principles and architectural guide
└── README.md
```

---

## 🚀 Production Cloud Deployment

AgentLens is architected for zero-docker cloud deployment:
- **Frontend Dashboard**: [Vercel](https://vercel.com) (configured via [`frontend/vercel.json`](frontend/vercel.json))
- **Backend API & WebSockets**: [Render](https://render.com) (configured via [`render.yaml`](render.yaml))
- **Database & Vector Search**: [Neon Serverless PostgreSQL](https://neon.tech) (`pgvector`)
- **Pub/Sub & Event Cache**: [Redis Cloud](https://redis.io/cloud) or Upstash
- **Complete Step-by-Step Guide**: See **[Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** for detailed setup, CORS configuration, environment variables, and verification.

---

## 🧪 Verification & Automated Test Suite

AgentLens maintains high test coverage with **484 total automated tests** across all tiers:

```powershell
# 1. Run Backend Pytest Suite (324 tests)
python -m pytest backend/tests/ -q

# 2. Run Python SDK Pytest Suite (43 tests)
python -m pytest sdk/tests/ -q

# 3. Run Demo Agent Pytest Suite (34 tests)
python -m pytest demo/ -q

# 4. Run Frontend Vitest Suite (83 tests)
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
