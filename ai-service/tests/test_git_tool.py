"""
Tests for GitInfoTool in ToolRegistry (Phase 12).

Tests metadata, schema validation, command dispatch, and read-only invariants.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from app.git.schemas import (
    GitBlameEntry,
    GitBlameResponse,
    GitBranchInfo,
    GitBranchListResponse,
    GitDiffResponse,
    GitLogEntry,
    GitLogResponse,
    GitShowResponse,
)
from app.tools.base import PermissionLevel
from app.tools.git_tool import GitInfoTool


@pytest.fixture
def git_tool() -> GitInfoTool:
    return GitInfoTool(project_root="C:\\test\\project")


def test_git_tool_metadata(git_tool: GitInfoTool) -> None:
    assert git_tool.name == "git_info"
    assert git_tool.permission == PermissionLevel.READ_ONLY
    assert "log" in git_tool.description
    assert git_tool.input_schema["type"] == "object"
    assert "command" in git_tool.input_schema["required"]


def test_git_tool_missing_command(git_tool: GitInfoTool) -> None:
    res = git_tool.execute({})
    assert not res.success
    assert res.error.code == "MISSING_PARAMETER"


def test_git_tool_invalid_command(git_tool: GitInfoTool) -> None:
    res = git_tool.execute({"command": "push"})
    assert not res.success
    assert res.error.code == "INVALID_COMMAND"


def test_git_tool_log_dispatch(git_tool: GitInfoTool) -> None:
    mock_log = GitLogResponse(
        project_root="C:\\test\\project",
        branch="main",
        total_returned=1,
        entries=[
            GitLogEntry(
                hash="a" * 40,
                short_hash="aaaaaaa",
                author="Dev",
                date="2026-10-28",
                message="feat: add git tool",
            )
        ],
    )
    with patch("app.git.service.git_log", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_log
        res = git_tool.execute({"command": "log", "max_count": 5})
        assert res.success
        assert len(res.data["entries"]) == 1
        assert res.data["entries"][0]["message"] == "feat: add git tool"
        mock_fn.assert_called_once_with("C:\\test\\project", max_count=5)


def test_git_tool_diff_dispatch(git_tool: GitInfoTool) -> None:
    mock_diff = GitDiffResponse(
        project_root="C:\\test\\project",
        diff_type="staged",
        diff_text="diff --git a/file.py b/file.py",
        files_changed=1,
    )
    with patch("app.git.service.git_diff", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_diff
        res = git_tool.execute({"command": "diff", "diff_type": "staged"})
        assert res.success
        assert res.data["files_changed"] == 1
        mock_fn.assert_called_once_with(
            "C:\\test\\project",
            diff_type="staged",
            ref_from=None,
            ref_to=None,
            path=None,
        )


def test_git_tool_branches_dispatch(git_tool: GitInfoTool) -> None:
    mock_branches = GitBranchListResponse(
        project_root="C:\\test\\project",
        current_branch="main",
        branches=[
            GitBranchInfo(name="main", is_current=True, is_remote=False)
        ],
    )
    with patch("app.git.service.git_branches", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_branches
        res = git_tool.execute({"command": "branches"})
        assert res.success
        assert res.data["current_branch"] == "main"


def test_git_tool_blame_requires_path(git_tool: GitInfoTool) -> None:
    res = git_tool.execute({"command": "blame"})
    assert not res.success
    assert res.error.code == "GIT_ERROR"


def test_git_tool_blame_dispatch(git_tool: GitInfoTool) -> None:
    mock_blame = GitBlameResponse(
        project_root="C:\\test\\project",
        path="app.py",
        total_lines=1,
        entries=[
            GitBlameEntry(
                line_number=1,
                commit="a" * 40,
                author="Dev",
                date="2026-10-28",
                content="print('hi')",
            )
        ],
    )
    with patch("app.git.service.git_blame", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_blame
        res = git_tool.execute({"command": "blame", "path": "app.py"})
        assert res.success
        assert len(res.data["entries"]) == 1
        mock_fn.assert_called_once_with("C:\\test\\project", "app.py")


def test_git_tool_show_dispatch(git_tool: GitInfoTool) -> None:
    mock_show = GitShowResponse(
        project_root="C:\\test\\project",
        ref="bbbbbbb",
        hash="b" * 40,
        author="Dev",
        date="2026-10-28",
        message="chore: test",
        diff_text="diff --git a/x.py b/x.py",
    )
    with patch("app.git.service.git_show", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_show
        res = git_tool.execute({"command": "show", "ref": "bbbbbbb"})
        assert res.success
        assert res.data["hash"] == "b" * 40
