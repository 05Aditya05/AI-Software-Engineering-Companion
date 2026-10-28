"""
Long-term memory search tool for AgentOrchestrator (Integration Bridge).

Allows the agent to retrieve relevant engineering lessons, bug fixes,
architecture decisions, and preferences from persistent storage.
Enforces strict project isolation and preserves provenance and verification status.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from pathlib import Path
from typing import Any

from app.memory.schemas import MemoryEntry, MemorySearchRequest
from app.memory.service import MemoryService
from app.models.memory import MemoryCategory, MemoryVerificationStatus
from app.tools.base import PermissionLevel, Tool, ToolResult

logger = logging.getLogger(__name__)

# Bounded excerpt length per memory to avoid inflating agent prompt tokens
MAX_MEMORY_EXCERPT_CHARS = 400
DEFAULT_MEMORY_SEARCH_LIMIT = 5
MAX_MEMORY_SEARCH_LIMIT = 10


class SearchMemoryTool(Tool):
    """
    Search persistent long-term memories and engineering lessons.

    The search is strictly scoped to global memories and the active project.
    Results explicitly show verification status ([VERIFIED], [UNVERIFIED], [PROPOSED])
    and source provenance so the agent can reason transparently about confidence.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        project_root: str,
    ) -> None:
        self._service = memory_service
        self._project_root = str(Path(project_root).resolve()).lower() if project_root else ""

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search long-term memory for relevant past engineering lessons, bug fixes, "
            "architecture decisions, and developer preferences. Results are strictly scoped "
            "to the active project and global lessons, and preserve verification status and provenance."
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
                    "description": "Optional keyword query to filter memory content or summary.",
                },
                "category": {
                    "type": "string",
                    "description": f"Optional category filter: {MemoryCategory.ALL}",
                },
                "verification_status": {
                    "type": "string",
                    "description": f"Optional status filter: {MemoryVerificationStatus.ALL}",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return (1-10, default 5).",
                },
            },
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        query_val = params.get("query")
        clean_query = str(query_val).strip() if query_val is not None else None

        category_val = params.get("category")
        clean_category = str(category_val).strip() if category_val is not None else None
        if clean_category and clean_category not in MemoryCategory.ALL:
            return ToolResult.fail(
                self.name,
                "INVALID_CATEGORY",
                f"category must be one of {MemoryCategory.ALL}",
            )

        status_val = params.get("verification_status")
        clean_status = str(status_val).strip() if status_val is not None else None
        if clean_status and clean_status not in MemoryVerificationStatus.ALL:
            return ToolResult.fail(
                self.name,
                "INVALID_STATUS",
                f"verification_status must be one of {MemoryVerificationStatus.ALL}",
            )

        try:
            limit = max(1, min(int(params.get("limit", DEFAULT_MEMORY_SEARCH_LIMIT)), MAX_MEMORY_SEARCH_LIMIT))
        except (ValueError, TypeError):
            limit = DEFAULT_MEMORY_SEARCH_LIMIT

        try:
            entries = self._run_search(
                query=clean_query,
                category=clean_category,
                verification_status=clean_status,
                limit=limit * 2,  # Fetch slightly more to account for scope filtering
            )
        except Exception as exc:
            logger.error("search_memory failed: %s", exc)
            return ToolResult.fail(self.name, "DB_ERROR", f"Memory search failed: {exc}")

        # Enforce strict project isolation:
        # Accept global memories OR project memories whose project_root matches active project
        scoped_entries: list[MemoryEntry] = []
        for e in entries:
            if e.scope == "global":
                scoped_entries.append(e)
            elif e.scope == "project" and e.project_root:
                norm_entry_root = str(Path(e.project_root).resolve()).lower()
                if norm_entry_root == self._project_root:
                    scoped_entries.append(e)

        # Trim to requested limit
        scoped_entries = scoped_entries[:limit]

        if not scoped_entries:
            return ToolResult.ok(self.name, {
                "total_found": 0,
                "memories": [],
                "note": "No memories found matching query and project scope.",
            })

        formatted = [
            {
                "id": m.id,
                "category": m.category,
                "scope": m.scope,
                "verification_status": m.verification_status,
                "confidence": m.confidence,
                "source": m.source,
                "summary": m.summary,
                "content_excerpt": (
                    m.content[:MAX_MEMORY_EXCERPT_CHARS] + "…"
                    if len(m.content) > MAX_MEMORY_EXCERPT_CHARS
                    else m.content
                ),
                "file_refs": m.file_refs,
            }
            for m in scoped_entries
        ]

        return ToolResult.ok(self.name, {
            "total_found": len(formatted),
            "memories": formatted,
        })

    # ------------------------------------------------------------------
    # Async DB bridge
    # ------------------------------------------------------------------

    def _run_search(
        self,
        query: str | None,
        category: str | None,
        verification_status: str | None,
        limit: int,
    ) -> list[MemoryEntry]:
        """Synchronously execute async DB search using dedicated executor if loop is running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self._async_search(query, category, verification_status, limit),
                ).result()

        return asyncio.run(self._async_search(query, category, verification_status, limit))

    async def _async_search(
        self,
        query: str | None,
        category: str | None,
        verification_status: str | None,
        limit: int,
    ) -> list[MemoryEntry]:
        from app.db import get_session  # noqa: PLC0415

        search_req = MemorySearchRequest(
            query=query,
            category=category,
            verification_status=verification_status,
            limit=limit,
            offset=0,
        )

        async for session in get_session():
            _, entries = await self._service.search(session, search_req)
            return entries

        return []
