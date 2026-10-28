"""
Semantic retrieval engine (Phase 9.5).

Embeds a user query through the EmbeddingProvider abstraction and
retrieves the most similar document chunks from PostgreSQL using the
pgvector cosine-distance operator (<=>) via HNSW/IVFFlat index.

Retrieval policy (configurable, documented below):
  - top_k: Number of results to return (default: 5, max: 20).
  - No arbitrary similarity threshold by default — the caller receives
    whatever the database returns and can apply its own threshold if
    desired.  This avoids silently dropping relevant results when
    embeddings are slightly out of distribution.

The retrieval is deterministic given the same query and database state.
No separate LLM framework is introduced.

Error handling:
  - Empty or whitespace-only queries raise ValueError.
  - Embedding-provider errors (auth, rate limit, server) propagate as
    LLMProviderError — callers handle accordingly.
  - Database failures raise SQLAlchemyError — callers roll back.
  - Dimension mismatch between query embedding and stored vectors
    raises ValueError before any database round-trip.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_knowledge import EMBEDDING_DIMENSION, ProjectKnowledge
from app.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

DEFAULT_TOP_K: int = 5
MAX_TOP_K: int = 20


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """
    A single retrieved chunk with relevance score and source location.

    Attributes:
        file_path:   Normalized POSIX relative path from project root.
        content:     Text content of the retrieved chunk.
        line_start:  1-based first line of the chunk.
        line_end:    1-based last line of the chunk.
        chunk_index: Position of the chunk within its source file.
        score:       Cosine similarity (1 - distance); higher is better.
                     Range: [−1, 1].  Values near 1.0 indicate high relevance.
    """

    file_path: str
    content: str
    line_start: int | None
    line_end: int | None
    chunk_index: int
    score: float


# ---------------------------------------------------------------------------
# Retrieval service
# ---------------------------------------------------------------------------


class RetrievalService:
    """
    Semantic search over the project_knowledge table.

    Args:
        embedding_provider: Any EmbeddingProvider implementation.
    """

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self._provider = embedding_provider

    async def search(
        self,
        query: str,
        session: AsyncSession,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[RetrievalResult]:
        """
        Find the *top_k* most relevant chunks for a natural-language query.

        Args:
            query:   User query string (non-empty).
            session: Active async SQLAlchemy session.
            top_k:   Maximum number of results to return (1 ≤ top_k ≤ MAX_TOP_K).

        Returns:
            List of RetrievalResult, ordered by descending cosine similarity.
            Empty list if the database has no rows.

        Raises:
            ValueError:        If query is empty/whitespace or top_k is out of range.
            LLMProviderError:  If the embedding provider fails.
            SQLAlchemyError:   If the database query fails.
        """
        query = query.strip()
        if not query:
            raise ValueError("Query must be a non-empty string.")

        top_k = max(1, min(int(top_k), MAX_TOP_K))

        # Embed the query
        response = self._provider.embed([query])
        query_vector = response.embeddings[0]

        # Validate query dimension
        if len(query_vector) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Query embedding dimension {len(query_vector)} does not match "
                f"stored dimension {EMBEDDING_DIMENSION}."
            )

        # Validate numeric values
        for val in query_vector:
            if not math.isfinite(val):
                raise ValueError(
                    f"Query embedding contains non-finite value {val!r}."
                )

        # pgvector cosine distance: embedding <=> query_vector
        # Cosine distance = 1 - cosine_similarity, so we ORDER BY ASC
        # and convert to similarity = 1 - distance for the result.
        distance_expr = (
            ProjectKnowledge.embedding.op("<=>")(query_vector)  # type: ignore[operator]
        )

        stmt = (
            select(
                ProjectKnowledge.file_path,
                ProjectKnowledge.content,
                ProjectKnowledge.line_start,
                ProjectKnowledge.line_end,
                ProjectKnowledge.chunk_index,
                distance_expr.label("distance"),
            )
            .where(ProjectKnowledge.embedding.isnot(None))
            .order_by(distance_expr)
            .limit(top_k)
        )

        rows = await session.execute(stmt)
        results: list[RetrievalResult] = []
        for row in rows:
            results.append(
                RetrievalResult(
                    file_path=row.file_path,
                    content=row.content,
                    line_start=row.line_start,
                    line_end=row.line_end,
                    chunk_index=row.chunk_index,
                    score=round(1.0 - float(row.distance), 6),
                )
            )

        logger.debug(
            "Semantic search for %r returned %d results (top_k=%d)",
            query[:60],
            len(results),
            top_k,
        )
        return results
