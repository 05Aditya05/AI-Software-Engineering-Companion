"""
Vector storage for project knowledge chunks (Phase 9.4).

Persists FileChunk objects alongside their embeddings into the
``project_knowledge`` PostgreSQL table using pgvector.

Design:
  - Uses a composite unique constraint on (file_path, chunk_index) to
    enable safe upsert: existing chunks are updated in-place rather
    than duplicated.
  - All writes use explicit SQLAlchemy transactions.  A failure rolls
    back the entire batch so partial-ingestion does not corrupt data.
  - Embedding dimension is validated against EMBEDDING_DIMENSION
    before any write operation.
  - No table truncation or DROP is performed.
  - Database credentials are never logged.

Batch sizes are bounded to avoid memory spikes on large projects.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.chunker import FileChunk
from app.models.project_knowledge import EMBEDDING_DIMENSION, ProjectKnowledge

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Maximum number of chunks written per database transaction.
WRITE_BATCH_SIZE: int = 50


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


async def ensure_unique_constraint(session: AsyncSession) -> None:
    """
    Ensure the composite unique constraint (file_path, chunk_index) exists.

    This is idempotent — safe to call on every startup.  The constraint
    is required for upsert semantics.  It is NOT created at model-
    definition time so that the existing table is not broken by a
    re-import.

    Raises:
        Exception: propagated if the DDL itself fails.
    """
    await session.execute(
        text(
            "ALTER TABLE project_knowledge "
            "ADD CONSTRAINT IF NOT EXISTS uq_pk_file_chunk "
            "UNIQUE (file_path, chunk_index)"
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_embeddings(
    chunks: list[FileChunk],
    embeddings: list[list[float]],
) -> None:
    """
    Raise ValueError if the embedding list does not match the chunks.

    Checks:
      - Count matches.
      - Each embedding has the correct dimension.
      - No NaN or Inf values.
    """
    if len(embeddings) != len(chunks):
        raise ValueError(
            f"Embedding count mismatch: {len(embeddings)} embeddings "
            f"for {len(chunks)} chunks."
        )
    import math

    for idx, emb in enumerate(embeddings):
        if len(emb) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding {idx} has dimension {len(emb)}, "
                f"expected {EMBEDDING_DIMENSION}."
            )
        for val in emb:
            if not math.isfinite(val):
                raise ValueError(
                    f"Embedding {idx} contains non-finite value {val!r}."
                )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


async def upsert_chunks(
    session: AsyncSession,
    chunks: list[FileChunk],
    embeddings: list[list[float]],
) -> int:
    """
    Persist chunks and their embeddings via upsert.

    On conflict of (file_path, chunk_index) the existing row is
    updated with the new content, fingerprint, line numbers, and
    embedding.  Unchanged rows are rewritten only when content or
    embedding changes — this is acceptable because pgvector upsert
    always overwrites on conflict.

    Args:
        session:    Active async SQLAlchemy session.
        chunks:     FileChunk list to persist.
        embeddings: One float vector per chunk (same order).

    Returns:
        Number of rows upserted.

    Raises:
        ValueError: If embeddings are invalid.
        SQLAlchemyError: Propagated on database error (caller should
            roll back the session).
    """
    if not chunks:
        return 0

    _validate_embeddings(chunks, embeddings)

    total = 0
    for start in range(0, len(chunks), WRITE_BATCH_SIZE):
        batch_chunks = chunks[start : start + WRITE_BATCH_SIZE]
        batch_embeddings = embeddings[start : start + WRITE_BATCH_SIZE]

        rows = [
            {
                "file_path": c.file_path,
                "content": c.content,
                "chunk_index": c.chunk_index,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "source_fingerprint": c.source_fingerprint,
                "metadata_": {
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "chunk_index": c.chunk_index,
                },
                "embedding": emb,
            }
            for c, emb in zip(batch_chunks, batch_embeddings, strict=True)
        ]

        stmt = pg_insert(ProjectKnowledge).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_pk_file_chunk",
            set_={
                "content": stmt.excluded.content,
                "source_fingerprint": stmt.excluded.source_fingerprint,
                "line_start": stmt.excluded.line_start,
                "line_end": stmt.excluded.line_end,
                "metadata_": stmt.excluded.metadata_,
                "embedding": stmt.excluded.embedding,
            },
        )
        await session.execute(stmt)
        await session.commit()
        total += len(batch_chunks)

    return total


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


async def delete_chunks_for_file(
    session: AsyncSession,
    file_path: str,
) -> int:
    """
    Delete all indexed chunks for a given relative file path.

    Args:
        session:   Active async SQLAlchemy session.
        file_path: Normalized POSIX relative path.

    Returns:
        Number of rows deleted.
    """
    result = await session.execute(
        delete(ProjectKnowledge).where(
            ProjectKnowledge.file_path == file_path
        )
    )
    await session.commit()
    deleted: int = result.rowcount  # type: ignore[assignment]
    logger.info("Deleted %d chunks for %s", deleted, file_path)
    return deleted


async def delete_chunks_for_paths(
    session: AsyncSession,
    file_paths: list[str],
) -> int:
    """
    Delete all indexed chunks for a list of relative file paths.

    Uses a single DELETE … WHERE file_path IN (…) statement.

    Args:
        session:    Active async SQLAlchemy session.
        file_paths: Normalized POSIX relative paths to remove.

    Returns:
        Total number of rows deleted.
    """
    if not file_paths:
        return 0
    result = await session.execute(
        delete(ProjectKnowledge).where(
            ProjectKnowledge.file_path.in_(file_paths)
        )
    )
    await session.commit()
    deleted: int = result.rowcount  # type: ignore[assignment]
    logger.info("Deleted %d chunks for %d files", deleted, len(file_paths))
    return deleted


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def get_indexed_fingerprints(
    session: AsyncSession,
) -> dict[str, dict[int, str]]:
    """
    Return stored fingerprints keyed by (file_path → chunk_index → fingerprint).

    Used by the incremental sync engine to detect unchanged chunks.

    Returns:
        Nested dict: {file_path: {chunk_index: fingerprint}}.
    """
    rows = await session.execute(
        select(
            ProjectKnowledge.file_path,
            ProjectKnowledge.chunk_index,
            ProjectKnowledge.source_fingerprint,
        )
    )
    result: dict[str, dict[int, str]] = {}
    for file_path, chunk_index, fingerprint in rows:
        if file_path not in result:
            result[file_path] = {}
        result[file_path][chunk_index] = fingerprint or ""
    return result


async def get_indexed_file_paths(session: AsyncSession) -> set[str]:
    """
    Return the set of all file paths currently indexed in the database.

    Args:
        session: Active async SQLAlchemy session.

    Returns:
        Set of normalized POSIX relative path strings.
    """
    rows = await session.execute(
        select(ProjectKnowledge.file_path).distinct()
    )
    return {row[0] for row in rows}
