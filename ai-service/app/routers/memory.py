"""
Long-term memory REST router (Phase 10).

Endpoints:
  POST   /api/memory/                   Create a new memory entry.
  GET    /api/memory/                   List/search memory entries.
  GET    /api/memory/{id}               Retrieve a single entry.
  PATCH  /api/memory/{id}               Partially update an entry.
  DELETE /api/memory/{id}               Delete an entry.

Security:
  - All endpoints require DATABASE_URL to be configured (503 otherwise).
  - project_root is taken from the request body / query params only.
    No server-side automatic scoping is applied (no user auth exists yet).
  - Deletion with a mismatched project_root is silently rejected (404).
  - Database credentials and secrets are never logged or returned.

Multi-user limitation:
  User identity and per-user ACLs are NOT implemented in Phase 10.
  Any caller can create, read, update, or delete any memory entry if
  they know its ID and (for project memories) its project_root.
  This is acceptable for the single-developer desktop-companion scope
  and is explicitly documented here so future phases can add auth.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.memory.schemas import (
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryEntry,
    MemoryListResponse,
    MemorySearchRequest,
    MemoryUpdateRequest,
)
from app.memory.service import MemoryService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["memory"])

_service = MemoryService()


def _require_db() -> str:
    """Return the database URL or raise HTTP 503."""
    db_url = settings.database_url.get_secret_value()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured.",
        )
    return db_url


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new long-term memory entry",
)
async def create_memory(req: MemoryCreateRequest) -> dict:
    """
    Create a new memory entry.

    Returns the saved entry plus an optional duplicate_warning field
    if an identical content entry already exists.
    """
    _require_db()
    try:
        from app.db import get_session  # noqa: PLC0415

        async for session in get_session():
            entry, warning = await _service.create(session, req)
            result: dict = {"entry": entry.model_dump(mode="json")}
            if warning:
                result["duplicate_warning"] = warning.message
            return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory creation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Memory creation failed.") from exc

    raise HTTPException(status_code=500, detail="Unexpected error")  # pragma: no cover


@router.get(
    "/",
    response_model=MemoryListResponse,
    summary="List or search long-term memory entries",
)
async def list_memories(
    query: Annotated[str | None, Query(description="Keyword filter")] = None,
    category: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    project_root: Annotated[str | None, Query()] = None,
    verification_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MemoryListResponse:
    """List or search memory entries with optional filters."""
    _require_db()
    search_req = MemorySearchRequest(
        query=query,
        category=category,
        scope=scope,
        project_root=project_root,
        verification_status=verification_status,
        limit=limit,
        offset=offset,
    )
    try:
        from app.db import get_session  # noqa: PLC0415

        async for session in get_session():
            total, entries = await _service.search(session, search_req)
            return MemoryListResponse(
                total=total,
                limit=limit,
                offset=offset,
                entries=entries,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory search failed: %s", exc)
        raise HTTPException(status_code=500, detail="Memory search failed.") from exc

    raise HTTPException(status_code=500, detail="Unexpected error")  # pragma: no cover


@router.get(
    "/{memory_id}",
    response_model=MemoryEntry,
    summary="Retrieve a single memory entry",
)
async def get_memory(memory_id: int) -> MemoryEntry:
    """Retrieve a memory entry by ID."""
    _require_db()
    try:
        from app.db import get_session  # noqa: PLC0415

        async for session in get_session():
            entry = await _service.get(session, memory_id)
            if entry is None:
                raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found.")
            return entry
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory retrieval failed: %s", exc)
        raise HTTPException(status_code=500, detail="Memory retrieval failed.") from exc

    raise HTTPException(status_code=500, detail="Unexpected error")  # pragma: no cover


@router.patch(
    "/{memory_id}",
    response_model=MemoryEntry,
    summary="Partially update a memory entry",
)
async def update_memory(memory_id: int, req: MemoryUpdateRequest) -> MemoryEntry:
    """
    Partially update a memory entry.

    Only supplied fields are changed.  Supply ``verification_status='verified'``
    only when you have genuine external evidence (test pass, user confirmation).
    """
    _require_db()
    try:
        from app.db import get_session  # noqa: PLC0415

        async for session in get_session():
            entry = await _service.update(session, memory_id, req)
            if entry is None:
                raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found.")
            return entry
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Memory update failed.") from exc

    raise HTTPException(status_code=500, detail="Unexpected error")  # pragma: no cover


@router.delete(
    "/{memory_id}",
    response_model=MemoryDeleteResponse,
    summary="Delete a memory entry",
)
async def delete_memory(
    memory_id: int,
    project_root: Annotated[str | None, Query(description="Project-scope guard")] = None,
) -> MemoryDeleteResponse:
    """
    Delete a memory entry by ID.

    If *project_root* is supplied, deletion is restricted to entries
    with that exact project_root value.  Use this to enforce project
    isolation when deleting project-scoped memories.
    """
    _require_db()
    try:
        from app.db import get_session  # noqa: PLC0415

        async for session in get_session():
            deleted = await _service.delete(session, memory_id, project_root=project_root)
            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Memory {memory_id} not found or not accessible "
                        "with the provided project_root."
                    ),
                )
            return MemoryDeleteResponse(
                success=True,
                deleted_id=memory_id,
                message=f"Memory {memory_id} deleted successfully.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Memory deletion failed: %s", exc)
        raise HTTPException(status_code=500, detail="Memory deletion failed.") from exc

    raise HTTPException(status_code=500, detail="Unexpected error")  # pragma: no cover
