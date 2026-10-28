"""
Real Git subprocess integration tests (Phase 12).

Executes genuine git operations in an isolated temporary repository:
- Read-only operations: log, diff, blame, branches, show
- Controlled mutations: stage, commit, branch creation
- Anti-tampering approval token verification
- Project-root confinement & path traversal rejection
- Destructive operations blocked
"""

from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

from app.git.service import (
    GitApprovalError,
    GitServiceError,
    _run_git,
    compute_stage_approval_token,
    git_blame,
    git_branches,
    git_commit,
    git_create_branch,
    git_diff,
    git_log,
    git_show,
    git_stage,
)


@pytest.fixture
def real_git_repo(tmp_path: Path) -> Path:
    """Creates a real git repository with an initial commit for integration testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # git init
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@companion.ai"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Companion Tester"], cwd=str(repo), check=True, capture_output=True)

    # Initial file and commit
    init_file = repo / "hello.py"
    init_file.write_text("print('Hello from test repo')\n", encoding="utf-8")

    subprocess.run(["git", "add", "hello.py"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=str(repo), check=True, capture_output=True)

    return repo


@pytest.mark.asyncio
async def test_real_git_log_and_show(real_git_repo: Path):
    log_res = await git_log(str(real_git_repo), max_count=5)
    assert log_res.total_returned == 1
    assert log_res.entries[0].message == "chore: initial commit"
    commit_hash = log_res.entries[0].hash

    show_res = await git_show(str(real_git_repo), ref=commit_hash)
    assert show_res.hash == commit_hash
    assert "Hello from test repo" in show_res.diff_text


@pytest.mark.asyncio
async def test_real_git_branches(real_git_repo: Path):
    branches_res = await git_branches(str(real_git_repo))
    assert branches_res.current_branch is not None
    assert len(branches_res.branches) >= 1
    assert any(b.is_current for b in branches_res.branches)


@pytest.mark.asyncio
async def test_real_git_blame(real_git_repo: Path):
    blame_res = await git_blame(str(real_git_repo), "hello.py")
    assert blame_res.total_lines == 1
    assert blame_res.entries[0].author == "Companion Tester"
    assert "print('Hello from test repo')" in blame_res.entries[0].content


@pytest.mark.asyncio
async def test_real_git_diff_working_and_staged(real_git_repo: Path):
    # Modify hello.py
    hello_file = real_git_repo / "hello.py"
    hello_file.write_text("print('Modified hello')\n", encoding="utf-8")

    # Working tree diff
    working_diff = await git_diff(str(real_git_repo), diff_type="working")
    assert "Modified hello" in working_diff.diff_text
    assert working_diff.files_changed >= 1

    # Stage the modification
    stage_res = await git_stage(str(real_git_repo), ["hello.py"])
    assert "hello.py" in stage_res.staged_files

    # Staged diff
    staged_diff = await git_diff(str(real_git_repo), diff_type="staged")
    assert "Modified hello" in staged_diff.diff_text


@pytest.mark.asyncio
async def test_real_git_commit_approval_token_lifecycle(real_git_repo: Path):
    # Add new file
    new_file = real_git_repo / "feature.py"
    new_file.write_text("def new_feature(): return True\n", encoding="utf-8")

    # Stage file
    await git_stage(str(real_git_repo), ["feature.py"])

    # Compute valid approval token for intended commit
    commit_msg = "feat: add new feature"
    valid_token = compute_stage_approval_token(["feature.py"], commit_msg)

    # 1. Invalid token is rejected with GitApprovalError
    with pytest.raises(GitApprovalError, match="Approval token mismatch"):
        await git_commit(str(real_git_repo), commit_msg, "invalid_token_1234567890abcdef")

    # 2. Token for a different commit message is rejected
    tampered_msg_token = compute_stage_approval_token(["feature.py"], "different message")
    with pytest.raises(GitApprovalError, match="Approval token mismatch"):
        await git_commit(str(real_git_repo), commit_msg, tampered_msg_token)

    # 3. Valid token succeeds
    commit_res = await git_commit(str(real_git_repo), commit_msg, valid_token)
    assert commit_res.commit_hash is not None
    assert commit_res.message == commit_msg

    # Verify log has 2 commits now
    log_res = await git_log(str(real_git_repo), max_count=5)
    assert log_res.total_returned == 2
    assert log_res.entries[0].message == "feat: add new feature"


@pytest.mark.asyncio
async def test_real_git_branch_creation(real_git_repo: Path):
    branch_res = await git_create_branch(str(real_git_repo), "feature/verified-branch", switch=True)
    assert branch_res.branch_name == "feature/verified-branch"
    assert branch_res.switched is True

    branches_res = await git_branches(str(real_git_repo))
    assert branches_res.current_branch == "feature/verified-branch"


@pytest.mark.asyncio
async def test_real_git_path_traversal_rejection(real_git_repo: Path):
    # 1. Staging path traversal: must not stage external file, must emit warning
    stage_res = await git_stage(str(real_git_repo), ["../../some_external_file.txt"])
    assert len(stage_res.staged_files) == 0
    assert any("traversal" in w.lower() for w in stage_res.warnings)

    # 2. Blame path traversal: raises GitServiceError with Path traversal detected
    with pytest.raises(GitServiceError, match="Path traversal detected"):
        await git_blame(str(real_git_repo), "../outside.py")


@pytest.mark.asyncio
async def test_real_git_stage_secret_files_rejection(real_git_repo: Path):
    # Attempting to stage .env
    env_file = real_git_repo / ".env"
    env_file.write_text("SECRET=123", encoding="utf-8")

    stage_res = await git_stage(str(real_git_repo), [".env", ".git/HEAD"])
    assert len(stage_res.staged_files) == 0
    assert len(stage_res.warnings) == 2
    assert any("forbidden" in w.lower() for w in stage_res.warnings)


@pytest.mark.asyncio
async def test_real_git_destructive_operations_blocked(real_git_repo: Path):
    # Ensure forbidden git commands are blocked before execution
    for forbidden_cmd in ["push", "reset", "clean", "rebase", "merge"]:
        with pytest.raises(GitServiceError, match="Forbidden git command"):
            await _run_git(real_git_repo, forbidden_cmd)
