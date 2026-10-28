"""
Tests for SearchMemoryTool and conversational memory injection (Integration Bridge).

Verifies:
  - Tool registration and metadata
  - Input validation (category, status, limit)
  - Result formatting and verification status retention
  - Strict project isolation (memories from other projects are never leaked)
  - Graceful handling of empty or error states
  - Verified memory prompt injection
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.schemas import MemoryEntry
from app.memory.service import MemoryService
from app.models.memory import MemoryCategory, MemoryVerificationStatus
from app.tools.base import PermissionLevel
from app.tools.memory_tool import SearchMemoryTool
from app.tools.project_tools import create_default_tool_registry


def _make_entry(
    id: int,
    category: str = MemoryCategory.ENGINEERING_LESSON,
    scope: str = "global",
    project_root: str | None = None,
    content: str = "Always test edge cases.",
    summary: str = "Test edge cases",
    source: str = "unit-test",
    verification_status: str = MemoryVerificationStatus.VERIFIED,
) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=id,
        category=category,
        scope=scope,
        project_root=project_root,
        content=content,
        summary=summary,
        source=source,
        verification_status=verification_status,
        confidence="high",
        file_refs=[],
        created_at=now,
        updated_at=now,
    )


def test_memory_tool_metadata() -> None:
    svc = MagicMock(spec=MemoryService)
    tool = SearchMemoryTool(svc, project_root="/app/myproject")
    assert tool.name == "search_memory"
    assert tool.permission == PermissionLevel.READ_ONLY
    assert "query" in tool.input_schema["properties"]
    assert "category" in tool.input_schema["properties"]


def test_memory_tool_invalid_parameters() -> None:
    svc = MagicMock(spec=MemoryService)
    tool = SearchMemoryTool(svc, project_root="/app/myproject")

    # Invalid category
    res_cat = tool.execute({"category": "non_existent"})
    assert not res_cat.success
    assert res_cat.error is not None
    assert res_cat.error.code == "INVALID_CATEGORY"

    # Invalid status
    res_stat = tool.execute({"verification_status": "non_existent"})
    assert not res_stat.success
    assert res_stat.error is not None
    assert res_stat.error.code == "INVALID_STATUS"


def test_memory_tool_project_isolation(tmp_path: Path) -> None:
    """Project-scoped memories from another project must NEVER be leaked."""
    proj_a = tmp_path / "project_a"
    proj_b = tmp_path / "project_b"
    proj_a.mkdir()
    proj_b.mkdir()

    svc = MagicMock(spec=MemoryService)
    tool = SearchMemoryTool(svc, project_root=str(proj_a))

    global_entry = _make_entry(1, scope="global", summary="Global rule")
    proj_a_entry = _make_entry(2, scope="project", project_root=str(proj_a), summary="Project A secret")
    proj_b_entry = _make_entry(3, scope="project", project_root=str(proj_b), summary="Project B secret")

    with patch.object(tool, "_run_search", return_value=[global_entry, proj_a_entry, proj_b_entry]):
        result = tool.execute({"limit": 5})

    assert result.success
    memories = result.data["memories"]
    ids = [m["id"] for m in memories]

    # Global and Project A must be present
    assert 1 in ids
    assert 2 in ids

    # Project B memory MUST NOT be present (Strict project isolation)
    assert 3 not in ids


def test_memory_tool_formatting_and_status() -> None:
    svc = MagicMock(spec=MemoryService)
    tool = SearchMemoryTool(svc, project_root="/test")

    verified_entry = _make_entry(
        10,
        category=MemoryCategory.BUG_FIX,
        summary="Fixed race condition",
        content="Long detailed fix explanation",
        verification_status=MemoryVerificationStatus.VERIFIED,
        source="PR #42 review",
    )

    with patch.object(tool, "_run_search", return_value=[verified_entry]):
        result = tool.execute({})

    assert result.success
    assert result.data["total_found"] == 1
    m = result.data["memories"][0]
    assert m["id"] == 10
    assert m["category"] == "bug_fix"
    assert m["verification_status"] == "verified"
    assert m["source"] == "PR #42 review"
    assert "Fixed race condition" in m["summary"]


def test_memory_tool_db_error_handling() -> None:
    svc = MagicMock(spec=MemoryService)
    tool = SearchMemoryTool(svc, project_root="/test")

    with patch.object(tool, "_run_search", side_effect=Exception("Database connection timeout")):
        result = tool.execute({})

    assert not result.success
    assert result.error is not None
    assert result.error.code == "DB_ERROR"
    assert "Database connection timeout" in result.error.message


def test_create_default_tool_registry_includes_memory_tool(tmp_path: Path) -> None:
    """When DATABASE_URL is configured, create_default_tool_registry registers search_memory."""
    with patch("app.config.settings.database_url") as mock_db:
        mock_db.get_secret_value.return_value = "postgresql+asyncpg://user:pass@localhost:5432/db"

        reg = create_default_tool_registry(str(tmp_path))
        assert reg.has_tool("search_memory")


def test_create_default_tool_registry_omits_memory_tool_when_no_db(tmp_path: Path) -> None:
    """When DATABASE_URL is empty, search_memory is omitted gracefully."""
    with patch("app.config.settings.database_url") as mock_db:
        mock_db.get_secret_value.return_value = ""

        reg = create_default_tool_registry(str(tmp_path))
        assert not reg.has_tool("search_memory")



def test_verified_memory_summary_injection(tmp_path: Path) -> None:
    from app.routers.chat import _get_verified_memory_summary

    entry1 = _make_entry(1, category=MemoryCategory.ARCHITECTURE_DECISION, summary="Use REST", content="Adopt REST APIs")
    entry2 = _make_entry(2, category=MemoryCategory.BUG_FIX, summary="Null check", content="Check nulls")

    with patch("app.config.settings.database_url") as mock_db, \
         patch("app.memory.service.MemoryService.search", new_callable=AsyncMock) as mock_search, \
         patch("app.db.get_session") as mock_session_gen:

        mock_db.get_secret_value.return_value = "postgresql+asyncpg://..."
        mock_search.return_value = (2, [entry1, entry2])

        async def fake_sess():
            yield AsyncMock()
        mock_session_gen.side_effect = fake_sess

        summary = _get_verified_memory_summary(str(tmp_path))
        assert summary is not None
        assert "--- Long-Term Memory (Verified Engineering Lessons) ---" in summary
        assert "[architecture_decision] Use REST" in summary
        assert "[bug_fix] Null check" in summary
