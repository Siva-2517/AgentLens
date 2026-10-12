"""Embedding provider abstraction for historical failure search (Phase 15)."""

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract interface for generating vector embeddings."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the embedding model identifier."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate a normalized embedding vector for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embedding vectors for a batch of texts."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, fast mock embedding provider for testing and offline environments.
    
    Generates deterministic, L2-normalized 768-dimensional vectors based on word-hash
    and full-text hash projections. Texts with overlapping vocabulary produce realistic,
    proportional cosine similarity without calling external APIs.
    """

    def __init__(self, dimension: int = 768, model_name: str = "mock-embedding-v1"):
        self._dim = dimension
        self._model = model_name

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> List[float]:
        return self._generate_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]

    def _generate_vector(self, text: str) -> List[float]:
        clean_text = (text or "").lower().strip()
        vec = [0.0] * self._dim

        words = clean_text.split()
        for w in words:
            h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            vec[idx] += 1.0 + (h % 5) * 0.1

        # Base noise from text hash for unigram uniqueness
        full_h = int(hashlib.sha256(clean_text.encode("utf-8")).hexdigest(), 16)
        for k in range(min(self._dim, 32)):
            vec[(full_h + k) % self._dim] += 0.05

        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [round(x / norm, 6) for x in vec]


def is_mock_allowed() -> bool:
    """Check if mock provider fallback is permitted based on environment and config."""
    env = (getattr(settings, "environment", "development") or "development").strip().lower()
    is_prod = env in ("production", "prod")
    if is_prod and not getattr(settings, "allow_mock_providers", False):
        return False
    return True


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embedding provider using text-embedding-004."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        dimension: int = 768,
    ):
        self._api_key = api_key or settings.gemini_api_key
        self._model = model_name or settings.embedding_model or "models/text-embedding-004"
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        from app.services.metrics import metrics_collector
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            embeddings = GoogleGenerativeAIEmbeddings(
                google_api_key=self._api_key,
                model=self._model,
            )
            res = await asyncio.wait_for(embeddings.aembed_documents(texts), timeout=15.0)
            metrics_collector.record_llm_call(provider="gemini_embeddings", success=True)
            return res
        except Exception as e:
            metrics_collector.record_llm_call(provider="gemini_embeddings", success=False)
            if not is_mock_allowed():
                logger.error(f"Gemini embedding call failed in production: {type(e).__name__}. Mock fallback is prohibited.")
                raise RuntimeError(
                    f"Embedding provider 'gemini' failed and mock fallback is disabled in production: {type(e).__name__}"
                ) from e
            metrics_collector.record_mock_fallback(provider="gemini_embeddings")
            logger.warning(
                f"Gemini embedding call failed: {e}. Falling back to deterministic MockEmbeddingProvider."
            )
            mock = MockEmbeddingProvider(dimension=self._dimension)
            return await mock.embed_batch(texts)


def get_embedding_provider(
    provider_name: Optional[str] = None,
) -> EmbeddingProvider:
    """Factory to get the configured embedding provider with fail-closed production semantics."""
    from app.services.metrics import metrics_collector

    name = (provider_name or settings.embedding_provider or "mock").lower()

    if not is_mock_allowed() and name == "mock":
        raise RuntimeError("Deterministic mock embedding provider is explicitly prohibited in production.")

    gemini_valid = bool(settings.gemini_api_key and not settings.gemini_api_key.startswith("your_"))

    if name == "gemini":
        if not gemini_valid:
            if not is_mock_allowed():
                raise RuntimeError("Embedding provider 'gemini' configured in production but GEMINI_API_KEY is missing or invalid.")
            logger.warning("Gemini API key not configured. Falling back to mock embedding provider in development.")
            metrics_collector.record_mock_fallback(provider="gemini_embedding_init")
            return MockEmbeddingProvider(dimension=settings.embedding_dimension)
        try:
            return GeminiEmbeddingProvider()
        except Exception as e:
            if not is_mock_allowed():
                raise RuntimeError(f"Failed to initialize Gemini embedding provider in production: {e}") from e
            logger.warning(
                f"Failed to initialize Gemini embedding provider: {e}. Falling back to mock."
            )
            metrics_collector.record_mock_fallback(provider="gemini_embedding_init")
            return MockEmbeddingProvider(dimension=settings.embedding_dimension)
    elif name == "mock":
        return MockEmbeddingProvider(dimension=settings.embedding_dimension)

    if not is_mock_allowed():
        raise RuntimeError(f"Unknown or unconfigured embedding provider '{name}' in production.")

    logger.info(
        f"Embedding provider '{name}' requested but no valid API key configured. Using MockEmbeddingProvider."
    )
    metrics_collector.record_mock_fallback(provider=name)
    return MockEmbeddingProvider(dimension=settings.embedding_dimension)
