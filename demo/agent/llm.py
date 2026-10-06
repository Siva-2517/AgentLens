"""LLM configuration using LangChain."""

import logging
from typing import Any

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

from agentlens.types import EventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockLLM:
    """Mock LLM for testing when no API key is available."""

    def __init__(self, model: str = "mock"):
        """Initialize mock LLM.

        Args:
            model: Model name (unused in mock).
        """
        self.model = model
        logger.warning(f"Using MOCK LLM: {model}")

    def invoke(self, messages: list) -> dict[str, Any]:
        """Invoke the mock LLM synchronously.

        Args:
            messages: Conversation history.

        Returns:
            Mock response dict.
        """
        user_message = ""
        if messages:
            last = messages[-1]
            user_message = getattr(last, "content", str(last))

        # Parse user request to determine tool selection
        tool_selection = self._parse_user_request(user_message)

        logger.info(f"Mock LLM message: {user_message}")
        logger.info(f"Mock LLM tool selection: {tool_selection}")

        return {
            "content": "",
            "tool_calls": [
                {
                    "name": tool_selection,
                    "args": {}
                    if tool_selection == "check_payment"
                    else {"customer_id": "CUST-001"}
                    if tool_selection == "get_customer"
                    else {"order_id": "ORD-1001"}
                    if tool_selection == "get_order"
                    else {"customer_id": "CUST-001", "issue": user_message},
                }
            ]
        }

    async def ainvoke(self, messages: list) -> dict[str, Any]:
        """Invoke the mock LLM asynchronously."""
        return self.invoke(messages)

    def _parse_user_request(self, request: str) -> str:
        """Simple keyword-based parsing for mock LLM.

        Args:
            request: User's natural language request.

        Returns:
            Tool name string.
        """
        request_lower = request.lower()

        if any(word in request_lower for word in ["order", "tracking", "ship"]):
            return "get_order"
        elif any(word in request_lower for word in ["payment", "card", "paid"]):
            return "check_payment"
        elif any(word in request_lower for word in ["ticket", "support", "problem"]):
            return "create_support_ticket"
        else:
            return "get_customer"


class LangChainLLMWrapper:
    """Wrapper for LangChain LLM that emits AgentLens events."""

    def __init__(
        self,
        model: str,
        provider: str = "groq",
    ):
        """Initialize LangChain LLM wrapper.

        Args:
            model: Model name (e.g., "llama3-70b-8192").
            provider: LLM provider ("groq" or "gemini").

        Raises:
            ValueError: If provider or model is invalid.
        """
        self.model = model
        self.provider = provider

        # Initialize LLM based on provider
        if provider == "groq":
            try:
                if ChatGroq is None:
                    raise ImportError("langchain_groq is not installed")
                from groq import Groq  # noqa: F401

                self.llm = ChatGroq(
                    model=model,
                    temperature=0.0,
                )
                logger.info(f"Groq LLM initialized: {model}")
            except Exception as e:
                logger.warning(f"Could not initialize Groq LLM: {e}")
                logger.warning("Falling back to mock LLM")
                self.llm = MockLLM(model)
        elif provider == "gemini":
            try:
                if ChatGoogleGenerativeAI is None:
                    raise ImportError("langchain_google_genai is not installed")
                self.llm = ChatGoogleGenerativeAI(
                    model=model,
                    temperature=0.0,
                    client_api_key=None,  # Will use env var
                )
                logger.info(f"Gemini LLM initialized: {model}")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini LLM: {e}")
                logger.warning("Falling back to mock LLM")
                self.llm = MockLLM(model)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def invoke(self, messages: list) -> dict[str, Any]:
        """Invoke the LLM synchronously.

        Args:
            messages: Conversation history.

        Returns:
            LLM response dict with tool_calls if applicable.
        """
        try:
            if isinstance(self.llm, MockLLM):
                return self.llm.invoke(messages)

            response = self.llm.invoke(messages)

            tool_calls = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool in response.tool_calls:
                    if isinstance(tool, dict):
                        tool_calls.append(tool)
                    elif hasattr(tool, "function"):
                        tool_calls.append({
                            "name": tool.function.name,
                            "args": tool.function.arguments,
                        })

            return {
                "content": getattr(response, "content", ""),
                "tool_calls": tool_calls,
            }
        except Exception as e:
            logger.error(f"LLM invoke failed: {e}")
            return {
                "content": "",
                "tool_calls": [],
            }

    async def ainvoke(self, messages: list) -> dict[str, Any]:
        """Invoke the LLM.

        Args:
            messages: Conversation history.

        Returns:
            LLM response dict with tool_calls if applicable.
        """
        try:
            if isinstance(self.llm, MockLLM):
                return self.llm.invoke(messages)

            response = await self.llm.ainvoke(messages)

            tool_calls = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool in response.tool_calls:
                    if isinstance(tool, dict):
                        tool_calls.append(tool)
                    elif hasattr(tool, "function"):
                        tool_calls.append({
                            "name": tool.function.name,
                            "args": tool.function.arguments,
                        })

            return {
                "content": getattr(response, "content", ""),
                "tool_calls": tool_calls,
            }
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # Return empty response to allow graceful recovery
            return {
                "content": "",
                "tool_calls": [],
            }


def get_llm(provider: str = "groq", model: str = "llama3-70b-8192") -> LangChainLLMWrapper:
    """Get LLM instance based on provider.

    Args:
        provider: LLM provider ("groq" or "gemini").
        model: Model name.

    Returns:
        LLM wrapper instance.
    """
    return LangChainLLMWrapper(provider=provider, model=model)