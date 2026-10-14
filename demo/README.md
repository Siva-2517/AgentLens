# AgentLens Customer Support Demo Agent

Production demo AI agent simulating a multi-step customer support workflow with real-time telemetry streaming to AgentLens.

- 🌐 **Watch Live in Dashboard**: [https://agent-lens-kappa.vercel.app](https://agent-lens-kappa.vercel.app)
- ⚡ **Target API**: [https://agentlens-backend-ofqg.onrender.com](https://agentlens-backend-ofqg.onrender.com) (or `http://localhost:8000`)

---

## Features

- **Multi-Step Agent Execution**: LLM reasoning, order tracking, payment checks, and support ticket creation.
- **Real-Time Telemetry**: Emits `AGENT_START`, `LLM_CALL`, `TOOL_CALL`, `TOOL_RESPONSE`, `STATE_CHANGE`, and `AGENT_END` events.
- **Live Streamer**: Simulates agent steps with 1.5s delays to watch React Flow graph animations live in the web dashboard.
- **Failure Simulation**: `--simulate-failure` flag to test AI Root Cause Analysis and pgvector failure search.

---

## Configuration (`demo/.env`)

Create or update `demo/.env`:

```env
# Point to live production backend or localhost
AGENTLENS_API_URL=https://agentlens-backend-ofqg.onrender.com
AGENTLENS_API_KEY=al_live_your_api_key_from_dashboard
AGENTLENS_PROJECT_NAME=default-project
```

---

## Running the Demos

### 1. Run Standard Customer Support Agent
Executes sample queries (order status, payment verification, ticket creation):

```bash
python demo/demo.py
```

### 2. Stream Live Execution (Real-Time Animation in Dashboard)
Streams each execution step with a 1.5-second pause so you can watch nodes and links appear live in the dashboard:

```bash
python backend/stream_live_demo.py --interval 1.5
```

### 3. Simulate an Agent Failure (Test AI Root Cause Analysis)
Triggers an intentional error scenario to evaluate AI investigation & pgvector semantic matching:

```bash
python backend/stream_live_demo.py --simulate-failure
```
