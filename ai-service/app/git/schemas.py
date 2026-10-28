"""
Pydantic schemas for Git Integration (Phase 12).

Covers read-only git inspection queries (log, diff, blame, branches)
and controlled mutation operations (stage, commit, branch create/switch).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Read-only query schemas
# ---------------------------------------------------------------------------


class GitLogEntry(BaseModel):
    """Single commit log entry."""
    hash: str
    short_hash: str
    author: str
    date: str
    message: str


class GitLogResponse(BaseModel):
    """Response for git log queries."""
    project_root: str
    branch: str | None = None
    total_returned: int = 0
    entries: list[GitLogEntry] = Field(default_factory=list)


class GitDiffRequest(BaseModel):
    """Request for viewing diffs."""
    project_root: str = Field(..., min_length=1)
    # "working" = unstaged, "staged" = cached, "refs" = between two refs
    diff_type: str = Field(default="working", description="One of: working, staged, refs")
    ref_from: str | None = Field(default=None, description="Base ref for 'refs' diff_type")
    ref_to: str | None = Field(default=None, description="Target ref for 'refs' diff_type")
    path: str | None = Field(default=None, description="Scope diff to specific file path")


class GitDiffResponse(BaseModel):
    """Response containing diff text."""
    project_root: str
    diff_type: str
    diff_text: str = ""
    files_changed: int = 0


class GitBlameRequest(BaseModel):
    """Request for git blame on a specific file."""
    project_root: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1, description="Relative file path to blame")


class GitBlameEntry(BaseModel):
    """Single blame line entry."""
    commit: str
    author: str
    date: str
    line_number: int
    content: str


class GitBlameResponse(BaseModel):
    """Response for git blame query."""
    project_root: str
    path: str
    entries: list[GitBlameEntry] = Field(default_factory=list)
    total_lines: int = 0


class GitBranchInfo(BaseModel):
    """Information about a single branch."""
    name: str
    is_current: bool = False
    is_remote: bool = False


class GitBranchListResponse(BaseModel):
    """Response listing all branches."""
    project_root: str
    current_branch: str | None = None
    branches: list[GitBranchInfo] = Field(default_factory=list)


class GitShowRequest(BaseModel):
    """Request to show a specific commit."""
    project_root: str = Field(..., min_length=1)
    ref: str = Field(default="HEAD", description="Commit hash or ref to show")


class GitShowResponse(BaseModel):
    """Response for git show."""
    project_root: str
    ref: str
    hash: str = ""
    author: str = ""
    date: str = ""
    message: str = ""
    diff_text: str = ""


# ---------------------------------------------------------------------------
# Controlled mutation schemas (require human approval)
# ---------------------------------------------------------------------------


class GitStageRequest(BaseModel):
    """Request to stage specific files."""
    project_root: str = Field(..., min_length=1)
    paths: list[str] = Field(..., min_length=1, description="Relative file paths to stage")


class GitStageResponse(BaseModel):
    """Response after staging files."""
    project_root: str
    staged_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GitCommitRequest(BaseModel):
    """Request to create a commit (requires explicit human approval)."""
    project_root: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=1024, description="Commit message")
    # Approval token: must match staged content hash for anti-tampering
    approval_token: str = Field(..., description="SHA-256 of staged file list + message for verification")


class GitCommitResponse(BaseModel):
    """Response after successful commit."""
    project_root: str
    commit_hash: str
    message: str
    branch: str | None = None


class GitBranchCreateRequest(BaseModel):
    """Request to create and optionally switch to a new branch."""
    project_root: str = Field(..., min_length=1)
    branch_name: str = Field(..., min_length=1, max_length=128)
    switch: bool = Field(default=True, description="Whether to switch to the new branch after creation")


class GitBranchCreateResponse(BaseModel):
    """Response after branch creation."""
    project_root: str
    branch_name: str
    switched: bool = False
    previous_branch: str | None = None
