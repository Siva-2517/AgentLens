# Project Description Document

## Project Title

**AgentLens — AI-Powered Observability and Failure Investigation Platform for AI Agents**

---

## 1. Project Overview

AgentLens is an AI-powered platform designed to **continuously monitor, analyze, and debug AI agents** running inside websites and applications.

The platform collects the agent's execution traces through an SDK or MCP integration. It tracks LLM calls, tool calls, inputs, outputs, state changes, errors, retries, and execution flow.

When an agent encounters an error or abnormal behavior, AgentLens analyzes the complete execution history and identifies:

* Where the first failure occurred
* What caused the failure
* Which subsequent actions were affected
* Why the agent made the incorrect decision
* How the developer can fix the problem

The platform also provides a real-time dashboard, execution visualization, failure analysis, and replay functionality.

---

# 2. Traditional Problem

* AI agents are increasingly being used for automation, customer support, coding, research, and decision-making.
* AI agents can perform multiple LLM calls, tool calls, API requests, database operations, and state transitions.
* When an agent fails, traditional logs usually show only the immediate error.
* Developers cannot easily identify the **first incorrect decision** made by the agent.
* A single incorrect decision can create multiple downstream failures.
* Debugging requires manually examining prompts, responses, tool calls, API logs, and application logs.
* Existing monitoring systems generally focus on application performance and technical errors rather than understanding **agent decision-making and failure causality**.

---

# 3. Proposed Solution

AgentLens provides a dedicated observability and debugging layer for AI agents.

* Developers integrate their AI agents with AgentLens using an **SDK, framework integration, or MCP**.
* AgentLens continuously collects execution events.
* Every agent run is converted into a structured execution trace.
* The system constructs an execution graph showing how the agent progressed.
* AI analyzes the trace to identify abnormal behavior and failures.
* The system determines the likely root cause and separates it from downstream symptoms.
* Developers can inspect the evidence behind the analysis.
* A replay system allows developers to reproduce and compare failed and successful executions.

---

# 4. Main Objectives

1. Continuously monitor AI-agent execution.
2. Capture complete agent execution traces.
3. Detect errors and abnormal agent behavior.
4. Identify the first point of failure.
5. Perform AI-based root-cause analysis.
6. Visualize agent execution as an interactive graph.
7. Explain why an agent made a particular decision.
8. Identify downstream effects of an initial failure.
9. Provide recommended corrective actions.
10. Allow failed executions to be replayed and compared.
11. Maintain historical failure information for future analysis.

---

# 5. Target Users

### Primary Users

* AI developers
* AI/ML engineers
* Backend developers
* Agent developers
* Full-stack developers building AI applications
* Organizations deploying AI agents

### Example Applications

* Customer-support agents
* AI research agents
* Coding agents
* Data-analysis agents
* Business automation agents
* Multi-agent systems
* RAG-based agents
* Tool-using AI agents

---

# 6. How the System Works

```text
User's Website/Application
          ↓
       AI Agent
          ↓
   AgentLens SDK/MCP
          ↓
   Trace Collection
          ↓
    AgentLens Backend
          ↓
   Execution Graph
          ↓
 Failure/Anomaly Detection
          ↓
 AI Root-Cause Analysis
          ↓
 Recommended Fix
          ↓
    Web Dashboard
```

---

# 7. Core Modules

## Module 1 — Agent Integration

Provides methods for connecting an external AI agent to AgentLens.

### Requirements

* Python SDK
* JavaScript/TypeScript SDK — optional second phase
* MCP integration
* API-key-based project authentication
* Framework integrations

### Initial framework

Start with:

* LangGraph
* Custom Python agents

Later:

* LangChain
* Other agent frameworks

---

# 8. Module 2 — Trace Collection

Collect execution events from the connected agent.

### Events to capture

* Agent start
* User request
* LLM request
* LLM response
* Tool selection
* Tool input
* Tool output
* API calls
* Database operations
* State changes
* Errors
* Retries
* Agent completion
* Agent termination

Example:

```text
User Request
     ↓
LLM Call
     ↓
Tool Selection
     ↓
Tool Call
     ↓
Tool Result
     ↓
State Update
     ↓
LLM Call
     ↓
Final Response
```

---

# 9. Module 3 — Execution Trace Engine

Convert raw events into a structured trace.

Each trace should contain:

```text
Trace ID
Agent ID
Session ID
Timestamp
Event Type
Parent Event
Input
Output
Tool
Model
Latency
Error
Status
```

This allows the complete execution history to be reconstructed.

---

# 10. Module 4 — Execution Graph

Convert the trace into a visual graph.

Example:

```text
             User
              ↓
           Planner
              ↓
         Search Tool
              ↓
        Data Extraction
              ↓
         API Request
              ↓
            Error
              ↓
            Retry
```

The graph should allow the developer to click on individual nodes and inspect their details.

---

# 11. Module 5 — Failure Detection

Detect different types of agent failures.

### Initial failure categories

* Wrong tool selection
* Invalid tool parameters
* Tool execution failure
* API failure
* Database failure
* Schema violation
* Context loss
* Incorrect state transition
* Agent loop
* Excessive retries
* Hallucinated information
* Unexpected tool output
* Planning failure
* Goal deviation
* Permission failure

---

# 12. Module 6 — AI Root-Cause Investigator

This is the **main AI component** of the project.

Instead of simply reporting:

```text
API Error
```

AgentLens analyzes the entire trace.

Example:

```text
Step 1  User Request       ✓
Step 2  Planning           ✓
Step 3  Tool Selection     ✓
Step 4  Parameter Creation ✗
Step 5  API Request        ✗
Step 6  Retry              ✗
```

The system generates:

```text
Root Cause:
Incorrect parameter generated at Step 4.

Evidence:
The previous tool returned customer ID X,
but the agent generated customer ID Y.

Downstream Impact:
Steps 5 and 6.

Recommended Fix:
Validate the customer ID before executing
the API request.
```

---

# 13. Module 7 — Anomaly Detection

The platform should identify unusual behavior even when there is no explicit error.

Example:

```text
Normal:

Search → Database → Response

Abnormal:

Search → Search → Search → Search → Search
```

AgentLens can identify this as:

```text
⚠ Possible Agent Loop
```

Other examples:

* Unusually high number of tool calls
* Excessive retries
* Unexpected tool sequence
* Sudden increase in execution time
* Unusual token consumption
* Repeated identical actions

---

# 14. Module 8 — Real-Time Monitoring

The dashboard should update while an agent is running.

Example:

```text
Agent Status: 🟢 Running

User Request        ✓
Planning            ✓
Tool Selection      ✓
Database Query      ⏳
LLM Response        -
Final Response      -
```

If an error occurs:

```text
🔴 Failure Detected

Step: Database Query

Error:
Invalid customer ID
```

The developer does not have to wait until the entire run finishes.

---

# 15. Module 9 — AI Explanation

The developer should be able to ask:

> Why did the agent fail?

The system should explain using the execution evidence.

Example:

```text
The agent selected the correct tool but generated
an invalid customer ID.

The invalid ID originated from the previous LLM
response.

The API failure was therefore a downstream effect,
not the original failure.
```

Other useful questions:

* Why did the agent select this tool?
* What caused this error?
* What was the first incorrect decision?
* Which steps were affected?
* Why did the agent retry?
* What should have happened?
* How can this failure be prevented?

---

# 16. Module 10 — Replay Engine

Store enough information to reproduce an execution.

```text
Failed Run
    ↓
Replay
    ↓
Modify Configuration
    ↓
Run Again
    ↓
Compare
```

Example:

```text
Original Run
❌ Failed

Modified Run
✓ Successful
```

The system should show the point where the two executions diverged.

---

# 17. Module 11 — Historical Failure Knowledge Base

Store previous incidents.

```text
Failure #001
Failure #002
Failure #003
...
```

When a new failure occurs:

```text
New Failure
     ↓
Embedding
     ↓
Vector Search
     ↓
Similar Historical Failures
     ↓
AI Investigation
```

This allows AgentLens to learn from previous incidents without directly retraining the underlying LLM.

---

# 18. Module 12 — MCP Integration

AgentLens can expose investigation capabilities through MCP.

Example tools:

```text
get_trace()
get_agent_status()
investigate_failure()
compare_runs()
search_similar_failures()
replay_trace()
get_recommendation()
```

This allows another AI agent to interact with AgentLens programmatically.

---

# 19. Web Dashboard

The dashboard is the main user interface.

### Dashboard pages

### 1. Overview

```text
Total Agents
Total Runs
Successful Runs
Failed Runs
Active Agents
Detected Anomalies
```

### 2. Live Agents

Shows currently running agents.

### 3. Trace Explorer

Shows individual executions.

### 4. Execution Graph

Interactive graph of agent execution.

### 5. Failure Investigation

Shows:

* Failure
* Root cause
* Evidence
* Impact
* Recommendation

### 6. Replay

Compare original and replayed execution.

### 7. Historical Incidents

Search previous failures.

---

# 20. Suggested Technology Stack

## Frontend

```text
React
TypeScript
Tailwind CSS
React Flow
Recharts
```

## Backend

```text
Python
FastAPI
Pydantic
WebSockets
```

## AI / Agent

```text
LangGraph
LangChain
Gemini API
Groq API
```

## Database

```text
PostgreSQL
pgvector
```

## Infrastructure

```text
Redis
Docker
GitHub Actions
```

## Integration

```text
Python SDK
MCP
REST API
WebSockets
```

---

# 21. High-Level Architecture

```text
                         USER APPLICATION
                               │
                               ▼
                         ┌───────────┐
                         │ AI Agent  │
                         └─────┬─────┘
                               │
                     SDK / MCP / API
                               │
                               ▼
                     ┌─────────────────┐
                     │ Trace Collector │
                     └────────┬────────┘
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
        PostgreSQL          Redis          Event Store
             │
             ▼
       Execution Graph
             │
             ▼
     Failure Detection
             │
             ▼
    AI Investigation Engine
             │
        ┌────┴────┐
        ▼         ▼
      LLM      pgvector
        │         │
        └────┬────┘
             ▼
      Root Cause Analysis
             │
             ▼
      Recommendation
             │
             ▼
       React Dashboard
```

---

# 22. Data Flow

```text
1. User sends request
        ↓
2. AI agent starts execution
        ↓
3. AgentLens SDK captures events
        ↓
4. Events sent to AgentLens backend
        ↓
5. Events stored in PostgreSQL
        ↓
6. Execution graph generated
        ↓
7. Failure/anomaly detector analyzes execution
        ↓
8. AI investigator analyzes suspicious traces
        ↓
9. Historical failures retrieved using pgvector
        ↓
10. Root cause generated
        ↓
11. Dashboard updated
        ↓
12. Developer investigates/replays/fixes agent
```

---

# 23. Security Requirements

Since agent traces may contain sensitive information, security is important.

### Requirements

* API-key authentication
* JWT authentication for dashboard
* HTTPS
* Project-level isolation
* User-level access control
* Encryption of sensitive credentials
* Avoid storing API keys from connected applications
* Configurable sensitive-data masking
* PII redaction
* Secure database access
* Audit logs

### Important design decision

Do **not** unnecessarily store complete passwords, API keys, access tokens, or other secrets contained in agent traces.

---

# 24. MVP Scope

For the first working version, don't build everything.

### MVP should contain:

```text
✓ Custom Python AI Agent
✓ AgentLens Python SDK
✓ FastAPI backend
✓ PostgreSQL
✓ Trace collection
✓ Live execution monitoring
✓ React dashboard
✓ Execution graph
✓ Error detection
✓ AI root-cause analysis
✓ Basic failure history
```

This is enough for a strong demonstration.

---

# 25. Advanced Version

After the MVP works:

```text
✓ MCP Server
✓ JavaScript SDK
✓ LangGraph integration
✓ Replay engine
✓ pgvector similarity search
✓ Anomaly detection
✓ Failure comparison
✓ Multiple-agent support
✓ More agent frameworks
✓ IDE integration
```

---

# 26. Example Demonstration

Create a customer-support AI agent.

User asks:

```text
"Find my order ORD-83921 and tell me its status."
```

Agent execution:

```text
User Request
     ↓
Planner                 ✓
     ↓
Order Search            ✓
     ↓
Extract Order ID        ✓
     ↓
Generate API Input      ✗
     ↓
Order API               ✗
     ↓
Retry                   ✗
     ↓
Final Response          ✗
```

AgentLens detects:

```text
FIRST FAILURE:
Generate API Input

ROOT CAUSE:
Incorrect order ID generated.

DOWNSTREAM EFFECT:
API failure → retry → incorrect response

RECOMMENDATION:
Validate order ID against the original
user request before API execution.
```

The developer can then click:

**Replay → Fix validation → Run again → Compare**

---

# 27. Evaluation Metrics

To make this suitable for a final-year academic project, measure the system.

### Metrics

* Root-cause detection accuracy
* Failure classification accuracy
* Anomaly detection precision
* False-positive rate
* Investigation latency
* Trace collection overhead
* Replay success rate
* Recommendation accuracy

For example, create a controlled test set containing different types of agent failures and measure how accurately AgentLens identifies the actual first failure.

---

# 28. Expected Outcome

The final system should allow a developer to connect an AI agent to AgentLens and see:

```text
🟢 Agent Running

        ↓

Live Execution Trace

        ↓

⚠ Anomaly / Error

        ↓

AI Investigation

        ↓

🔴 Root Cause Identified

        ↓

Evidence + Impact

        ↓

Recommended Fix

        ↓

Replay

        ↓

✓ Verified Improvement
```

---

# 29. What Makes the Project Different

The project is **not simply an AI chatbot, monitoring dashboard, or error logger**.

Its main purpose is:

> **Understanding the behavior and failure causality of autonomous AI agents.**

The important distinction is:

```text
Traditional Monitoring

"What error occurred?"

             ↓

AgentLens

"What did the agent do?"
        ↓
"Where did it first go wrong?"
        ↓
"Why did it go wrong?"
        ↓
"What failures did it cause?"
        ↓
"How can we fix it?"
        ↓
"Can we replay and verify the fix?"
```

---

# 30. Final Project Definition

**AgentLens is an AI-powered observability and failure-investigation platform that continuously monitors AI-agent execution, reconstructs agent behavior, detects failures and anomalies, performs AI-based root-cause analysis, and provides evidence-based recommendations and replay capabilities to help developers debug and improve autonomous AI systems.**
