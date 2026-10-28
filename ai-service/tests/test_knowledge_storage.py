"""
Tests for Phase 9.4 — Vector storage (unit tests with mocked database).

No real PostgreSQL connection is made.  All database interactions use
mock/fake session objects.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.chunker import FileChunk
from app.knowledge.storage import (
    WRITE_BATCH_SIZE,
    _validate_embeddings,
    delete_chunks_for_file,
    delete_chunks_for_paths,
    get_indexed_file_paths,
    get_indexed_fingerprints,
    upsert_chunks,
)
from app.models.project_knowledge import EMBEDDING_DIMENSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    file_path: str = "src/main.py",
    content: str = "def foo(): pass",
    chunk_index: int = 0,
    line_start: int = 1,
    line_end: int = 1,
    fingerprint: str = "aabbcc",
) -> FileChunk:
    return FileChunk(
        file_path=file_path,
        content=content,
        chunk_index=chunk_index,
        line_start=line_start,
        line_end=line_end,
        source_fingerprint=fingerprint,
    )


def _make_embedding(dim: int = EMBEDDING_DIMENSION) -> list[float]:
    return [0.1] * dim


def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# _validate_embeddings
# ---------------------------------------------------------------------------


class TestValidateEmbeddings:
    def test_valid_embeddings_pass(self):
        chunks = [_make_chunk()]
        embs = [_make_embedding()]
        # Should not raise
        _validate_embeddings(chunks, embs)

    def test_count_mismatch_raises(self):
        chunks = [_make_chunk(), _make_chunk(chunk_index=1)]
        embs = [_make_embedding()]  # only 1 for 2 chunks
        with pytest.raises(ValueError, match="mismatch"):
            _validate_embeddings(chunks, embs)

    def test_wrong_dimension_raises(self):
        chunks = [_make_chunk()]
        embs = [[0.1] * (EMBEDDING_DIMENSION - 1)]
        with pytest.raises(ValueError, match="dimension"):
            _validate_embeddings(chunks, embs)

    def test_nan_raises(self):
        import math

        chunks = [_make_chunk()]
        emb = _make_embedding()
        emb[0] = math.nan
        with pytest.raises(ValueError, match="non-finite"):
            _validate_embeddings(chunks, [emb])

    def test_inf_raises(self):
        import math

        chunks = [_make_chunk()]
        emb = _make_embedding()
        emb[0] = math.inf
        with pytest.raises(ValueError, match="non-finite"):
            _validate_embeddings(chunks, [emb])

    def test_empty_inputs_pass(self):
        # Empty lists — zero chunks, zero embeddings: valid
        _validate_embeddings([], [])


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------


class TestUpsertChunks:
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero(self):
        session = _make_mock_session()
        n = await upsert_chunks(session, [], [])
        assert n == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_embeddings_raises_before_db(self):
        session = _make_mock_session()
        chunks = [_make_chunk()]
        bad_embs: list[list[float]] = []  # count mismatch
        with pytest.raises(ValueError):
            await upsert_chunks(session, chunks, bad_embs)
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_executes_and_commits(self):
        session = _make_mock_session()
        chunks = [_make_chunk()]
        embs = [_make_embedding()]
        with patch("app.knowledge.storage.pg_insert") as mock_insert:
            mock_stmt = MagicMock()
            mock_stmt.on_conflict_do_update.return_value = mock_stmt
            mock_insert.return_value = mock_stmt
            n = await upsert_chunks(session, chunks, embs)
        assert n == 1
        session.execute.assert_called()
        session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_batches(self):
        """When chunks exceed WRITE_BATCH_SIZE, multiple execute calls occur."""
        n_chunks = WRITE_BATCH_SIZE + 5
        chunks = [_make_chunk(chunk_index=i, fingerprint=f"fp{i}") for i in range(n_chunks)]
        embs = [_make_embedding() for _ in range(n_chunks)]
        session = _make_mock_session()
        with patch("app.knowledge.storage.pg_insert") as mock_insert:
            mock_stmt = MagicMock()
            mock_stmt.on_conflict_do_update.return_value = mock_stmt
            mock_insert.return_value = mock_stmt
            n = await upsert_chunks(session, chunks, embs)
        assert n == n_chunks
        assert session.execute.call_count == 2  # ceil(55/50) = 2


# ---------------------------------------------------------------------------
# delete_chunks_for_file
# ---------------------------------------------------------------------------


class TestDeleteChunksForFile:
    @pytest.mark.asyncio
    async def test_deletes_and_commits(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.rowcount = 3
        session.execute = AsyncMock(return_value=result_mock)

        with patch("app.knowledge.storage.delete") as mock_delete:
            mock_where = MagicMock()
            mock_delete.return_value.where.return_value = mock_where
            n = await delete_chunks_for_file(session, "src/main.py")

        assert n == 3
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# delete_chunks_for_paths
# ---------------------------------------------------------------------------


class TestDeleteChunksForPaths:
    @pytest.mark.asyncio
    async def test_empty_paths_returns_zero(self):
        session = _make_mock_session()
        n = await delete_chunks_for_paths(session, [])
        assert n == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_multiple(self):
        session = _make_mock_session()
        result_mock = MagicMock()
        result_mock.rowcount = 7
        session.execute = AsyncMock(return_value=result_mock)

        with patch("app.knowledge.storage.delete") as mock_delete:
            mock_where = MagicMock()
            mock_delete.return_value.where.return_value = mock_where
            n = await delete_chunks_for_paths(session, ["a.py", "b.py", "c.py"])

        assert n == 7
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_indexed_fingerprints
# ---------------------------------------------------------------------------


class TestGetIndexedFingerprints:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_rows(self):
        session = _make_mock_session()
        # Simulate empty result set
        session.execute = AsyncMock(return_value=iter([]))
        result = await get_indexed_fingerprints(session)
        assert result == {}

    @pytest.mark.asyncio
    async def test_builds_nested_dict(self):
        session = _make_mock_session()
        rows = [
            ("src/a.py", 0, "fp_a0"),
            ("src/a.py", 1, "fp_a1"),
            ("src/b.py", 0, "fp_b0"),
        ]
        session.execute = AsyncMock(return_value=iter(rows))
        result = await get_indexed_fingerprints(session)
        assert result == {
            "src/a.py": {0: "fp_a0", 1: "fp_a1"},
            "src/b.py": {0: "fp_b0"},
        }


# ---------------------------------------------------------------------------
# get_indexed_file_paths
# ---------------------------------------------------------------------------


class TestGetIndexedFilePaths:
    @pytest.mark.asyncio
    async def test_returns_set_of_paths(self):
        session = _make_mock_session()
        rows = [("src/a.py",), ("docs/README.md",)]
        session.execute = AsyncMock(return_value=iter(rows))
        result = await get_indexed_file_paths(session)
        assert result == {"src/a.py", "docs/README.md"}

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty_set(self):
        session = _make_mock_session()
        session.execute = AsyncMock(return_value=iter([]))
        result = await get_indexed_file_paths(session)
        assert result == set()
