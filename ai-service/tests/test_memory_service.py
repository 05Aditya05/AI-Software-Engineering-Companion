"""
Unit tests for MemoryService (Phase 10 — Long-Term Memory).

Tests CRUD operations, duplicate warnings, scoped isolation, and verification status policies
using mocked AsyncSession without requiring an active PostgreSQL database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.schemas import (
    MemoryCreateRequest,
    MemorySearchRequest,
    MemoryUpdateRequest,
)
from app.memory.service import DuplicateMemoryWarning, MemoryService
from app.models.memory import (
    LongTermMemory,
    MemoryCategory,
    MemoryScope,
    MemoryVerificationStatus,
)


def _make_dummy_row(
    id: int = 1,
    category: str = MemoryCategory.BUG_FIX,
    scope: str = MemoryScope.GLOBAL,
    project_root: str | None = None,
    content: str = "Always close async session generators cleanly.",
    summary: str = "Close async sessions",
    source: str = "user",
    verification_status: str = MemoryVerificationStatus.UNVERIFIED,
    confidence: str | None = "high",
    file_refs: list[str] | None = None,
) -> LongTermMemory:
    row = LongTermMemory(
        category=category,
        scope=scope,
        project_root=project_root,
        content=content,
        summary=summary,
        source=source,
        verification_status=verification_status,
        confidence=confidence,
        file_refs=file_refs or [],
    )
    row.id = id
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)
    return row


@pytest.fixture
def service() -> MemoryService:
    return MemoryService()


@pytest.mark.asyncio
async def test_create_memory_global_success(service: MemoryService) -> None:
    session = AsyncMock()
    # Mock duplicate check execute -> scalar_one_or_none -> None
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = None
    session.execute.return_value = dup_res

    req = MemoryCreateRequest(
        category=MemoryCategory.ENGINEERING_LESSON,
        scope=MemoryScope.GLOBAL,
        content="Prefer composition over deep inheritance hierarchies.",
        summary="Use composition",
        source="architecture-review",
        confidence="high",
        file_refs=["core/engine.py"],
    )

    async def mock_refresh(row):
        row.id = 42
        row.created_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=mock_refresh)

    entry, warning = await service.create(session, req)

    assert entry.id == 42
    assert entry.category == MemoryCategory.ENGINEERING_LESSON
    assert entry.scope == MemoryScope.GLOBAL
    assert entry.summary == "Use composition"
    assert warning is None
    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_memory_project_scope_requires_project_root(service: MemoryService) -> None:
    session = AsyncMock()
    req = MemoryCreateRequest(
        category=MemoryCategory.BUG_FIX,
        scope=MemoryScope.PROJECT,
        project_root=None,  # Missing
        content="Fixed issue with timeout",
        summary="Fixed timeout",
    )

    with pytest.raises(ValueError, match="project_root is required when scope='project'"):
        await service.create(session, req)


@pytest.mark.asyncio
async def test_create_memory_duplicate_detection(service: MemoryService) -> None:
    session = AsyncMock()
    # Duplicate check finds existing ID 99
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = 99
    session.execute.return_value = dup_res

    req = MemoryCreateRequest(
        category=MemoryCategory.BUG_FIX,
        scope=MemoryScope.GLOBAL,
        content="Identical content already stored.",
        summary="Duplicate test",
    )

    async def mock_refresh(row):
        row.id = 100
        row.created_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=mock_refresh)

    entry, warning = await service.create(session, req)

    assert entry.id == 100
    assert warning is not None
    assert isinstance(warning, DuplicateMemoryWarning)
    assert warning.existing_id == 99
    assert "already exists (id=99)" in warning.message


@pytest.mark.asyncio
async def test_get_memory_found_and_not_found(service: MemoryService) -> None:
    session = AsyncMock()
    row = _make_dummy_row(id=10)
    session.get.return_value = row

    entry = await service.get(session, 10)
    assert entry is not None
    assert entry.id == 10
    assert entry.summary == "Close async sessions"

    session.get.return_value = None
    entry_none = await service.get(session, 999)
    assert entry_none is None


@pytest.mark.asyncio
async def test_search_memories(service: MemoryService) -> None:
    session = AsyncMock()
    row1 = _make_dummy_row(id=1, summary="Lesson 1")
    row2 = _make_dummy_row(id=2, summary="Lesson 2")

    # Mock count query and fetch query
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    fetch_result = MagicMock()
    fetch_result.scalars.return_value = [row1, row2]

    session.execute.side_effect = [count_result, fetch_result]

    search_req = MemorySearchRequest(
        query="Lesson",
        category=MemoryCategory.BUG_FIX,
        limit=10,
        offset=0,
    )

    total, entries = await service.search(session, search_req)
    assert total == 2
    assert len(entries) == 2
    assert entries[0].id == 1
    assert entries[1].id == 2


@pytest.mark.asyncio
async def test_update_memory_success(service: MemoryService) -> None:
    session = AsyncMock()
    row = _make_dummy_row(id=5, verification_status=MemoryVerificationStatus.UNVERIFIED)
    session.get.return_value = row

    update_req = MemoryUpdateRequest(
        summary="Updated summary note",
        verification_status=MemoryVerificationStatus.VERIFIED,
        confidence="verified-by-pytest",
    )

    entry = await service.update(session, 5, update_req)
    assert entry is not None
    assert entry.summary == "Updated summary note"
    assert entry.verification_status == MemoryVerificationStatus.VERIFIED
    assert entry.confidence == "verified-by-pytest"
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_memory_not_found(service: MemoryService) -> None:
    session = AsyncMock()
    session.get.return_value = None

    update_req = MemoryUpdateRequest(summary="Updated summary note")
    entry = await service.update(session, 999, update_req)
    assert entry is None


@pytest.mark.asyncio
async def test_delete_memory_scoped(service: MemoryService) -> None:
    session = AsyncMock()
    # Scenario 1: matching project root
    row = _make_dummy_row(id=7, scope=MemoryScope.PROJECT, project_root="/projects/app")
    session.get.return_value = row

    deleted = await service.delete(session, 7, project_root="/projects/app")
    assert deleted is True
    session.delete.assert_called_once_with(row)
    session.commit.assert_called_once()

    # Scenario 2: mismatched project root should be rejected
    session.delete.reset_mock()
    deleted_mismatch = await service.delete(session, 7, project_root="/projects/other")
    assert deleted_mismatch is False
    session.delete.assert_not_called()
