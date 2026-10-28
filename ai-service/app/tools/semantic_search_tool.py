"""
Semantic search tool for the AgentOrchestrator (Phase 9.6).

Integrates the RetrievalService into the ToolRegistry as a READ_ONLY
tool named ``semantic_search``.  The agent can invoke it to retrieve
project knowledge chunks that are semantically relevant to a query,
complementing the existing exact-match ``search_code`` tool.

Security:
  - The tool does NOT accept a file-path argument from the agent.
    Scope is always the entire indexed project.  Preventing arbitrary
    file-system access via arguments is therefore not needed here.
  - Results contain only content and metadata already stored during
    safe ingestion; no new file reads occur at retrieval time.
  - Top-K is capped at MAX_TOP_K (20) regardless of agent input.
  - Database session is managed inside the tool; no session is exposed
    to the agent or LLM.

Error handling:
  - Empty queries return a MISSING_PARAMETER error.
  - Embedding provider errors return a PROVIDER_ERROR.
  - Database errors return a DB_ERROR.
  - No crash escapes the execute() boundary (ToolResult.fail is always
    returned on exception).

Result format:
  - Each result includes: file_path, line_start, line_end, score,
    and a content excerpt (capped at EXCERPT_CHARS characters).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.knowledge.retrieval import DEFAULT_TOP_K, MAX_TOP_K, RetrievalService
from app.providers.base import EmbeddingProvider
from app.tools.base import PermissionLevel, Tool, ToolResult

logger = logging.getLogger(__name__)

# Maximum characters of chunk content included per result (keeps prompts compact).
EXCERPT_CHARS: int = 600


class SemanticSearchTool(Tool):
    """
    Semantic search over indexed project knowledge.

    Retrieves project-knowledge chunks that are semantically similar to
    a natural-language query using pgvector cosine similarity.

    This tool complements ``search_code`` (exact keyword match) — use
    ``semantic_search`` when the agent needs to answer conceptual
    questions (e.g. "how does authentication work?") rather than
    looking for a specific identifier.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        project_root: str,
    ) -> None:
        """
        Args:
            retrieval_service: Initialized RetrievalService.
            project_root:      Absolute project root path (used for path
                               validation and logging only).
        """
        self._retrieval = retrieval_service
        self._project_root = project_root

    # ------------------------------------------------------------------
    # Tool interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return (
            "Search the indexed project knowledge using natural-language semantic "
            "similarity. Returns relevant source-code or documentation chunks with "
            "file paths and line ranges. Use this tool when you need to find "
            "conceptually related code or documentation rather than an exact keyword. "
            "Complements search_code (exact match)."
        )

    @property
    def permission(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language question or concept to search for",
                },
                "top_k": {
                    "type": "integer",
                    "description": (
                        f"Maximum number of results to return "
                        f"(default: {DEFAULT_TOP_K}, max: {MAX_TOP_K})"
                    ),
                    "default": DEFAULT_TOP_K,
                },
            },
            "required": ["query"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute semantic search and return a ToolResult.

        Runs the async RetrievalService in a new event loop (the tool
        interface is synchronous to match the existing Tool.execute
        contract; async orchestration is handled by the caller).

        Args:
            params: Dict with 'query' (required) and 'top_k' (optional).

        Returns:
            ToolResult with a list of relevant chunks.
        """
        query = params.get("query")
        if not query or not str(query).strip():
            return ToolResult.fail(
                self.name,
                "MISSING_PARAMETER",
                "Parameter 'query' is required and must be non-empty.",
            )

        query_str = str(query).strip()
        try:
            top_k = max(1, min(int(params.get("top_k", DEFAULT_TOP_K)), MAX_TOP_K))
        except (ValueError, TypeError):
            top_k = DEFAULT_TOP_K

        try:
            results = self._run_search(query_str, top_k)
        except ValueError as exc:
            return ToolResult.fail(self.name, "INVALID_QUERY", str(exc))
        except Exception as exc:
            logger.error("semantic_search error: %s", exc)
            # Distinguish embedding errors from DB errors by message heuristic
            msg = str(exc)
            code = "PROVIDER_ERROR" if "embed" in msg.lower() else "DB_ERROR"
            return ToolResult.fail(self.name, code, f"Semantic search failed: {msg}")

        if not results:
            return ToolResult.ok(self.name, {
                "query": query_str,
                "total_results": 0,
                "results": [],
                "note": "No indexed knowledge matched the query.",
            })

        formatted = [
            {
                "file_path": r.file_path,
                "line_start": r.line_start,
                "line_end": r.line_end,
                "score": r.score,
                "excerpt": r.content[:EXCERPT_CHARS] + (
                    "…" if len(r.content) > EXCERPT_CHARS else ""
                ),
            }
            for r in results
        ]

        return ToolResult.ok(self.name, {
            "query": query_str,
            "total_results": len(formatted),
            "results": formatted,
        })

    # ------------------------------------------------------------------
    # Async bridge
    # ------------------------------------------------------------------

    def _run_search(self, query: str, top_k: int) -> list:
        """Run async search synchronously via a dedicated event loop."""
        return asyncio.run(self._async_search(query, top_k))

    async def _async_search(self, query: str, top_k: int) -> list:
        """Acquire a DB session and call the retrieval service."""
        from app.db import get_session  # noqa: PLC0415

        async for session in get_session():
            return await self._retrieval.search(query, session, top_k=top_k)
        return []
