#!/usr/bin/env python
"""Quick test of demo agent functionality."""

import asyncio
import sys
import os

# Add project root to path
demo_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(demo_dir)
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

async def test_tools():
    """Test that tools work correctly."""
    print("Testing demo agent tools...")

    from demo.agent.tools import get_customer, get_order, check_payment, create_support_ticket

    # Test customer tool
    customer = get_customer("CUST-001")
    assert customer is not None
    assert customer["customer_id"] == "CUST-001"
    assert customer["name"] == "John Doe"
    print("✓ get_customer works")

    # Test order tool
    order = get_order("ORD-1001")
    assert order is not None
    assert order["order_id"] == "ORD-1001"
    print("✓ get_order works")

    # Test payment tool
    payment = check_payment("ORD-1001")
    assert payment is not None
    assert payment["payment_status"] == "paid"
    print("✓ check_payment works")

    # Test ticket creation
    ticket = create_support_ticket("CUST-001", "Test issue")
    assert ticket is not None
    assert ticket["customer_id"] == "CUST-001"
    assert ticket["status"] == "pending"
    print("✓ create_support_ticket works")

    return True

async def test_runner():
    """Test demo agent runner."""
    print("\nTesting demo agent runner...")

    from demo.agent.runner import DemoAgentRunner

    # Test runner initialization
    runner = DemoAgentRunner(
        api_url="http://localhost:8000",
        api_key="test_api_key_123",
        use_agentlens=False  # Disable Lens for testing
    )

    print("✓ Runner initialized")

    # Test a simple query
    result = await runner.run_user_query("Where is my order ORD-1001?")

    assert "success" in result
    assert isinstance(result["success"], bool)
    assert "response" in result
    assert isinstance(result["response"], str)

    print(f"✓ Query executed: success={result['success']}")
    print(f"  Response preview: {result['response'][:80]}...")

    runner.close()
    print("✓ Runner closed")

    return True

async def test_graph():
    """Test LangGraph compilation."""
    print("\nTesting LangGraph construction...")

    from demo.agent.graph import customer_support_agent

    # Check that graph is compiled
    assert hasattr(customer_support_agent, "invoke")
    assert hasattr(customer_support_agent, "ainvoke")
    print("✓ Graph is compiled and ready")

    return True

async def main():
    """Run all quick tests."""
    print("=" * 50)
    print("AGENTLENS DEMO AGENT - QUICK TEST")
    print("=" * 50)

    try:
        await test_tools()
        await test_runner()
        await test_graph()

        print("\n" + "=" * 50)
        print("✅ ALL QUICK TESTS PASSED")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)