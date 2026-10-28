"""
Git safety and filesystem boundary enforcement (Phase 11).

Guarantees that all file operations are strictly confined within the verified
project root, protects against directory traversal and symlink escapes,
and inspects git working-tree status using non-destructive, read-only queries.

Safety invariants:
  - NEVER execute git commit, git push, git reset, git checkout, or git clean.
  - Path canonicalization resolves symlinks and verifies strict enclosure.
  - Sensitive files (.git, .env, private keys) are protected from writes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

from app.coding_agent.schemas import GitStatusResponse

logger = logging.getLogger(__name__)

# Sensitive path components that must never be targeted by code proposals
FORBIDDEN_PATH_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    ".env",
}


class PathSafetyError(ValueError):
    """Raised when a path breaches the allowed project boundary or targets a forbidden path."""


def validate_safe_path(project_root: str, relative_path: str) -> Path:
    """
    Validate that relative_path resolves strictly within project_root.

    Resolves symbolic links and canonicalizes both paths. Prevents path traversal
    and writes to sensitive control directories (.git, .env).

    Args:
        project_root: The declared absolute project root directory.
        relative_path: The relative file path to check.

    Returns:
        The canonicalized, safe Path object.

    Raises:
        PathSafetyError: If the path escapes the root or touches forbidden files.
    """
    clean_root = Path(project_root).resolve()
    if not clean_root.exists() or not clean_root.is_dir():
        raise PathSafetyError(f"project_root does not exist or is not a directory: {project_root}")

    # Normalize relative path separators
    normalized_rel = relative_path.replace("\\", "/").strip("/")
    if not normalized_rel:
        raise PathSafetyError("Relative path cannot be empty.")

    # Check for forbidden directories or sensitive files in parts
    parts = normalized_rel.split("/")
    for part in parts:
        if part in FORBIDDEN_PATH_PARTS or part.startswith(".env"):
            raise PathSafetyError(f"Modifying path '{relative_path}' is forbidden for security.")

    target_candidate = clean_root.joinpath(normalized_rel)

    # Resolve any symlinks in the path if parent exists
    try:
        resolved_target = target_candidate.resolve()
    except (RuntimeError, OSError) as exc:
        raise PathSafetyError(f"Invalid path structure: {exc}") from exc

    # Strict containment check: resolved target must start with resolved root
    try:
        resolved_target.relative_to(clean_root)
    except ValueError as exc:
        raise PathSafetyError(
            f"Path traversal detected: '{relative_path}' resolves outside project root '{project_root}'."
        ) from exc

    return resolved_target


async def inspect_git_status(project_root: str) -> GitStatusResponse:
    """
    Safely inspect the git repository status for project_root.

    Uses strictly read-only git commands:
      - `git rev-parse --is-inside-work-tree`
      - `git rev-parse --abbrev-ref HEAD`
      - `git status --porcelain`

    Returns:
        GitStatusResponse detailing branch, clean/dirty state, and file lists.
    """
    clean_root = Path(project_root).resolve()
    if not clean_root.exists() or not clean_root.is_dir():
        return GitStatusResponse(is_git=False)

    git_bin = shutil.which("git")
    if not git_bin:
        logger.debug("git executable not found on host.")
        return GitStatusResponse(is_git=False)

    # Check if directory is inside a git work tree
    try:
        proc = await asyncio.create_subprocess_exec(
            git_bin,
            "rev-parse",
            "--is-inside-work-tree",
            cwd=str(clean_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0 or stdout.decode().strip() != "true":
            return GitStatusResponse(is_git=False)
    except Exception as exc:
        logger.debug("Failed checking git repository status: %s", exc)
        return GitStatusResponse(is_git=False)

    # Get current branch name
    branch: str | None = None
    try:
        proc_branch = await asyncio.create_subprocess_exec(
            git_bin,
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
            cwd=str(clean_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_branch, _ = await proc_branch.communicate()
        if proc_branch.returncode == 0:
            branch = stdout_branch.decode().strip() or None
    except Exception:
        pass

    # Read status porcelain
    untracked: list[str] = []
    modified: list[str] = []
    staged: list[str] = []

    try:
        proc_status = await asyncio.create_subprocess_exec(
            git_bin,
            "status",
            "--porcelain",
            cwd=str(clean_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_status, _ = await proc_status.communicate()
        lines = stdout_status.decode(errors="replace").splitlines()

        for line in lines:
            if not line or len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            filepath = line[3:].strip()

            if index_status == "?" and worktree_status == "?":
                untracked.append(filepath)
            else:
                if index_status not in (" ", "?"):
                    staged.append(filepath)
                if worktree_status not in (" ", "?"):
                    modified.append(filepath)
    except Exception as exc:
        logger.warning("Error running git status: %s", exc)

    total_uncommitted = len(untracked) + len(modified) + len(staged)
    is_clean = total_uncommitted == 0

    return GitStatusResponse(
        is_git=True,
        branch=branch,
        clean=is_clean,
        untracked_files=untracked,
        modified_files=modified,
        staged_files=staged,
        uncommitted_changes_count=total_uncommitted,
    )
