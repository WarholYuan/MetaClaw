"""Tests for agent/memory/storage.py — MemoryStorage with SQLite + FTS5"""

import pytest
import json
import tempfile
from pathlib import Path

from agent.memory.storage import MemoryStorage, MemoryChunk, SearchResult


@pytest.fixture
def storage():
    """Create a MemoryStorage backed by a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_memory.db"
        store = MemoryStorage(db_path)
        yield store
        store.close()


@pytest.fixture
def sample_chunk():
    """A reusable MemoryChunk for tests."""
    return MemoryChunk(
        id="test-1",
        user_id="user-1",
        scope="user",
        source="memory",
        path="/mem/test.md",
        start_line=1,
        end_line=10,
        text="Hello world, this is a Python AI agent",
        embedding=None,
        hash="abc123",
    )


class TestMemoryStorageInit:
    """Database initialization."""

    def test_init_creates_db_file(self, storage):
        assert storage.db_path.exists()
        assert storage.conn is not None

    def test_chunks_table_exists(self, storage):
        tables = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
        ).fetchall()
        assert len(tables) == 1

    def test_files_table_exists(self, storage):
        tables = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
        ).fetchall()
        assert len(tables) == 1

    def test_fts5_triggers_when_available(self, storage):
        """If FTS5 is available, chunks_fts table exists."""
        if storage.fts5_available:
            tables = storage.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
            ).fetchall()
            assert len(tables) == 1


class TestMemoryStorageSaveGet:
    """save_chunk + get_chunk."""

    def test_save_and_get(self, storage, sample_chunk):
        storage.save_chunk(sample_chunk)
        result = storage.get_chunk("test-1")
        assert result is not None
        assert result.id == "test-1"
        assert result.text == "Hello world, this is a Python AI agent"
        assert result.scope == "user"
        assert result.user_id == "user-1"

    def test_get_nonexistent(self, storage):
        assert storage.get_chunk("no-such-id") is None

    def test_save_upserts(self, storage, sample_chunk):
        storage.save_chunk(sample_chunk)
        sample_chunk.text = "Updated text"
        storage.save_chunk(sample_chunk)
        result = storage.get_chunk("test-1")
        assert result.text == "Updated text"

    def test_save_batch(self, storage):
        chunks = [
            MemoryChunk(
                id=f"batch-{i}", user_id="u1", scope="shared",
                source="memory", path=f"/b/{i}.md",
                start_line=1, end_line=1, text=f"batch text {i}",
                embedding=None, hash=f"h{i}",
            )
            for i in range(5)
        ]
        storage.save_chunks_batch(chunks)
        for i in range(5):
            assert storage.get_chunk(f"batch-{i}") is not None

    def test_save_with_embedding(self, storage):
        embedding = [0.1, 0.2, 0.3]
        chunk = MemoryChunk(
            id="emb-1", user_id=None, scope="shared",
            source="memory", path="/e.md",
            start_line=1, end_line=1, text="embedding test",
            embedding=embedding, hash="eh1",
        )
        storage.save_chunk(chunk)
        result = storage.get_chunk("emb-1")
        assert result.embedding == embedding


class TestMemoryStorageDelete:
    """delete_by_path."""

    def test_delete_by_path(self, storage, sample_chunk):
        storage.save_chunk(sample_chunk)
        storage.delete_by_path("/mem/test.md")
        assert storage.get_chunk("test-1") is None

    def test_delete_by_path_nonexistent(self, storage):
        # Should not raise
        storage.delete_by_path("/nonexistent.md")


class TestMemoryStorageStats:
    """get_stats."""

    def test_stats_empty(self, storage):
        stats = storage.get_stats()
        assert isinstance(stats, dict)

    def test_stats_with_data(self, storage, sample_chunk):
        storage.save_chunk(sample_chunk)
        stats = storage.get_stats()
        assert isinstance(stats, dict)
        assert "chunks" in stats
        assert stats["chunks"] >= 1

class TestMemoryStorageKeywordSearch:
    """search_keyword."""

    def test_search_returns_results(self, storage):
        storage.save_chunk(MemoryChunk(
            id="k-1", user_id=None, scope="shared",
            source="memory", path="/k.md",
            start_line=1, end_line=1, text="Python is great for AI agents",
            embedding=None, hash="k1",
        ))
        storage.save_chunk(MemoryChunk(
            id="k-2", user_id=None, scope="shared",
            source="memory", path="/k2.md",
            start_line=1, end_line=1, text="Java for enterprise",
            embedding=None, hash="k2",
        ))
        results = storage.search_keyword("Python")
        # FTS5 may not be available; check graceful result
        assert isinstance(results, list)
        if results:
            assert any("Python" in r.snippet for r in results)

    def test_search_no_results(self, storage):
        results = storage.search_keyword("xyzzy_nonexistent_12345")
        assert results == []


class TestMemoryStorageVectorSearch:
    """search_vector."""

    def test_vector_search_with_embedding(self, storage):
        embedding = [0.1] * 384
        storage.save_chunk(MemoryChunk(
            id="cos-1", user_id=None, scope="shared",
            source="memory", path="/cos.md",
            start_line=1, end_line=1, text="AI agent memory",
            embedding=embedding, hash="cos1",
        ))
        results = storage.search_vector(embedding, scopes=["shared"], limit=5)
        assert len(results) >= 1
        assert results[0].path == "/cos.md"

    def test_vector_search_no_embeddings(self, storage):
        storage.save_chunk(MemoryChunk(
            id="no-emb", user_id=None, scope="shared",
            source="memory", path="/n.md",
            start_line=1, end_line=1, text="no embedding",
            embedding=None, hash="ne1",
        ))
        results = storage.search_vector([0.1] * 384, scopes=["shared"])
        assert results == []


class TestMemoryStorageComputeHash:
    """Static compute_hash."""

    def test_compute_hash_deterministic(self):
        h1 = MemoryStorage.compute_hash("hello")
        h2 = MemoryStorage.compute_hash("hello")
        assert h1 == h2

    def test_compute_hash_different_content(self):
        h1 = MemoryStorage.compute_hash("hello")
        h2 = MemoryStorage.compute_hash("world")
        assert h1 != h2

    def test_compute_hash_non_empty(self):
        h = MemoryStorage.compute_hash("test")
        assert len(h) > 0
