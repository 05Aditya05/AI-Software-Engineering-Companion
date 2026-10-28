"""
Pydantic schemas and data transfer objects for the Controlled Coding Agent (Phase 11).

Contracts for code modification proposals, unified diffs, approval workflows,
git safety inspections, and post-apply validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field, field_validator


class FileAction(str, Enum):
    """Supported file manipulation operations."""

    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class ProposalStatus(str, Enum):
    """Proposal lifecycle state."""

    PROPOSED = "proposed"      # Created by AI or user, awaiting human review
    APPROVED = "approved"      # Explicitly confirmed by human reviewer
    REJECTED = "rejected"      # Declined by human reviewer
    APPLIED = "applied"        # Changes safely applied to filesystem
    FAILED = "failed"          # Error during application or rollback


class FileChangeItem(BaseModel):
    """Specification of an incoming change to a single file."""

    path: str = Field(..., description="Relative path from project_root.")
    action: str = Field(..., description="Action: 'create', 'modify', or 'delete'.")
    proposed_content: str | None = Field(
        default=None,
        description="New file contents for create/modify actions.",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in {a.value for a in FileAction}:
            raise ValueError(f"action must be one of {[a.value for a in FileAction]}")
        return v_lower

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        clean = v.strip().replace("\\", "/")
        if not clean:
            raise ValueError("File path cannot be empty.")
        if clean.startswith("/") or clean.startswith("../") or "/../" in clean:
            raise ValueError("Path must be a relative path within project_root.")
        return clean


class FileChange(BaseModel):
    """A fully computed file change with original content and unified diff."""

    path: str = Field(..., description="Relative path within the project root.")
    action: str = Field(..., description="create, modify, or delete.")
    original_content: str | None = Field(default=None, description="Pre-change content if file existed.")
    proposed_content: str | None = Field(default=None, description="Proposed content.")
    diff: str = Field(default="", description="Unified diff formatted output.")


class ValidationResult(BaseModel):
    """Result of running a post-apply validation command."""

    command: str = Field(..., description="The executed validation command.")
    exit_code: int = Field(..., description="Subprocess return code.")
    stdout: str = Field(default="", description="Captured standard output (truncated if large).")
    stderr: str = Field(default="", description="Captured standard error (truncated if large).")
    duration_ms: float = Field(..., description="Execution time in milliseconds.")
    passed: bool = Field(..., description="True if exit_code == 0.")


class Proposal(BaseModel):
    """
    An immutable proposal representing an atomic batch of file modifications.
    
    Carries a SHA-256 content_hash computed over the canonical representation
    of all changes to guarantee anti-tampering between proposal and application.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="")
    project_root: str = Field(..., min_length=1)
    changes: list[FileChange] = Field(default_factory=list)
    status: str = Field(default=ProposalStatus.PROPOSED.value)
    content_hash: str = Field(..., description="SHA-256 fingerprint of the proposal content.")
    validation_results: list[ValidationResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    applied_at: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None)


class ProposalCreateRequest(BaseModel):
    """Request payload to create a new change proposal."""

    title: str = Field(..., min_length=1, max_length=256, description="Short descriptive title.")
    description: str = Field(default="", description="Detailed rationale or issue reference.")
    project_root: str = Field(..., min_length=1, description="Absolute path to target project.")
    changes: list[FileChangeItem] = Field(..., min_length=1, description="List of proposed file modifications.")


class ProposalApproveRequest(BaseModel):
    """Explicit human approval payload requiring content hash verification."""

    content_hash: str = Field(..., description="The content_hash of the proposal being approved.")


class ProposalRejectRequest(BaseModel):
    """Payload to reject a proposed change."""

    reason: str | None = Field(default=None, description="Optional explanation for rejection.")


class ProposalApplyRequest(BaseModel):
    """Payload to apply an approved proposal."""

    content_hash: str = Field(..., description="Verification hash to ensure proposal was not modified.")
    run_validation: bool = Field(default=True, description="Whether to run safe validations post-apply.")


class ValidationRequest(BaseModel):
    """Payload to run on-demand validation commands against project."""

    project_root: str = Field(..., min_length=1)
    commands: list[list[str]] | None = Field(
        default=None,
        description="Optional list of command argv lists from allowlist (e.g. [['pytest'], ['npm', 'test']]).",
    )
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)


class GitStatusResponse(BaseModel):
    """Detailed git status inspection response."""

    is_git: bool
    branch: str | None = None
    clean: bool = True
    untracked_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    staged_files: list[str] = Field(default_factory=list)
    uncommitted_changes_count: int = 0
