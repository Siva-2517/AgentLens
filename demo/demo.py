#!/usr/bin/env python
"""Simple demo script to test the customer support agent."""

import asyncio
import sys
from pathlib import Path

# Ensure project root is at front of sys.path and demo directory does not shadow package
demo_dir = str(Path(__file__).resolve().parent)
root_dir = str(Path(__file__).resolve().parent.parent)
while demo_dir in sys.path:
    sys.path.remove(demo_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure console supports UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

# Load demo/.env strictly
demo_env = Path(__file__).resolve().parent / ".env"
load_dotenv(demo_env)

from demo.agent.runner import DemoAgentRunner


async def main():
    """Run demo agent with sample queries."""
    print("=" * 60)
    print("AGENTLENS DEMO AGENT - Customer Support")
    print("=" * 60)
    print()

    # Initialize runner from environment variables
    runner = DemoAgentRunner()

    # Example queries
    examples = [
        "Where is my order ORD-1001?",
        "Check the payment status for order ORD-1002",
        "My payment succeeded but my order hasn't arrived yet",
        "Create a support ticket for my missing order",
    ]

    for i, query in enumerate(examples, 1):
        print(f"\n[User Query {i}]: {query}")
        print("-" * 60)

        result = await runner.run_user_query(query, trace_name=f"Query {i}")

        if result.get("success"):
            print(f"[Agent Response]: {result.get('response', 'No response')}")
            print(f"[Trace ID]: {result.get('trace_id', 'None')}")
        else:
            print(f"[Error]: {result.get('error', 'Unknown error')}")

        # Small delay between queries
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)

    # Close runner
    runner.close()


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())