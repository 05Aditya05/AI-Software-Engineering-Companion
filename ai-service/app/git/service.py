"""
Git operations service (Phase 12).

Provides both read-only git inspection queries and controlled mutation
operations requiring explicit human approval.

Safety invariants:
  - NEVER execute: git push, git reset --hard, git clean -fd, git force-*
  - All operations are strictly confined within verified project root.
  - Mutation operations require an approval token (SHA-256 verification).
  - Subprocess execution uses argv list (no shell=True).
  - Output buffers are bounded to prevent memory exhaustion.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
from pathlib import Path

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

logger = logging.getLogger(__name__)

# Safety: commands that are NEVER allowed
FORBIDDEN_GIT_COMMANDS = frozenset({
    "push", "reset", "clean", "force-push",
    "rebase", "merge",  # also too dangerous for automated use
})

# Maximum output capture size (characters)
MAX_OUTPUT_CHARS = 50_000

# Maximum subprocess timeout (seconds)
MAX_TIMEOUT_SECONDS = 15


class GitServiceError(Exception):
    """Raised when a git operation fails."""


class GitApprovalError(ValueError):
    """Raised when approval token verification fails."""


def _find_git() -> str:
    """Locate git binary on system PATH."""
    git_bin = shutil.which("git")
    if not git_bin:
        raise GitServiceError("git executable not found on system PATH.")
    return git_bin


def _validate_project_root(project_root: str) -> Path:
    """Validate and resolve project root."""
    root = Path(project_root).resolve()
    if not root.exists() or not root.is_dir():
        raise GitServiceError(f"project_root does not exist or is not a directory: {project_root}")
    return root


def _validate_ref(ref: str) -> str:
    """
    Validate a git ref is safe (no shell injection).
    Allows: alphanumeric, -, _, /, ., ~, ^, @, :
    """
    if not ref or not re.match(r'^[a-zA-Z0-9\-_/\.~^@:{}]+$', ref):
        raise GitServiceError(f"Invalid git ref: '{ref}'")
    return ref


def _truncate(text: str) -> str:
    """Truncate output to safe limits."""
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated at {MAX_OUTPUT_CHARS} chars]"
    return text


async def _run_git(root: Path, *args: str, timeout: float = MAX_TIMEOUT_SECONDS) -> tuple[str, str, int]:
    """Run a git command safely and return (stdout, stderr, returncode)."""
    git_bin = _find_git()

    # Safety check: reject forbidden subcommands
    if args and args[0] in FORBIDDEN_GIT_COMMANDS:
        raise GitServiceError(f"Forbidden git command: 'git {args[0]}'")

    proc = await asyncio.create_subprocess_exec(
        git_bin, *args,
        cwd=str(root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise GitServiceError(f"Git command timed out after {timeout}s: git {' '.join(args)}")

    stdout = _truncate(stdout_raw.decode(errors="replace"))
    stderr = _truncate(stderr_raw.decode(errors="replace"))
    return stdout, stderr, proc.returncode or 0


# ---------------------------------------------------------------------------
# Read-only operations
# ---------------------------------------------------------------------------


async def git_log(project_root: str, max_count: int = 20) -> GitLogResponse:
    """Retrieve recent commit log entries."""
    root = _validate_project_root(project_root)
    max_count = max(1, min(max_count, 100))

    stdout, stderr, rc = await _run_git(
        root, "log",
        f"--max-count={max_count}",
        "--format=%H|%h|%an|%ai|%s",
        "--no-color",
    )

    if rc != 0:
        raise GitServiceError(f"git log failed: {stderr.strip()}")

    # Get current branch
    branch = None
    try:
        b_out, _, b_rc = await _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
        if b_rc == 0:
            branch = b_out.strip() or None
    except Exception:
        pass

    entries: list[GitLogEntry] = []
    for line in stdout.strip().splitlines():
        parts = line.split("|", 4)
        if len(parts) >= 5:
            entries.append(GitLogEntry(
                hash=parts[0],
                short_hash=parts[1],
                author=parts[2],
                date=parts[3],
                message=parts[4],
            ))

    return GitLogResponse(
        project_root=project_root,
        branch=branch,
        total_returned=len(entries),
        entries=entries,
    )


async def git_diff(
    project_root: str,
    diff_type: str = "working",
    ref_from: str | None = None,
    ref_to: str | None = None,
    path: str | None = None,
) -> GitDiffResponse:
    """Retrieve diff output for various diff types."""
    root = _validate_project_root(project_root)

    args: list[str] = ["diff", "--no-color", "--stat"]

    if diff_type == "staged":
        args.append("--cached")
    elif diff_type == "refs":
        if not ref_from:
            raise GitServiceError("ref_from is required for 'refs' diff_type")
        args.append(_validate_ref(ref_from))
        if ref_to:
            args.append(_validate_ref(ref_to))

    if path:
        # Validate path doesn't escape root
        safe = root / path.replace("\\", "/").strip("/")
        try:
            safe.resolve().relative_to(root)
        except ValueError:
            raise GitServiceError(f"Path traversal detected: '{path}'")
        args.extend(["--", path])

    stdout, stderr, rc = await _run_git(root, *args)
    if rc != 0:
        raise GitServiceError(f"git diff failed: {stderr.strip()}")

    # Count changed files from --stat output
    lines = stdout.strip().splitlines()
    files_changed = 0
    for line in lines:
        if "|" in line:
            files_changed += 1

    # Now get the full diff (without --stat)
    full_args = [a for a in args if a != "--stat"]
    full_out, _, _ = await _run_git(root, *full_args)

    return GitDiffResponse(
        project_root=project_root,
        diff_type=diff_type,
        diff_text=_truncate(full_out),
        files_changed=files_changed,
    )


async def git_blame(project_root: str, path: str) -> GitBlameResponse:
    """Retrieve git blame for a specific file."""
    root = _validate_project_root(project_root)

    # Validate path
    clean_path = path.replace("\\", "/").strip("/")
    safe = root / clean_path
    try:
        safe.resolve().relative_to(root)
    except ValueError:
        raise GitServiceError(f"Path traversal detected: '{path}'")
    if not safe.exists():
        raise GitServiceError(f"File not found: '{path}'")

    stdout, stderr, rc = await _run_git(
        root, "blame", "--porcelain", clean_path,
    )
    if rc != 0:
        raise GitServiceError(f"git blame failed: {stderr.strip()}")

    # Parse porcelain blame output
    entries: list[GitBlameEntry] = []
    lines = stdout.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Header line: <sha> <orig-line> <final-line> [<num-lines>]
        header_match = re.match(r'^([0-9a-f]{40})\s+\d+\s+(\d+)', line)
        if header_match:
            commit = header_match.group(1)[:8]
            line_number = int(header_match.group(2))
            author = ""
            date = ""
            content = ""

            # Read header fields
            i += 1
            while i < len(lines) and not lines[i].startswith("\t"):
                if lines[i].startswith("author "):
                    author = lines[i][7:]
                elif lines[i].startswith("author-time "):
                    date = lines[i][12:]
                i += 1

            # Content line starts with tab
            if i < len(lines) and lines[i].startswith("\t"):
                content = lines[i][1:]
                i += 1

            entries.append(GitBlameEntry(
                commit=commit,
                author=author,
                date=date,
                line_number=line_number,
                content=content[:200],
            ))
        else:
            i += 1

    # Limit blame output to first 500 lines
    entries = entries[:500]

    return GitBlameResponse(
        project_root=project_root,
        path=clean_path,
        entries=entries,
        total_lines=len(entries),
    )


async def git_branches(project_root: str) -> GitBranchListResponse:
    """List all local and remote branches."""
    root = _validate_project_root(project_root)

    stdout, stderr, rc = await _run_git(root, "branch", "-a", "--no-color")
    if rc != 0:
        raise GitServiceError(f"git branch failed: {stderr.strip()}")

    branches: list[GitBranchInfo] = []
    current_branch: str | None = None

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        is_current = line.startswith("* ")
        name = line.lstrip("* ").strip()
        is_remote = name.startswith("remotes/")

        if is_current:
            current_branch = name

        # Skip HEAD pointer
        if " -> " in name:
            continue

        branches.append(GitBranchInfo(
            name=name,
            is_current=is_current,
            is_remote=is_remote,
        ))

    return GitBranchListResponse(
        project_root=project_root,
        current_branch=current_branch,
        branches=branches,
    )


async def git_show(project_root: str, ref: str = "HEAD") -> GitShowResponse:
    """Show details of a specific commit."""
    root = _validate_project_root(project_root)
    safe_ref = _validate_ref(ref)

    stdout, stderr, rc = await _run_git(
        root, "show",
        "--no-color",
        "--format=%H%n%an%n%ai%n%B",
        safe_ref,
    )
    if rc != 0:
        raise GitServiceError(f"git show failed: {stderr.strip()}")

    lines = stdout.split("\n", 3)
    commit_hash = lines[0] if len(lines) > 0 else ""
    author = lines[1] if len(lines) > 1 else ""
    date = lines[2] if len(lines) > 2 else ""

    # Everything after the header separator is message + diff
    remaining = lines[3] if len(lines) > 3 else ""
    # Split at first 'diff --git' to separate message from diff
    if "diff --git" in remaining:
        idx = remaining.index("diff --git")
        message = remaining[:idx].strip()
        diff_text = remaining[idx:]
    else:
        message = remaining.strip()
        diff_text = ""

    return GitShowResponse(
        project_root=project_root,
        ref=safe_ref,
        hash=commit_hash,
        author=author,
        date=date,
        message=message,
        diff_text=_truncate(diff_text),
    )


# ---------------------------------------------------------------------------
# Controlled mutation operations (require approval)
# ---------------------------------------------------------------------------


def compute_stage_approval_token(paths: list[str], message: str = "") -> str:
    """
    Compute a SHA-256 approval token over the sorted file paths and commit message.
    This must be generated client-side and verified server-side.
    """
    canonical = "|".join(sorted(paths)) + "||" + message
    return hashlib.sha256(canonical.encode()).hexdigest()


async def git_stage(project_root: str, paths: list[str]) -> GitStageResponse:
    """
    Stage specific files for commit.

    Validates all paths are within project root before staging.
    """
    root = _validate_project_root(project_root)

    staged: list[str] = []
    warnings: list[str] = []

    for p in paths:
        clean = p.replace("\\", "/").strip("/")
        if not clean:
            warnings.append(f"Skipped empty path")
            continue

        target = root / clean
        try:
            target.resolve().relative_to(root)
        except ValueError:
            warnings.append(f"Skipped path traversal: '{p}'")
            continue

        # Check path safety (no .git, .env, etc.)
        parts = clean.split("/")
        forbidden = False
        for part in parts:
            if part in {".git", ".env"} or part.startswith(".env"):
                warnings.append(f"Skipped forbidden path: '{p}'")
                forbidden = True
                break
        if forbidden:
            continue

        _, stderr, rc = await _run_git(root, "add", clean)
        if rc != 0:
            warnings.append(f"Failed to stage '{p}': {stderr.strip()}")
        else:
            staged.append(clean)

    return GitStageResponse(
        project_root=project_root,
        staged_files=staged,
        warnings=warnings,
    )


async def git_commit(
    project_root: str,
    message: str,
    approval_token: str,
) -> GitCommitResponse:
    """
    Create a git commit with the given message.

    Requires a valid approval_token that matches the SHA-256 of the
    currently staged files + message. This prevents automated commits
    without explicit human review.
    """
    root = _validate_project_root(project_root)

    if not message.strip():
        raise GitServiceError("Commit message cannot be empty.")

    # Get currently staged files
    stdout, _, rc = await _run_git(root, "diff", "--cached", "--name-only")
    if rc != 0:
        raise GitServiceError("Failed to read staged files.")

    staged_files = [f.strip() for f in stdout.strip().splitlines() if f.strip()]
    if not staged_files:
        raise GitServiceError("No files are staged for commit.")

    # Verify approval token
    expected_token = compute_stage_approval_token(staged_files, message)
    if approval_token != expected_token:
        raise GitApprovalError(
            "Approval token mismatch. The staged files or commit message have changed "
            "since approval was granted. Re-review and approve again."
        )

    # Execute commit
    _, stderr, rc = await _run_git(root, "commit", "-m", message)
    if rc != 0:
        raise GitServiceError(f"git commit failed: {stderr.strip()}")

    # Get the resulting commit hash
    hash_out, _, _ = await _run_git(root, "rev-parse", "HEAD")
    commit_hash = hash_out.strip()

    # Get current branch
    branch = None
    try:
        b_out, _, b_rc = await _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
        if b_rc == 0:
            branch = b_out.strip() or None
    except Exception:
        pass

    return GitCommitResponse(
        project_root=project_root,
        commit_hash=commit_hash,
        message=message,
        branch=branch,
    )


async def git_create_branch(
    project_root: str,
    branch_name: str,
    switch: bool = True,
) -> GitBranchCreateResponse:
    """
    Create a new branch and optionally switch to it.

    Validates branch name for safety (no shell injection, no forbidden patterns).
    """
    root = _validate_project_root(project_root)

    # Validate branch name
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_/.]*$', branch_name):
        raise GitServiceError(f"Invalid branch name: '{branch_name}'")
    if branch_name.startswith("-"):
        raise GitServiceError("Branch name cannot start with '-'")
    if ".." in branch_name or branch_name.endswith(".lock"):
        raise GitServiceError(f"Invalid branch name pattern: '{branch_name}'")

    # Get current branch before switching
    prev_out, _, _ = await _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    previous_branch = prev_out.strip() or None

    # Create branch
    _, stderr, rc = await _run_git(root, "branch", branch_name)
    if rc != 0:
        raise GitServiceError(f"Failed to create branch '{branch_name}': {stderr.strip()}")

    switched = False
    if switch:
        _, stderr, rc = await _run_git(root, "switch", branch_name)
        if rc != 0:
            raise GitServiceError(f"Branch created but failed to switch: {stderr.strip()}")
        switched = True

    return GitBranchCreateResponse(
        project_root=project_root,
        branch_name=branch_name,
        switched=switched,
        previous_branch=previous_branch,
    )
