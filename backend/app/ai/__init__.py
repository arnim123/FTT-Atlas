"""AI provider boundaries. Phase 1 ships interfaces only; AI_ENABLED stays false."""

from app.ai.errors import NotConfigured
from app.ai.providers import (
    EmbeddingProvider,
    LLMProvider,
    get_embedding_provider,
    get_llm_provider,
)

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "NotConfigured",
    "get_embedding_provider",
    "get_llm_provider",
]
