"""
API tests for Phase 12 Git Integration REST endpoints.

Validates:
  - GET  /api/git/log
  - POST /api/git/diff
  - POST /api/git/blame
  - GET  /api/git/branches
  - POST /api/git/show
  - POST /api/git/stage
  - POST /api/git/commit (approval token verification)
  - POST /api/git/branch
  - GET  /api/git/stage-token
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.git.schemas import (
    GitBlameEntry,
    GitBlameResponse,
    GitBranchCreateResponse,
    GitBranchInfo,
    GitBranchListResponse,
    GitCommitResponse,
    GitDiffResponse,
    GitLogEntry,
    GitLogResponse,
    GitShowResponse,
    GitStageResponse,
)
from app.git.service import GitApprovalError, GitServiceError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_git_log(client: TestClient) -> None:
    mock_log = GitLogResponse(
        project_root="C:\\test\\repo",
        branch="main",
        total_returned=1,
        entries=[
            GitLogEntry(
                hash="c" * 40,
                short_hash="ccccccc",
                author="Tester",
                date="2026-10-28",
                message="commit msg",
            )
        ],
    )
    with patch("app.routers.git.git_log", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_log
        res = client.get("/api/git/log?project_root=C:\\test\\repo&max_count=10")
        assert res.status_code == 200
        data = res.json()
        assert data["total_returned"] == 1
        assert data["entries"][0]["short_hash"] == "ccccccc"


def test_api_git_log_error(client: TestClient) -> None:
    with patch("app.routers.git.git_log", new_callable=AsyncMock) as mock_fn:
        mock_fn.side_effect = GitServiceError("Not a git repository")
        res = client.get("/api/git/log?project_root=C:\\bad\\path")
        assert res.status_code == 400
        assert "Not a git repository" in res.json()["detail"]


def test_api_git_diff(client: TestClient) -> None:
    mock_diff = GitDiffResponse(
        project_root="C:\\test\\repo",
        diff_type="working",
        diff_text="diff --git a/x b/x",
        files_changed=1,
    )
    with patch("app.routers.git.git_diff", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_diff
        res = client.post(
            "/api/git/diff",
            json={"project_root": "C:\\test\\repo", "diff_type": "working"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["diff_text"] == "diff --git a/x b/x"


def test_api_git_blame(client: TestClient) -> None:
    mock_blame = GitBlameResponse(
        project_root="C:\\test\\repo",
        path="main.py",
        entries=[
            GitBlameEntry(
                commit="d" * 40,
                author="Tester",
                date="2026-10-28",
                line_number=1,
                content="print('ok')",
            )
        ],
        total_lines=1,
    )
    with patch("app.routers.git.git_blame", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_blame
        res = client.post(
            "/api/git/blame",
            json={"project_root": "C:\\test\\repo", "path": "main.py"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["path"] == "main.py"
        assert len(data["entries"]) == 1


def test_api_git_branches(client: TestClient) -> None:
    mock_branches = GitBranchListResponse(
        project_root="C:\\test\\repo",
        current_branch="feature/phase12",
        branches=[
            GitBranchInfo(name="main", is_current=False, is_remote=False),
            GitBranchInfo(name="feature/phase12", is_current=True, is_remote=False),
        ],
    )
    with patch("app.routers.git.git_branches", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_branches
        res = client.get("/api/git/branches?project_root=C:\\test\\repo")
        assert res.status_code == 200
        data = res.json()
        assert data["current_branch"] == "feature/phase12"
        assert len(data["branches"]) == 2


def test_api_git_show(client: TestClient) -> None:
    mock_show = GitShowResponse(
        project_root="C:\\test\\repo",
        ref="HEAD",
        hash="e" * 40,
        author="Tester",
        date="2026-10-28",
        message="feat: awesome",
        diff_text="diff --git a/a b/a",
    )
    with patch("app.routers.git.git_show", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_show
        res = client.post(
            "/api/git/show",
            json={"project_root": "C:\\test\\repo", "ref": "HEAD"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["hash"] == "e" * 40


def test_api_git_stage(client: TestClient) -> None:
    mock_stage = GitStageResponse(
        project_root="C:\\test\\repo",
        staged_files=["app.py", "README.md"],
        warnings=[],
    )
    with patch("app.routers.git.git_stage", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_stage
        res = client.post(
            "/api/git/stage",
            json={"project_root": "C:\\test\\repo", "paths": ["app.py", "README.md"]},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["staged_files"] == ["app.py", "README.md"]


def test_api_git_commit(client: TestClient) -> None:
    mock_commit = GitCommitResponse(
        project_root="C:\\test\\repo",
        commit_hash="f" * 40,
        message="feat: safe commit",
        branch="main",
    )
    with patch("app.routers.git.git_commit", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_commit
        res = client.post(
            "/api/git/commit",
            json={
                "project_root": "C:\\test\\repo",
                "message": "feat: safe commit",
                "approval_token": "token123",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["commit_hash"] == "f" * 40


def test_api_git_commit_approval_conflict(client: TestClient) -> None:
    with patch("app.routers.git.git_commit", new_callable=AsyncMock) as mock_fn:
        mock_fn.side_effect = GitApprovalError("Approval token mismatch")
        res = client.post(
            "/api/git/commit",
            json={
                "project_root": "C:\\test\\repo",
                "message": "feat: bad token",
                "approval_token": "bad",
            },
        )
        assert res.status_code == 409
        assert "Approval token mismatch" in res.json()["detail"]


def test_api_git_branch_create(client: TestClient) -> None:
    mock_branch = GitBranchCreateResponse(
        project_root="C:\\test\\repo",
        branch_name="feature/new-branch",
        switched=True,
        previous_branch="main",
    )
    with patch("app.routers.git.git_create_branch", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_branch
        res = client.post(
            "/api/git/branch",
            json={
                "project_root": "C:\\test\\repo",
                "branch_name": "feature/new-branch",
                "switch": True,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["branch_name"] == "feature/new-branch"
        assert data["switched"] is True
