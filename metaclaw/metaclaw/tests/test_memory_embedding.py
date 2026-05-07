"""
Tests for memory embedding module: EmbeddingCache, factory, provider.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.memory.embedding import (
    EmbeddingProvider,
    EmbeddingCache,
    create_embedding_provider,
)


# ─────────────────── EmbeddingCache tests ───────────────────

@pytest.fixture
def cache():
    """Fresh EmbeddingCache."""
    return EmbeddingCache()


def test_cache_put_and_get(cache):
    """Cache stores and retrieves embeddings."""
    emb = [0.1, 0.2, 0.3]
    cache.put("hello world", "openai", "text-embedding-3-small", emb)
    result = cache.get("hello world", "openai", "text-embedding-3-small")
    assert result == emb


def test_cache_miss(cache):
    """Cache returns None on miss."""
    result = cache.get("unknown", "openai", "text-embedding-3-small")
    assert result is None


def test_cache_different_text(cache):
    """Different text produces different cache entries."""
    emb1 = [0.1, 0.2]
    emb2 = [0.3, 0.4]
    cache.put("text A", "openai", "small", emb1)
    cache.put("text B", "openai", "small", emb2)

    assert cache.get("text A", "openai", "small") == emb1
    assert cache.get("text B", "openai", "small") == emb2


def test_cache_different_providers(cache):
    """Same text with different providers yields separate entries."""
    emb = [0.1, 0.2]
    cache.put("hello", "openai", "small", emb)

    # Different provider should miss
    result = cache.get("hello", "legacy_provider", "small")
    assert result is None


def test_cache_different_models(cache):
    """Same text with different models yields separate entries."""
    emb1 = [0.1]
    emb2 = [0.2]
    cache.put("hello", "openai", "text-embedding-3-small", emb1)
    cache.put("hello", "openai", "text-embedding-3-large", emb2)

    assert cache.get("hello", "openai", "text-embedding-3-small") == emb1
    assert cache.get("hello", "openai", "text-embedding-3-large") == emb2


def test_cache_clear(cache):
    """Clear removes all entries."""
    emb = [0.1, 0.2]
    for i in range(10):
        cache.put(f"text{i}", "openai", "small", emb)

    cache.clear()
    for i in range(10):
        assert cache.get(f"text{i}", "openai", "small") is None


def test_cache_overwrite(cache):
    """Caching the same key twice overwrites."""
    emb1 = [1.0, 2.0]
    emb2 = [3.0, 4.0]
    cache.put("hello", "openai", "small", emb1)
    cache.put("hello", "openai", "small", emb2)
    result = cache.get("hello", "openai", "small")
    assert result == emb2


def test_cache_key_stability():
    """Cache key computation is deterministic."""
    k1 = EmbeddingCache._compute_key("hello", "openai", "text-embedding-3-small")
    k2 = EmbeddingCache._compute_key("hello", "openai", "text-embedding-3-small")
    assert k1 == k2
    assert len(k1) == 32  # MD5 hex digest


def test_cache_key_unique():
    """Different inputs produce different keys."""
    k1 = EmbeddingCache._compute_key("a", "openai", "small")
    k2 = EmbeddingCache._compute_key("b", "openai", "small")
    k3 = EmbeddingCache._compute_key("a", "legacy_provider", "small")
    assert k1 != k2
    assert k1 != k3


# ─────────────────── Factory function tests ───────────────────

def test_factory_openai_requires_api_key():
    """Factory raises ValueError when api_key is missing."""
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        create_embedding_provider(provider="unsupported")

    # openai with missing key raises ValueError
    with pytest.raises(ValueError, match="API key"):
        create_embedding_provider(
            provider="openai",
            api_key="YOUR API KEY",  # Placeholder value triggers validation
        )


def test_factory_openai_empty_key():
    """Factory rejects empty API key."""
    with pytest.raises(ValueError, match="API key"):
        create_embedding_provider(provider="openai", api_key="")


def test_factory_legacy_provider_rejected():
    """Factory rejects unsupported legacy providers."""
    with pytest.raises(ValueError, match="Unsupported embedding provider: legacy_provider"):
        create_embedding_provider(provider="legacy_provider", api_key="sk-test")


def test_factory_default_model():
    """Default model is text-embedding-3-small. Validation happens at API call time."""
    provider = create_embedding_provider(provider="openai", api_key="sk-test-key")
    assert provider is not None
    assert provider.model == "text-embedding-3-small"


def test_factory_custom_model():
    """Custom model name is accepted."""
    provider = create_embedding_provider(
        provider="openai",
        model="text-embedding-3-large",
        api_key="sk-test-key",
    )
    assert provider.model == "text-embedding-3-large"


# ─────────────────── Provider dimensions test ───────────────────

def test_openai_provider_dimensions():
    """Provider creates successfully regardless of model name."""
    provider = create_embedding_provider(
        provider="openai",
        model="text-embedding-3-small",
        api_key="sk-test-key",
    )
    assert provider is not None


# ─────────────────── Abstract base class ───────────────────

def test_embedding_provider_is_abstract():
    """Cannot instantiate abstract EmbeddingProvider directly."""
    with pytest.raises(TypeError):
        EmbeddingProvider()  # type: ignore[abstract]
