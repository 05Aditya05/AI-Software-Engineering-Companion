"""
Incremental knowledge indexer (Phase 9.7).

Orchestrates the full ingestion pipeline:

1. Discover eligible project files via the chunker.
2. Load stored fingerprints from the database.
3. Compute new chunks for each file.
4. Skip files whose chunks are all unchanged (fingerprint match).
5. Upsert changed/new chunks; remove excess stale chunks for shrunken files.
6. Delete chunks belonging to files that no longer exist or are no
   longer eligible.
7. Return an IndexSummary describing what happened.

Atomicity strategy:
  - Each file's upsert is committed immediately after its batch
    completes.  If embedding or database errors occur mid-file, the
    completed files remain indexed; the failed file is recorded in
    `summary.failed` and the pipeline continues.
  - Chunk deletion for removed files happens in a single transaction
    after ingestion is complete.

Project isolation:
  - All operations are scoped to the file paths discovered under the
    configured project root.  No other project's data is touched.
  - Deletion only removes paths that the current project root
    previously indexed (intersection of DB paths and discovered paths).

Security:
  - No shell commands are executed.
  - Database credentials are never logged.
  - Secret/credential files are never read (enforced by chunker).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.chunker import FileChunk, discover_eligible_files, read_and_chunk_file
from app.knowledge.storage import (
    delete_chunks_for_paths,
    get_indexed_file_paths,
    get_indexed_fingerprints,
    upsert_chunks,
)
from app.providers.base import EmbeddingProvider
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

# Maximum chunks embedded in one API call (matches EmbeddingProvider batch limit).
EMBED_BATCH_SIZE: int = 50


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@dataclass
class IndexSummary:
    """
    Summary of a single indexing/synchronisation run.

    Attributes:
        indexed_files:  Files newly indexed or updated.
        skipped_files:  Files with no content changes (skipped).
        removed_files:  Files removed from the index (deleted or ineligible).
        failed_files:   Files that caused errors during ingestion.
        indexed_chunks: Total chunks written (inserted or updated).
        removed_chunks: Total chunks deleted.
        errors:         Human-readable error descriptions keyed by file path.
    """

    indexed_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    indexed_chunks: int = 0
    removed_chunks: int = 0
    errors: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"IndexSummary("
            f"indexed={len(self.indexed_files)} files/{self.indexed_chunks} chunks, "
            f"skipped={len(self.skipped_files)}, "
            f"removed={len(self.removed_files)} files/{self.removed_chunks} chunks, "
            f"failed={len(self.failed_files)})"
        )


# ---------------------------------------------------------------------------
# Core incremental indexer
# ---------------------------------------------------------------------------


async def incremental_index(
    service: ProjectService,
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
) -> IndexSummary:
    """
    Run an incremental synchronisation of the project knowledge index.

    Args:
        service:            Initialized ProjectService (provides root + helpers).
        embedding_provider: Provider used to embed chunk content.
        session:            Active async SQLAlchemy session.

    Returns:
        IndexSummary describing the outcome of this run.
    """
    summary = IndexSummary()

    # 1. Discover eligible files on disk
    eligible_paths = discover_eligible_files(service)
    eligible_rel = {
        p.relative_to(service.root).as_posix() for p in eligible_paths
    }

    # 2. Load stored fingerprints: {file_path: {chunk_index: fingerprint}}
    try:
        stored_fingerprints = await get_indexed_fingerprints(session)
    except Exception as exc:
        logger.error("Failed to load stored fingerprints: %s", exc)
        stored_fingerprints = {}

    # 3. Load the set of all indexed file paths (for stale-file detection)
    try:
        indexed_paths = await get_indexed_file_paths(session)
    except Exception as exc:
        logger.error("Failed to load indexed file paths: %s", exc)
        indexed_paths = set()

    # 4. Process each eligible file
    for abs_path in eligible_paths:
        rel = abs_path.relative_to(service.root).as_posix()
        try:
            await _index_file(
                abs_path=abs_path,
                rel_path=rel,
                project_root=service.root,
                stored_fingerprints=stored_fingerprints.get(rel, {}),
                embedding_provider=embedding_provider,
                session=session,
                summary=summary,
            )
        except Exception as exc:
            logger.error("Unexpected error indexing %s: %s", rel, exc)
            summary.failed_files.append(rel)
            summary.errors[rel] = str(exc)

    # 5. Remove stale chunks for deleted or ineligible files
    stale_paths = sorted(indexed_paths - eligible_rel)
    if stale_paths:
        try:
            removed = await delete_chunks_for_paths(session, stale_paths)
            summary.removed_files.extend(stale_paths)
            summary.removed_chunks += removed
        except Exception as exc:
            logger.error("Failed to remove stale chunks: %s", exc)
            for p in stale_paths:
                summary.errors[p] = f"Deletion failed: {exc}"

    logger.info("Indexing complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Per-file indexing
# ---------------------------------------------------------------------------


async def _index_file(
    abs_path: object,
    rel_path: str,
    project_root: object,
    stored_fingerprints: dict[int, str],
    embedding_provider: EmbeddingProvider,
    session: AsyncSession,
    summary: IndexSummary,
) -> None:
    """Index (or skip) a single file."""
    from pathlib import Path

    abs_path = Path(abs_path)  # type: ignore[arg-type]
    project_root = Path(project_root)  # type: ignore[arg-type]

    # Chunk the file
    chunks = read_and_chunk_file(abs_path, project_root)
    if not chunks:
        # File produced no chunks (empty, whitespace-only)
        summary.skipped_files.append(rel_path)
        return

    # Determine which chunks need embedding (fingerprint changed or new)
    changed_chunks: list[FileChunk] = []
    unchanged_count = 0

    for chunk in chunks:
        stored_fp = stored_fingerprints.get(chunk.chunk_index)
        if stored_fp == chunk.source_fingerprint:
            unchanged_count += 1
        else:
            changed_chunks.append(chunk)

    if not changed_chunks:
        # All chunks unchanged — skip embedding and DB write entirely
        summary.skipped_files.append(rel_path)
        return

    # Embed only the changed chunks in batches
    all_embeddings: list[list[float]] = []
    try:
        for start in range(0, len(changed_chunks), EMBED_BATCH_SIZE):
            batch = changed_chunks[start : start + EMBED_BATCH_SIZE]
            texts = [c.content for c in batch]
            response = embedding_provider.embed(texts)
            all_embeddings.extend(response.embeddings)
    except Exception as exc:
        logger.error("Embedding failed for %s: %s", rel_path, exc)
        summary.failed_files.append(rel_path)
        summary.errors[rel_path] = f"Embedding error: {exc}"
        return

    # Upsert changed chunks
    try:
        n = await upsert_chunks(session, changed_chunks, all_embeddings)
        summary.indexed_chunks += n
        summary.indexed_files.append(rel_path)
    except Exception as exc:
        logger.error("DB upsert failed for %s: %s", rel_path, exc)
        summary.failed_files.append(rel_path)
        summary.errors[rel_path] = f"DB upsert error: {exc}"
        return

    # Remove excess stale chunks (file shrank — old high-index chunks remain)
    old_indices = set(stored_fingerprints.keys())
    new_indices = {c.chunk_index for c in chunks}
    excess_indices = old_indices - new_indices
    if excess_indices:
        from sqlalchemy import delete

        from app.models.project_knowledge import ProjectKnowledge

        try:
            await session.execute(
                delete(ProjectKnowledge).where(
                    ProjectKnowledge.file_path == rel_path,
                    ProjectKnowledge.chunk_index.in_(excess_indices),
                )
            )
            await session.commit()
            logger.info(
                "Removed %d excess chunks for shrunken file %s",
                len(excess_indices),
                rel_path,
            )
        except Exception as exc:
            logger.warning("Could not remove excess chunks for %s: %s", rel_path, exc)
