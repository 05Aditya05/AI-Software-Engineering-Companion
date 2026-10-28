"""
Long-term memory service (Phase 10).

Provides CRUD operations and keyword search over the long_term_memory
table.  Project isolation is enforced at the query level: operations
that specify a project_root only affect rows with that exact value.

Design decisions:
  - No embedding-based search is performed at record time; memories are
    short enough that case-insensitive text search is sufficient for
    the initial version.  Semantic retrieval can be added later as an
    EmbeddingProvider call if needed.
  - Duplicate detection: a new memory is considered a near-duplicate
    if an existing row in the same category and project scope has
    identical content (exact match).  The caller receives a warning
    rather than a hard rejection, so the user can still store it.
  - verification_status is never automatically promoted from
    ``proposed`` to ``verified``.  Only the caller (API or test) may
    supply ``verified`` status, and only for memories that genuinely
    have external evidence.
  - Deletion is strictly scoped: deleting by ID only removes that
    specific row.  There is no bulk-delete path to prevent accidents.

Security:
  - No raw SQL strings are built from user input.
  - Database credentials are never logged.
  - Memory content must not include secrets; this is documented policy,
    not enforced programmatically (we cannot know what users write).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.schemas import (
    MemoryCreateRequest,
    MemoryEntry,
    MemorySearchRequest,
    MemoryUpdateRequest,
)
from app.models.memory import LongTermMemory

logger = logging.getLogger(__name__)


class DuplicateMemoryWarning:
    """Returned alongside a saved entry when a near-duplicate exists."""

    def __init__(self, existing_id: int) -> None:
        self.existing_id = existing_id
        self.message = (
            f"A memory with identical content already exists (id={existing_id}). "
            "Saved the new entry anyway. Consider reviewing both records."
        )


class MemoryService:
    """
    Application-level service for long-term memory operations.

    All methods accept an active AsyncSession.  Session management and
    transaction boundaries are the caller's responsibility.
    """

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        session: AsyncSession,
        req: MemoryCreateRequest,
    ) -> tuple[MemoryEntry, DuplicateMemoryWarning | None]:
        """
        Persist a new memory entry.

        Args:
            session: Active async SQLAlchemy session.
            req:     Validated MemoryCreateRequest.

        Returns:
            (MemoryEntry, DuplicateMemoryWarning | None)
            The warning is non-None if an identical content entry exists.
        """
        # Validation: project scope requires project_root
        if req.scope == "project" and not req.project_root:
            raise ValueError("project_root is required when scope='project'.")

        # Check for duplicate
        warning = await self._check_duplicate(session, req)

        # Build the row
        row = LongTermMemory(
            category=req.category,
            scope=req.scope,
            project_root=req.project_root,
            content=req.content,
            summary=req.summary,
            source=req.source,
            verification_status=req.verification_status,
            confidence=req.confidence,
            file_refs=req.file_refs or [],
        )
        session.add(row)
        await session.flush()  # Populate auto-generated id without committing
        await session.refresh(row)
        await session.commit()

        logger.info(
            "Memory created: id=%d category=%s scope=%s status=%s",
            row.id,
            row.category,
            row.scope,
            row.verification_status,
        )

        return _to_schema(row), warning

    # ------------------------------------------------------------------
    # Read / List / Search
    # ------------------------------------------------------------------

    async def get(
        self,
        session: AsyncSession,
        memory_id: int,
    ) -> MemoryEntry | None:
        """Retrieve a single memory entry by id, or None if not found."""
        row = await session.get(LongTermMemory, memory_id)
        if row is None:
            return None
        return _to_schema(row)

    async def search(
        self,
        session: AsyncSession,
        req: MemorySearchRequest,
    ) -> tuple[int, list[MemoryEntry]]:
        """
        Search and paginate memory entries.

        Args:
            session: Active async SQLAlchemy session.
            req:     Search/filter parameters.

        Returns:
            (total_count, page_of_entries)
        """
        stmt = select(LongTermMemory)

        if req.category:
            stmt = stmt.where(LongTermMemory.category == req.category)
        if req.scope:
            stmt = stmt.where(LongTermMemory.scope == req.scope)
        if req.project_root:
            stmt = stmt.where(LongTermMemory.project_root == req.project_root)
        if req.verification_status:
            stmt = stmt.where(LongTermMemory.verification_status == req.verification_status)
        if req.query:
            pattern = f"%{req.query.lower()}%"
            stmt = stmt.where(
                func.lower(LongTermMemory.content).like(pattern)
                | func.lower(LongTermMemory.summary).like(pattern)
            )

        # Count before pagination
        count_result = await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        total = count_result.scalar_one()

        # Paginated results — most recent first
        stmt = stmt.order_by(LongTermMemory.created_at.desc())
        stmt = stmt.offset(req.offset).limit(req.limit)

        rows_result = await session.execute(stmt)
        entries = [_to_schema(r) for r in rows_result.scalars()]

        return total, entries

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        session: AsyncSession,
        memory_id: int,
        req: MemoryUpdateRequest,
    ) -> MemoryEntry | None:
        """
        Partially update a memory entry.

        Only the fields set in *req* are changed.  Returns None if
        the entry does not exist.

        Verification status notes:
          - Callers may upgrade from ``proposed`` → ``unverified`` or
            ``proposed`` / ``unverified`` → ``verified``.
          - Downgrading from ``verified`` to lower states is permitted
            only for human users with appropriate context (no programmatic
            restriction here — the API layer may add it if needed).
        """
        row = await session.get(LongTermMemory, memory_id)
        if row is None:
            return None

        if req.content is not None:
            row.content = req.content
        if req.summary is not None:
            row.summary = req.summary
        if req.source is not None:
            row.source = req.source
        if req.verification_status is not None:
            row.verification_status = req.verification_status
        if req.confidence is not None:
            row.confidence = req.confidence
        if req.file_refs is not None:
            row.file_refs = req.file_refs

        # SQLAlchemy does not auto-set onupdate for in-memory changes to
        # server_default columns; set it explicitly.
        row.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(row)

        logger.info("Memory updated: id=%d status=%s", row.id, row.verification_status)
        return _to_schema(row)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(
        self,
        session: AsyncSession,
        memory_id: int,
        project_root: str | None = None,
    ) -> bool:
        """
        Delete a memory entry by id.

        If *project_root* is supplied, the deletion is restricted to rows
        that have that exact project_root value (project isolation guard).
        Returns True if a row was deleted, False if not found / not authorized.
        """
        row = await session.get(LongTermMemory, memory_id)
        if row is None:
            return False

        # Project isolation guard
        if project_root is not None and row.project_root != project_root:
            logger.warning(
                "Blocked deletion of memory id=%d: project_root mismatch "
                "(requested=%r, stored=%r)",
                memory_id,
                project_root,
                row.project_root,
            )
            return False

        await session.delete(row)
        await session.commit()
        logger.info("Memory deleted: id=%d", memory_id)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_duplicate(
        self,
        session: AsyncSession,
        req: MemoryCreateRequest,
    ) -> DuplicateMemoryWarning | None:
        """Return a warning if an exact-content duplicate exists."""
        stmt = (
            select(LongTermMemory.id)
            .where(
                LongTermMemory.category == req.category,
                LongTermMemory.scope == req.scope,
                LongTermMemory.content == req.content,
            )
        )
        if req.project_root:
            stmt = stmt.where(LongTermMemory.project_root == req.project_root)

        result = await session.execute(stmt.limit(1))
        row = result.scalar_one_or_none()
        if row is not None:
            return DuplicateMemoryWarning(existing_id=row)
        return None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _to_schema(row: LongTermMemory) -> MemoryEntry:
    """Convert an ORM row to the API response schema."""
    return MemoryEntry(
        id=row.id,
        category=row.category,
        scope=row.scope,
        project_root=row.project_root,
        content=row.content,
        summary=row.summary,
        source=row.source,
        verification_status=row.verification_status,
        confidence=row.confidence,
        file_refs=row.file_refs or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
