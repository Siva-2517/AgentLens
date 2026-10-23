import { useState } from 'react';

interface HomePageProps {
  onLogin: () => void;
  onRegister: () => void;
}

export function HomePage({ onLogin, onRegister }: HomePageProps) {
  const [activeCodeTab, setActiveCodeTab] = useState<'sdk' | 'langgraph' | 'mcp'>('sdk');
  const [activeFeatureTab, setActiveFeatureTab] = useState<'graph' | 'realtime' | 'investigation' | 'search'>('graph');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-purple-500 selection:text-white relative overflow-x-hidden font-sans">
      {/* Ambient background glows */}
      <div className="absolute top-0 left-1/4 w-[600px] h-[400px] bg-gradient-to-br from-purple-600/20 via-indigo-600/10 to-transparent blur-3xl pointer-events-none -z-10" />
      <div className="absolute top-1/3 right-10 w-[500px] h-[500px] bg-gradient-to-bl from-cyan-600/15 via-blue-600/10 to-transparent blur-3xl pointer-events-none -z-10" />
      <div className="absolute bottom-10 left-1/3 w-[600px] h-[400px] bg-purple-900/10 blur-3xl pointer-events-none -z-10" />

      {/* ----------------------------------------------------------------------- */}
      {/* 1. Sticky Navigation Bar */}
      {/* ----------------------------------------------------------------------- */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-slate-950/80 border-b border-slate-800/80 px-6 py-3.5 transition-all">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-purple-900/30">
              <span className="text-white font-extrabold text-lg tracking-tight">AL</span>
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                AgentLens
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800/60 font-semibold">
                  v0.1 Cloud
                </span>
              </span>
              <span className="text-[11px] text-slate-400 font-medium">AI Agent Observability</span>
            </div>
          </div>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#features" className="hover:text-purple-400 transition">Features</a>
            <a href="#preview" className="hover:text-purple-400 transition">Live Preview</a>
            <a href="#quickstart" className="hover:text-purple-400 transition">SDK Quickstart</a>
            <a href="#architecture" className="hover:text-purple-400 transition">Architecture</a>
          </nav>

          {/* Action CTAs */}
          <div className="flex items-center gap-3">
            <button
              onClick={onLogin}
              data-testid="btn-nav-login"
              className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/80 rounded-lg transition"
            >
              Sign In
            </button>
            <button
              onClick={onRegister}
              data-testid="btn-nav-register"
              className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 rounded-lg shadow-lg shadow-purple-900/30 transition transform hover:-translate-y-0.5"
            >
              Get Started Free
            </button>
          </div>
        </div>
      </header>

      {/* ----------------------------------------------------------------------- */}
      {/* 2. Hero Section */}
      {/* ----------------------------------------------------------------------- */}
      <section data-testid="homepage-hero" className="relative pt-16 pb-20 px-6 text-center max-w-5xl mx-auto">
        {/* Status Pill */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/90 border border-purple-500/30 text-purple-300 text-xs font-medium mb-8 shadow-inner shadow-purple-900/20">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Real-Time Multi-Agent Observability & Failure Detection</span>
        </div>

        {/* Hero Headline */}
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
          Observe Every Agent Thought.{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-indigo-300 to-cyan-400">
            Debug Every Autonomous Step.
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-base sm:text-xl text-slate-300 max-w-3xl mx-auto mb-10 leading-relaxed font-normal">
          AgentLens gives engineering teams deep observability into autonomous AI agents.
          Stream execution DAGs in real-time, pinpoint cascading failures, and generate AI-powered
          root-cause post-mortems with one line of code.
        </p>

        {/* Hero CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <button
            onClick={onRegister}
            data-testid="btn-hero-register"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-500 hover:from-purple-500 hover:to-cyan-400 shadow-xl shadow-purple-900/40 transition transform hover:-translate-y-0.5 flex items-center justify-center gap-2 text-base"
          >
            <span>Launch Dashboard Free</span>
            <span className="text-lg">➔</span>
          </button>
          <button
            onClick={onLogin}
            data-testid="btn-hero-login"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl font-medium text-slate-200 bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 transition flex items-center justify-center gap-2 text-base"
          >
            <span>Sign In to Existing Account</span>
          </button>
        </div>

        {/* Metrics Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto pt-6 border-t border-slate-800/60">
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
            <div className="text-2xl font-bold text-cyan-400 font-mono">&lt; 50ms</div>
            <div className="text-xs text-slate-400 mt-1">Pub/Sub Fanout Latency</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
            <div className="text-2xl font-bold text-purple-400 font-mono">100%</div>
            <div className="text-xs text-slate-400 mt-1">Deterministic Failure Capture</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
            <div className="text-2xl font-bold text-indigo-400 font-mono">768-dim</div>
            <div className="text-xs text-slate-400 mt-1">pgvector Semantic Memory</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
            <div className="text-2xl font-bold text-emerald-400 font-mono">Native MCP</div>
            <div className="text-xs text-slate-400 mt-1">Cursor & Claude Code Ready</div>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------------- */}
      {/* 3. Interactive Product Preview Showcase */}
      {/* ----------------------------------------------------------------------- */}
      <section id="preview" className="py-16 px-6 max-w-6xl mx-auto w-full">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Designed for Multi-Agent Complexity
          </h2>
          <p className="text-sm text-slate-400 max-w-2xl mx-auto">
            Switch between views to experience the live telemetry, interactive graph reconstruction,
            and root-cause inspection capabilities.
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center justify-center gap-2 mb-6 flex-wrap">
          <button
            onClick={() => setActiveFeatureTab('graph')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeFeatureTab === 'graph'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/30'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            🕸️ Directed Execution Graph
          </button>
          <button
            onClick={() => setActiveFeatureTab('realtime')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeFeatureTab === 'realtime'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/30'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            ⚡ Live Redis Streaming
          </button>
          <button
            onClick={() => setActiveFeatureTab('investigation')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeFeatureTab === 'investigation'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/30'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            🧠 AI Root-Cause Post-Mortem
          </button>
          <button
            onClick={() => setActiveFeatureTab('search')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeFeatureTab === 'search'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/30'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            🔍 pgvector Semantic Search
          </button>
        </div>

        {/* Preview Frame */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl p-6 backdrop-blur-xl relative overflow-hidden">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500/80" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
              <span className="ml-3 text-xs font-mono text-slate-400">trace_id: live-support-9988</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded border border-emerald-800/60">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
              <span>LIVE SUBSCRIBER CONNECTED</span>
            </div>
          </div>

          {activeFeatureTab === 'graph' && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 py-4">
              <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 text-center">
                <div className="text-xs font-mono text-slate-400 mb-1">01. ENTRY</div>
                <div className="text-sm font-bold text-white">thought_node</div>
                <div className="text-[11px] text-purple-300 mt-2 font-mono">Query Analysis</div>
              </div>
              <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-700/60 text-center relative">
                <div className="text-xs font-mono text-indigo-400 mb-1">02. LLM CALL</div>
                <div className="text-sm font-bold text-white">llama-3.3-70b</div>
                <div className="text-[11px] text-indigo-300 mt-2 font-mono">Decision: Tool Call</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 text-center">
                <div className="text-xs font-mono text-slate-400 mb-1">03. TOOL EXEC</div>
                <div className="text-sm font-bold text-white">get_order(ORD-1001)</div>
                <div className="text-[11px] text-emerald-300 mt-2 font-mono">Status: Shipped</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 text-center">
                <div className="text-xs font-mono text-slate-400 mb-1">04. OUTPUT</div>
                <div className="text-sm font-bold text-white">final_response</div>
                <div className="text-[11px] text-cyan-300 mt-2 font-mono">Streamed to User</div>
              </div>
            </div>
          )}

          {activeFeatureTab === 'realtime' && (
            <div className="space-y-3 font-mono text-xs p-4 bg-slate-950 rounded-xl border border-slate-800">
              <div className="text-emerald-400 flex items-center justify-between">
                <span>[14:48:02.120] ➜ REDIS PUB/SUB: Channel "agentlens:trace:live-support-9988"</span>
                <span className="text-slate-500">Latency: 12ms</span>
              </div>
              <div className="text-slate-300 pl-4 border-l border-slate-800">
                event_type: "AGENT_START" | agent_name: "CustomerSupportAgent" | session: "session-abc"
              </div>
              <div className="text-indigo-400 flex items-center justify-between">
                <span>[14:48:02.850] ➜ LLM INFERENCE: Model "groq/llama-3.3-70b-versatile"</span>
                <span className="text-slate-500">Latency: 730ms</span>
              </div>
              <div className="text-cyan-400 flex items-center justify-between">
                <span>[14:48:03.110] ➜ WEBSOCKET BROADCAST: Dispatched to 1 connected browser clients</span>
                <span className="text-slate-500">Echo: Blocked (Instance Match)</span>
              </div>
            </div>
          )}

          {activeFeatureTab === 'investigation' && (
            <div className="p-4 bg-slate-950 rounded-xl border border-rose-900/40 space-y-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-xs font-mono font-bold">
                  CRITICAL ROOT CAUSE
                </span>
                <span className="text-xs font-mono text-slate-400">Rule: RATE_LIMIT_BREACH</span>
              </div>
              <p className="text-sm text-slate-200">
                The agent received HTTP 429 Too Many Requests from the upstream shipping provider API during recursive order validation.
              </p>
              <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 text-xs text-purple-300">
                <strong>Recommended Mitigation:</strong> Introduce exponential backoff with jitter on tool <code className="text-cyan-300">get_order</code> and configure fallback cache lookup.
              </div>
            </div>
          )}

          {activeFeatureTab === 'search' && (
            <div className="space-y-3 p-4 bg-slate-950 rounded-xl border border-slate-800">
              <div className="flex items-center gap-3 bg-slate-900 p-2.5 rounded-lg border border-slate-700">
                <span className="text-slate-400">🔍</span>
                <input
                  type="text"
                  readOnly
                  value="Rate limit exceeded on external API in production"
                  aria-label="Example semantic search query"
                  className="bg-transparent text-xs text-slate-200 w-full focus:outline-none font-mono"
                />
                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800/60">
                  pgvector HNSW Cosine
                </span>
              </div>
              <div className="p-3 bg-slate-900/60 rounded border border-slate-800/80 flex items-center justify-between text-xs">
                <div>
                  <div className="font-semibold text-slate-200">Provider API Throttling Event</div>
                  <div className="text-[11px] text-slate-400">Trace: trace-prod-8871 • Rule: RATE_LIMIT</div>
                </div>
                <div className="text-right">
                  <div className="text-emerald-400 font-mono font-bold">96.4% Match</div>
                  <div className="text-[10px] text-slate-500">2 days ago</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ----------------------------------------------------------------------- */}
      {/* 4. Core Features Grid */}
      {/* ----------------------------------------------------------------------- */}
      <section id="features" className="py-20 px-6 max-w-6xl mx-auto w-full">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-white mb-4">
            Engineered for Production AI Observability
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-sm">
            Everything you need to debug, monitor, and optimize autonomous agent swarms in high-stakes environments.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-purple-900/30 border border-purple-700/40 flex items-center justify-center text-xl mb-4">
              ⚡
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Real-Time Event Streaming</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Sub-50ms event fan-out using Redis Cloud Pub/Sub. Browser clients update dynamically without polling or page refreshes.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-indigo-900/30 border border-indigo-700/40 flex items-center justify-center text-xl mb-4">
              🕸️
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Interactive Directed Graphs</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Automatic DAG construction for every trace run. Inspect multi-step tool calls, LLM prompts, and branching agent loops visually.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-cyan-900/30 border border-cyan-700/40 flex items-center justify-center text-xl mb-4">
              🧠
            </div>
            <h3 className="text-lg font-bold text-white mb-2">AI Root-Cause Post-Mortems</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Automated root-cause analysis powered by Groq (Llama 3.3 70B) and Gemini. Isolate earliest failure points and get suggested code fixes.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-emerald-900/30 border border-emerald-700/40 flex items-center justify-center text-xl mb-4">
              🔍
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Semantic Failure Search</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Neon Cloud PostgreSQL with pgvector HNSW indexing. Query past agent failures using natural language semantic similarity.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-amber-900/30 border border-amber-700/40 flex items-center justify-center text-xl mb-4">
              🔒
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Enterprise Multi-Tenancy</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Organization and project boundaries with SHA-256 hashed API keys (<code className="text-amber-300">al_live_...</code>) and double-submit CSRF cookie protection.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-blue-900/30 border border-blue-700/40 flex items-center justify-center text-xl mb-4">
              🤖
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Model Context Protocol (MCP)</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Native stdio MCP server enabling Cursor, Claude Code, and autonomous developer agents to query trace graphs and historical post-mortems directly.
            </p>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------------- */}
      {/* 5. Code Quickstart Section */}
      {/* ----------------------------------------------------------------------- */}
      <section id="quickstart" className="py-16 px-6 max-w-5xl mx-auto w-full">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Add Observability in Minutes
          </h2>
          <p className="text-sm text-slate-400">
            Plug the AgentLens Python SDK into your existing AI agent workflows.
          </p>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-slate-800 bg-slate-950/60 px-4 pt-3">
            <button
              onClick={() => setActiveCodeTab('sdk')}
              className={`px-4 py-2 text-xs font-mono font-medium rounded-t-lg transition ${
                activeCodeTab === 'sdk'
                  ? 'bg-slate-900 text-purple-400 border-t-2 border-purple-500'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Python SDK
            </button>
            <button
              onClick={() => setActiveCodeTab('langgraph')}
              className={`px-4 py-2 text-xs font-mono font-medium rounded-t-lg transition ${
                activeCodeTab === 'langgraph'
                  ? 'bg-slate-900 text-purple-400 border-t-2 border-purple-500'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              LangGraph Integration
            </button>
            <button
              onClick={() => setActiveCodeTab('mcp')}
              className={`px-4 py-2 text-xs font-mono font-medium rounded-t-lg transition ${
                activeCodeTab === 'mcp'
                  ? 'bg-slate-900 text-purple-400 border-t-2 border-purple-500'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              MCP (Cursor / Claude Code)
            </button>
          </div>

          {/* Code Viewer */}
          <div className="p-6 font-mono text-xs overflow-x-auto text-slate-300 leading-relaxed bg-slate-950/40">
            {activeCodeTab === 'sdk' && (
              <pre className="text-purple-300">
                <span className="text-slate-500"># 1. Install SDK</span>{'\n'}
                <span className="text-cyan-400">pip install</span> agentlensx{'\n\n'}
                <span className="text-slate-500"># 2. Trace your agent execution</span>{'\n'}
                <span className="text-pink-400">from</span> agentlensx <span className="text-pink-400">import</span> AgentLens, EventType{'\n\n'}
                lens = AgentLens(project_name=<span className="text-emerald-300">"customer-support-agent"</span>){'\n\n'}
                <span className="text-pink-400">with</span> lens.trace(<span className="text-emerald-300">"order-inquiry"</span>) <span className="text-pink-400">as</span> trace_id:{'\n'}
                {'    '}lens.create_event(EventType.LLM_CALL, data=&#123;<span className="text-emerald-300">"prompt"</span>: user_query&#125;){'\n'}
                {'    '}result = agent.invoke(user_query){'\n'}
                {'    '}lens.create_event(EventType.TOOL_CALL, data=&#123;<span className="text-emerald-300">"tool"</span>: <span className="text-emerald-300">"check_order"</span>&#125;)
              </pre>
            )}

            {activeCodeTab === 'langgraph' && (
              <pre className="text-indigo-300">
                <span className="text-slate-500"># LangGraph trace listener</span>{'\n'}
                <span className="text-pink-400">from</span> demo.agent.runner <span className="text-pink-400">import</span> DemoAgentRunner{'\n\n'}
                runner = DemoAgentRunner({'\n'}
                {'    '}api_url=<span className="text-emerald-300">"http://localhost:8000"</span>,{'\n'}
                {'    '}project_name=<span className="text-emerald-300">"support-bot"</span>,{'\n'}
                {'    '}use_agentlens=<span className="text-pink-400">True</span>{'\n'}
                ){'\n\n'}
                response = <span className="text-pink-400">await</span> runner.run_user_query(<span className="text-emerald-300">"Where is order ORD-1001?"</span>)
              </pre>
            )}

            {activeCodeTab === 'mcp' && (
              <pre className="text-cyan-300">
                <span className="text-slate-500">// Add to Claude Desktop or Cursor mcp.json:</span>{'\n'}
                &#123;{'\n'}
                {'  '}<span className="text-pink-400">"mcpServers"</span>: &#123;{'\n'}
                {'    '}<span className="text-pink-400">"agentlens"</span>: &#123;{'\n'}
                {'      '}<span className="text-pink-400">"command"</span>: <span className="text-emerald-300">"python"</span>,{'\n'}
                {'      '}<span className="text-pink-400">"args"</span>: [<span className="text-emerald-300">"-m"</span>, <span className="text-emerald-300">"app.mcp.server"</span>],{'\n'}
                {'      '}<span className="text-pink-400">"env"</span>: &#123;{'\n'}
                {'        '}<span className="text-pink-400">"AGENTLENS_API_KEY"</span>: <span className="text-emerald-300">"al_live_your_project_key_here"</span>{'\n'}
                {'      '}&#125;{'\n'}
                {'    '}&#125;{'\n'}
                {'  '}&#125;{'\n'}
                &#125;
              </pre>
            )}
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------------- */}
      {/* 6. Cloud Native Architecture Overview */}
      {/* ----------------------------------------------------------------------- */}
      <section id="architecture" className="py-16 px-6 max-w-5xl mx-auto w-full">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
            Cloud-Native Architecture
          </h2>
          <p className="text-sm text-slate-400 max-w-xl mx-auto">
            Zero heavy local containers. Powered by production-grade cloud services.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800">
            <div className="text-3xl mb-3">🐘</div>
            <h4 className="text-base font-bold text-white mb-1">Neon PostgreSQL</h4>
            <p className="text-xs text-slate-400">
              Serverless Postgres with native <code className="text-emerald-400">pgvector</code> HNSW indexing for instant semantic search.
            </p>
          </div>
          <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800">
            <div className="text-3xl mb-3">⚡</div>
            <h4 className="text-base font-bold text-white mb-1">Redis Cloud</h4>
            <p className="text-xs text-slate-400">
              High-throughput Pub/Sub with TLS and multi-instance channel broadcasting with local failover.
            </p>
          </div>
          <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800">
            <div className="text-3xl mb-3">🧠</div>
            <h4 className="text-base font-bold text-white mb-1">Groq & Gemini</h4>
            <p className="text-xs text-slate-400">
              Ultra-fast Llama 3.3 70B inference for root-cause diagnosis and Gemini embeddings for failure memory.
            </p>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------------- */}
      {/* 7. Bottom Call-To-Action Banner */}
      {/* ----------------------------------------------------------------------- */}
      <section className="py-16 px-6 max-w-5xl mx-auto w-full text-center">
        <div className="p-10 rounded-3xl bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-cyan-900/30 border border-purple-500/30 backdrop-blur-xl relative overflow-hidden">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-4">
            Ready to Debug Your Autonomous Agents?
          </h2>
          <p className="text-sm text-slate-300 max-w-xl mx-auto mb-8">
            Create your organization account, generate your project API key, and start streaming live execution traces immediately.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={onRegister}
              className="px-8 py-3.5 rounded-xl font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-xl shadow-purple-900/40 transition transform hover:-translate-y-0.5"
            >
              Get Started for Free
            </button>
            <button
              onClick={onLogin}
              className="px-8 py-3.5 rounded-xl font-medium text-slate-300 hover:text-white bg-slate-900/80 hover:bg-slate-800 border border-slate-700 transition"
            >
              Sign In to Dashboard
            </button>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------------- */}
      {/* 8. Footer */}
      {/* ----------------------------------------------------------------------- */}
      <footer className="mt-auto border-t border-slate-900 bg-slate-950 py-8 px-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-tr from-purple-600 to-cyan-400 flex items-center justify-center text-white font-bold text-xs">
              AL
            </div>
            <span className="font-semibold text-slate-400">AgentLens</span>
            <span>— AI Agent Observability & Root-Cause Detection</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="hover:text-slate-300 transition">Features</a>
            <a href="#quickstart" className="hover:text-slate-300 transition">Quickstart</a>
            <button onClick={onLogin} className="hover:text-slate-300 transition">Sign In</button>
            <button onClick={onRegister} className="hover:text-slate-300 transition">Register</button>
          </div>
        </div>
      </footer>
    </div>
  );
}
