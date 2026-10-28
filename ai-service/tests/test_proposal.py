"""
Unit tests for Phase 11 — Controlled Coding Agent (Proposal Manager, Diffs, Git Safety, Validator).

Validates:
  - Unified diff generation (create, modify, delete)
  - Anti-tampering SHA-256 canonical proposal hashing
  - Path traversal & security boundary enforcement (.git, .env, ../)
  - Proposal lifecycle (proposed -> approved -> applied / rejected)
  - Invariant: Zero filesystem modifications before explicit approval
  - Atomic rollback when application encounters an error
  - Subprocess validator command allowlist
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.coding_agent.diff_engine import compute_proposal_hash, generate_unified_diff
from app.coding_agent.git_safety import PathSafetyError, validate_safe_path
from app.coding_agent.proposal import (
    ProposalError,
    ProposalManager,
    ProposalNotFoundError,
    ProposalStaleError,
    ProposalStateError,
    ProposalTamperError,
)
from app.coding_agent.schemas import (
    FileAction,
    FileChange,
    FileChangeItem,
    ProposalCreateRequest,
    ProposalStatus,
)
from app.coding_agent.validator import (
    CommandValidationError,
    check_command_allowed,
    run_single_validation,
)


# ---------------------------------------------------------------------------
# 1. Diff Engine Tests
# ---------------------------------------------------------------------------


def test_diff_creation() -> None:
    diff = generate_unified_diff("src/new.py", None, "def new_func():\n    return 42\n")
    assert "--- /dev/null" in diff
    assert "+++ b/src/new.py" in diff
    assert "+def new_func():" in diff


def test_diff_modification() -> None:
    orig = "def compute():\n    return 1\n"
    prop = "def compute():\n    return 2\n"
    diff = generate_unified_diff("src/calc.py", orig, prop)
    assert "--- a/src/calc.py" in diff
    assert "+++ b/src/calc.py" in diff
    assert "-    return 1" in diff
    assert "+    return 2" in diff


def test_diff_deletion() -> None:
    orig = "deprecated code\n"
    diff = generate_unified_diff("src/old.py", orig, None)
    assert "--- a/src/old.py" in diff
    assert "+++ /dev/null" in diff
    assert "-deprecated code" in diff


def test_diff_no_changes() -> None:
    content = "unchanged text\n"
    diff = generate_unified_diff("src/same.py", content, content)
    assert diff == ""


# ---------------------------------------------------------------------------
# 2. Canonical Hashing Tests
# ---------------------------------------------------------------------------


def test_proposal_hash_deterministic() -> None:
    changes1 = [
        FileChange(path="b.py", action="modify", proposed_content="b_code"),
        FileChange(path="a.py", action="create", proposed_content="a_code"),
    ]
    changes2 = [
        FileChange(path="a.py", action="create", proposed_content="a_code"),
        FileChange(path="b.py", action="modify", proposed_content="b_code"),
    ]
    hash1 = compute_proposal_hash("/my/project", changes1)
    hash2 = compute_proposal_hash("/my/project", changes2)
    assert hash1 == hash2


def test_proposal_hash_sensitive_to_content() -> None:
    c1 = [FileChange(path="a.py", action="create", proposed_content="code 1")]
    c2 = [FileChange(path="a.py", action="create", proposed_content="code 2")]
    assert compute_proposal_hash("/proj", c1) != compute_proposal_hash("/proj", c2)


# ---------------------------------------------------------------------------
# 3. Path Safety & Boundary Tests
# ---------------------------------------------------------------------------


def test_validate_safe_path_valid(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    target = validate_safe_path(str(tmp_path), "sub/file.py")
    assert target == (sub / "file.py").resolve()


def test_validate_safe_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathSafetyError, match="Path must be a relative path|Path traversal detected"):
        validate_safe_path(str(tmp_path), "../outside.py")


def test_validate_safe_path_rejects_forbidden_targets(tmp_path: Path) -> None:
    with pytest.raises(PathSafetyError, match="forbidden for security"):
        validate_safe_path(str(tmp_path), ".git/config")

    with pytest.raises(PathSafetyError, match="forbidden for security"):
        validate_safe_path(str(tmp_path), ".env")

    with pytest.raises(PathSafetyError, match="forbidden for security"):
        validate_safe_path(str(tmp_path), ".env.production")


# ---------------------------------------------------------------------------
# 4. Proposal Manager Lifecycle & Atomic Rollback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proposal_lifecycle_success(tmp_path: Path) -> None:
    manager = ProposalManager()

    # Pre-existing file
    existing_file = tmp_path / "mod.txt"
    existing_file.write_text("original", encoding="utf-8")

    # File to delete
    delete_file = tmp_path / "del.txt"
    delete_file.write_text("delete me", encoding="utf-8")

    req = ProposalCreateRequest(
        title="Refactor core files",
        description="Update logic and clean up",
        project_root=str(tmp_path),
        changes=[
            FileChangeItem(path="mod.txt", action="modify", proposed_content="updated content"),
            FileChangeItem(path="new.txt", action="create", proposed_content="brand new"),
            FileChangeItem(path="del.txt", action="delete"),
        ],
    )

    # 1. Create proposal
    proposal = await manager.create_proposal(req)
    assert proposal.status == ProposalStatus.PROPOSED.value
    assert len(proposal.changes) == 3

    # INVARIANT CHECK: Files on disk must remain unchanged!
    assert existing_file.read_text(encoding="utf-8") == "original"
    assert not (tmp_path / "new.txt").exists()
    assert delete_file.exists()

    # 2. Cannot apply without approval
    with pytest.raises(ProposalStateError, match="Must be 'approved'"):
        await manager.apply_proposal(proposal.id, proposal.content_hash, run_validation=False)

    # 3. Approve with bad hash raises tamper error
    with pytest.raises(ProposalTamperError):
        manager.approve_proposal(proposal.id, "tampered_hash_000")

    # 4. Approve with correct hash
    approved = manager.approve_proposal(proposal.id, proposal.content_hash)
    assert approved.status == ProposalStatus.APPROVED.value

    # 5. Apply changes safely
    applied, _ = await manager.apply_proposal(proposal.id, proposal.content_hash, run_validation=False)
    assert applied.status == ProposalStatus.APPLIED.value

    # Verify on-disk updates
    assert existing_file.read_text(encoding="utf-8") == "updated content"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "brand new"
    assert not delete_file.exists()


@pytest.mark.asyncio
async def test_proposal_rejection(tmp_path: Path) -> None:
    manager = ProposalManager()
    req = ProposalCreateRequest(
        title="Change to reject",
        project_root=str(tmp_path),
        changes=[FileChangeItem(path="sample.txt", action="create", proposed_content="data")],
    )
    p = await manager.create_proposal(req)
    rejected = manager.reject_proposal(p.id, reason="Not approved by lead")
    assert rejected.status == ProposalStatus.REJECTED.value
    assert rejected.error_message == "Not approved by lead"


@pytest.mark.asyncio
async def test_proposal_rollback_on_error(tmp_path: Path) -> None:
    manager = ProposalManager()

    file1 = tmp_path / "f1.txt"
    file1.write_text("orig1", encoding="utf-8")

    req = ProposalCreateRequest(
        title="Failing Proposal",
        project_root=str(tmp_path),
        changes=[
            FileChangeItem(path="f1.txt", action="modify", proposed_content="new1"),
            FileChangeItem(path="f2.txt", action="create", proposed_content="new2"),
        ],
    )

    p = await manager.create_proposal(req)
    manager.approve_proposal(p.id, p.content_hash)

    # Inject failure during write of the second file
    original_write = Path.write_text

    def failing_write(self, data, *args, **kwargs):
        if "f2.txt" in str(self):
            raise OSError("Disk write error simulation")
        return original_write(self, data, *args, **kwargs)

    with patch.object(Path, "write_text", failing_write):
        with pytest.raises(ProposalError, match="Apply failed"):
            await manager.apply_proposal(p.id, p.content_hash, run_validation=False)

    # Rollback invariant: f1.txt must have been restored to orig1!
    assert file1.read_text(encoding="utf-8") == "orig1"
    assert not (tmp_path / "f2.txt").exists()

    proposal_failed = manager.get(p.id)
    assert proposal_failed is not None
    assert proposal_failed.status == ProposalStatus.FAILED.value


@pytest.mark.asyncio
async def test_proposal_stale_state_aborts_apply(tmp_path: Path) -> None:
    manager = ProposalManager()

    target_file = tmp_path / "concurrent.txt"
    target_file.write_text("initial version", encoding="utf-8")

    req = ProposalCreateRequest(
        title="Proposal before concurrent edit",
        project_root=str(tmp_path),
        changes=[
            FileChangeItem(path="concurrent.txt", action="modify", proposed_content="agent version"),
        ],
    )

    p = await manager.create_proposal(req)
    manager.approve_proposal(p.id, p.content_hash)

    # User concurrently edits the file on disk before agent applies
    target_file.write_text("concurrent user edit", encoding="utf-8")

    # Apply must detect stale state and abort
    with pytest.raises(ProposalStaleError, match="Stale state detected"):
        await manager.apply_proposal(p.id, p.content_hash, run_validation=False)

    # Invariant: User's concurrent edit was preserved and NOT overwritten!
    assert target_file.read_text(encoding="utf-8") == "concurrent user edit"


# ---------------------------------------------------------------------------
# 5. Validator Allowlist Tests
# ---------------------------------------------------------------------------


def test_validator_allowlist_permits_safe_commands() -> None:
    check_command_allowed(["pytest", "-v"])
    check_command_allowed(["npm", "test"])
    check_command_allowed(["python", "-m", "pytest", "tests/"])
    check_command_allowed(["git", "status", "--porcelain"])


def test_validator_allowlist_rejects_unsafe_commands() -> None:
    with pytest.raises(CommandValidationError, match="not in the allowed validation tool set"):
        check_command_allowed(["rm", "-rf", "/"])

    with pytest.raises(CommandValidationError, match="not in the allowed validation tool set"):
        check_command_allowed(["bash", "-c", "echo pwned"])

    with pytest.raises(CommandValidationError, match="Python validation is restricted"):
        check_command_allowed(["python", "arbitrary_script.py"])
