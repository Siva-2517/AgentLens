import { useState, useEffect } from 'react'

function App() {
  const [apiStatus, setApiStatus] = useState<string>('checking...')

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(res => res.json())
      .then(data => setApiStatus(data.status))
      .catch(() => setApiStatus('offline'))
  }, [])

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8">
          <h1 className="text-4xl font-bold mb-2">AgentLens</h1>
          <p className="text-gray-400">
            AI-powered observability for AI agents
          </p>
        </header>

        <main>
          <div className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-2xl font-semibold mb-4">System Status</h2>
            <div className="flex items-center gap-2">
              <span className="text-gray-400">API:</span>
              <span
                className={`font-mono ${
                  apiStatus === 'healthy'
                    ? 'text-green-400'
                    : apiStatus === 'offline'
                    ? 'text-red-400'
                    : 'text-yellow-400'
                }`}
              >
                {apiStatus}
              </span>
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">Welcome</h2>
            <p className="text-gray-300">
              AgentLens is being built incrementally. This is Phase 1: Project
              Foundation.
            </p>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
