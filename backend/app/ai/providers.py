"""Phase 2 provider boundaries.

Phase 1 always returns the NotConfigured implementations. No route in this
process calls them, and `AI_ENABLED` stays false. A later phase replaces
`get_embedding_provider` and `get_llm_provider` without changing callers.
"""

from typing import Protocol

from app.ai.errors import NotConfigured


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input string, in the same order."""


class LLMProvider(Protocol):
    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return one completion. The prompt is instructions; document text stays data."""


class NotConfiguredEmbedding:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotConfigured("Embeddings are not configured. AI_ENABLED is false.")


class NotConfiguredLLM:
    def complete(self, prompt: str, *, system: str | None = None) -> str:
        raise NotConfigured("Language model calls are not configured. AI_ENABLED is false.")


def get_embedding_provider() -> EmbeddingProvider:
    """The embedding provider for this process. Phase 1 has none."""
    return NotConfiguredEmbedding()


def get_llm_provider() -> LLMProvider:
    """The language-model provider for this process. Phase 1 has none."""
    return NotConfiguredLLM()
