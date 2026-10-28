"""
Tests for Git service (Phase 12).

Tests cover:
  - Read-only operations: log, diff, branches, show, blame
  - Controlled mutations: stage, commit with approval token
  - Safety: forbidden commands, path traversal, ref validation
  - Error handling: invalid project root, missing git
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.git.service import (
    GitApprovalError,
    GitServiceError,
    _validate_project_root,
    _validate_ref,
    _truncate,
    compute_stage_approval_token,
)
from app.git.schemas import (
    GitLogResponse,
    GitDiffResponse,
    GitBranchListResponse,
    GitShowResponse,
    GitBlameResponse,
    GitStageResponse,
    GitCommitResponse,
    GitBranchCreateResponse,
)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestValidateProjectRoot:
    """Tests for project root validation."""

    def test_valid_root(self, tmp_path: Path):
        result = _validate_project_root(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_nonexistent_root_raises(self):
        with pytest.raises(GitServiceError, match="does not exist"):
            _validate_project_root("/nonexistent/path/xyz")

    def test_file_not_dir_raises(self, tmp_path: Path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(GitServiceError, match="not a directory"):
            _validate_project_root(str(f))


class TestValidateRef:
    """Tests for git ref validation."""

    def test_valid_refs(self):
        assert _validate_ref("HEAD") == "HEAD"
        assert _validate_ref("main") == "main"
        assert _validate_ref("v1.0.0") == "v1.0.0"
        assert _validate_ref("feature/add-login") == "feature/add-login"
        assert _validate_ref("abc123") == "abc123"
        assert _validate_ref("HEAD~3") == "HEAD~3"
        assert _validate_ref("HEAD^2") == "HEAD^2"

    def test_invalid_refs(self):
        with pytest.raises(GitServiceError, match="Invalid git ref"):
            _validate_ref("")
        with pytest.raises(GitServiceError, match="Invalid git ref"):
            _validate_ref("ref; rm -rf /")
        with pytest.raises(GitServiceError, match="Invalid git ref"):
            _validate_ref("ref && echo pwned")


class TestTruncate:
    """Tests for output truncation."""

    def test_short_text(self):
        assert _truncate("hello") == "hello"

    def test_long_text(self):
        text = "x" * 60_000
        result = _truncate(text)
        assert len(result) < 60_000
        assert "truncated" in result


class TestApprovalToken:
    """Tests for commit approval token computation."""

    def test_deterministic(self):
        t1 = compute_stage_approval_token(["a.py", "b.py"], "fix bug")
        t2 = compute_stage_approval_token(["a.py", "b.py"], "fix bug")
        assert t1 == t2

    def test_sorted_order(self):
        t1 = compute_stage_approval_token(["b.py", "a.py"], "msg")
        t2 = compute_stage_approval_token(["a.py", "b.py"], "msg")
        assert t1 == t2  # Sorted, so order doesn't matter

    def test_different_message_different_token(self):
        t1 = compute_stage_approval_token(["a.py"], "fix")
        t2 = compute_stage_approval_token(["a.py"], "refactor")
        assert t1 != t2

    def test_token_is_sha256(self):
        token = compute_stage_approval_token(["test.py"], "test")
        assert len(token) == 64  # SHA-256 hex digest length


# ---------------------------------------------------------------------------
# Read-only operation tests (with mocked subprocess)
# ---------------------------------------------------------------------------


class TestGitLog:
    """Tests for git log."""

    @pytest.mark.asyncio
    async def test_log_parses_entries(self, tmp_path: Path):
        mock_log_output = (
            "abc123full|abc123|Alice|2026-10-28 10:00:00|Initial commit\n"
            "def456full|def456|Bob|2026-10-27 09:00:00|Add feature\n"
        )
        with patch("app.git.service._run_git") as mock_run:
            # First call: git log
            # Second call: git rev-parse --abbrev-ref HEAD
            mock_run.side_effect = [
                (mock_log_output, "", 0),
                ("main\n", "", 0),
            ]
            from app.git.service import git_log
            result = await git_log(str(tmp_path), max_count=10)

        assert isinstance(result, GitLogResponse)
        assert result.branch == "main"
        assert result.total_returned == 2
        assert result.entries[0].short_hash == "abc123"
        assert result.entries[1].author == "Bob"

    @pytest.mark.asyncio
    async def test_log_error_raises(self, tmp_path: Path):
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = ("", "fatal: not a git repo", 128)
            from app.git.service import git_log
            with pytest.raises(GitServiceError, match="git log failed"):
                await git_log(str(tmp_path))


class TestGitDiff:
    """Tests for git diff."""

    @pytest.mark.asyncio
    async def test_working_diff(self, tmp_path: Path):
        stat_output = " file.py | 2 +-\n 1 file changed\n"
        diff_output = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n"
        with patch("app.git.service._run_git") as mock_run:
            mock_run.side_effect = [
                (stat_output, "", 0),
                (diff_output, "", 0),
            ]
            from app.git.service import git_diff
            result = await git_diff(str(tmp_path), diff_type="working")

        assert isinstance(result, GitDiffResponse)
        assert result.files_changed == 1
        assert "diff --git" in result.diff_text


class TestGitBranches:
    """Tests for git branch listing."""

    @pytest.mark.asyncio
    async def test_branches_parsed(self, tmp_path: Path):
        output = "  feature/login\n* main\n  remotes/origin/main\n"
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = (output, "", 0)
            from app.git.service import git_branches
            result = await git_branches(str(tmp_path))

        assert isinstance(result, GitBranchListResponse)
        assert result.current_branch == "main"
        assert len(result.branches) >= 2


class TestGitShow:
    """Tests for git show."""

    @pytest.mark.asyncio
    async def test_show_commit(self, tmp_path: Path):
        output = "abc123\nAlice\n2026-10-28\nFix bug\n\ndiff --git a/f.py b/f.py\n"
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = (output, "", 0)
            from app.git.service import git_show
            result = await git_show(str(tmp_path), ref="HEAD")

        assert isinstance(result, GitShowResponse)
        assert result.hash == "abc123"
        assert result.author == "Alice"


# ---------------------------------------------------------------------------
# Controlled mutation tests
# ---------------------------------------------------------------------------


class TestGitStage:
    """Tests for git stage."""

    @pytest.mark.asyncio
    async def test_stage_valid_files(self, tmp_path: Path):
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = ("", "", 0)
            from app.git.service import git_stage
            result = await git_stage(str(tmp_path), ["file.py", "readme.md"])

        assert isinstance(result, GitStageResponse)
        assert len(result.staged_files) == 2
        assert len(result.warnings) == 0

    @pytest.mark.asyncio
    async def test_stage_rejects_forbidden_paths(self, tmp_path: Path):
        from app.git.service import git_stage
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = ("", "", 0)
            result = await git_stage(str(tmp_path), [".git/config", ".env", "ok.py"])

        assert "ok.py" in result.staged_files
        assert ".git/config" not in result.staged_files
        assert len(result.warnings) >= 2


class TestGitCommit:
    """Tests for git commit with approval."""

    @pytest.mark.asyncio
    async def test_commit_with_valid_token(self, tmp_path: Path):
        staged = ["a.py", "b.py"]
        message = "Fix: resolve null pointer"
        token = compute_stage_approval_token(staged, message)

        with patch("app.git.service._run_git") as mock_run:
            mock_run.side_effect = [
                ("a.py\nb.py\n", "", 0),     # diff --cached --name-only
                ("", "", 0),                   # commit
                ("abc123hash\n", "", 0),       # rev-parse HEAD
                ("main\n", "", 0),             # rev-parse --abbrev-ref HEAD
            ]
            from app.git.service import git_commit
            result = await git_commit(str(tmp_path), message, token)

        assert isinstance(result, GitCommitResponse)
        assert result.commit_hash == "abc123hash"
        assert result.message == message

    @pytest.mark.asyncio
    async def test_commit_rejects_invalid_token(self, tmp_path: Path):
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = ("a.py\n", "", 0)
            from app.git.service import git_commit
            with pytest.raises(GitApprovalError, match="Approval token mismatch"):
                await git_commit(str(tmp_path), "msg", "wrongtoken")

    @pytest.mark.asyncio
    async def test_commit_empty_message_raises(self, tmp_path: Path):
        from app.git.service import git_commit
        with pytest.raises(GitServiceError, match="empty"):
            await git_commit(str(tmp_path), "   ", "token")

    @pytest.mark.asyncio
    async def test_commit_no_staged_files_raises(self, tmp_path: Path):
        with patch("app.git.service._run_git") as mock_run:
            mock_run.return_value = ("\n", "", 0)
            from app.git.service import git_commit
            with pytest.raises(GitServiceError, match="No files are staged"):
                await git_commit(str(tmp_path), "msg", "token")


# ---------------------------------------------------------------------------
# Safety and security tests
# ---------------------------------------------------------------------------


class TestForbiddenCommands:
    """Tests that forbidden git commands are rejected."""

    @pytest.mark.asyncio
    async def test_push_forbidden(self, tmp_path: Path):
        from app.git.service import _run_git
        with pytest.raises(GitServiceError, match="Forbidden git command"):
            await _run_git(tmp_path, "push")

    @pytest.mark.asyncio
    async def test_reset_forbidden(self, tmp_path: Path):
        from app.git.service import _run_git
        with pytest.raises(GitServiceError, match="Forbidden git command"):
            await _run_git(tmp_path, "reset")

    @pytest.mark.asyncio
    async def test_clean_forbidden(self, tmp_path: Path):
        from app.git.service import _run_git
        with pytest.raises(GitServiceError, match="Forbidden git command"):
            await _run_git(tmp_path, "clean")

    @pytest.mark.asyncio
    async def test_rebase_forbidden(self, tmp_path: Path):
        from app.git.service import _run_git
        with pytest.raises(GitServiceError, match="Forbidden git command"):
            await _run_git(tmp_path, "rebase")

    @pytest.mark.asyncio
    async def test_merge_forbidden(self, tmp_path: Path):
        from app.git.service import _run_git
        with pytest.raises(GitServiceError, match="Forbidden git command"):
            await _run_git(tmp_path, "merge")
