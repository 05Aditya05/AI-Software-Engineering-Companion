"""
Pydantic schemas for the long-term memory API (Phase 10).

These are the I/O contracts for the REST endpoints.  Internal
SQLAlchemy objects are never exposed directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.memory import MemoryCategory, MemoryScope, MemoryVerificationStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class MemoryCreateRequest(BaseModel):
    """Payload to create a new memory entry."""

    category: str = Field(
        ...,
        description=f"Memory category. One of: {MemoryCategory.ALL}",
    )
    scope: str = Field(
        default=MemoryScope.GLOBAL,
        description="'global' or 'project'",
    )
    project_root: str | None = Field(
        default=None,
        description="Required when scope='project'. Absolute project path.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Full text of the memory.",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Concise one-line summary.",
    )
    source: str = Field(
        default="user",
        description="Provenance description (e.g. 'user', 'test run 2026-10-27', 'AI proposal').",
    )
    verification_status: str = Field(
        default=MemoryVerificationStatus.UNVERIFIED,
        description=f"One of: {MemoryVerificationStatus.ALL}. Default: unverified.",
    )
    confidence: str | None = Field(
        default=None,
        description="Optional qualitative confidence note.",
    )
    file_refs: list[str] = Field(
        default_factory=list,
        description="Optional list of related file paths or symbol names.",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in MemoryCategory.ALL:
            raise ValueError(f"category must be one of {MemoryCategory.ALL}")
        return v

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        if v not in MemoryScope.ALL:
            raise ValueError(f"scope must be one of {MemoryScope.ALL}")
        return v

    @field_validator("verification_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in MemoryVerificationStatus.ALL:
            raise ValueError(f"verification_status must be one of {MemoryVerificationStatus.ALL}")
        return v


class MemoryUpdateRequest(BaseModel):
    """Partial-update payload for a memory entry (all fields optional)."""

    content: str | None = Field(default=None, description="Updated content.")
    summary: str | None = Field(default=None, max_length=512, description="Updated summary.")
    source: str | None = Field(default=None, description="Updated provenance description.")
    verification_status: str | None = Field(default=None, description="Updated verification status.")
    confidence: str | None = Field(default=None, description="Updated confidence note.")
    file_refs: list[str] | None = Field(default=None, description="Updated file references.")

    @field_validator("verification_status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> Any:
        if v is not None and v not in MemoryVerificationStatus.ALL:
            raise ValueError(f"verification_status must be one of {MemoryVerificationStatus.ALL}")
        return v


class MemorySearchRequest(BaseModel):
    """Query parameters for memory search/listing."""

    query: str | None = Field(
        default=None,
        description="Optional keyword to filter by content or summary (case-insensitive).",
    )
    category: str | None = Field(default=None, description="Filter by category.")
    scope: str | None = Field(default=None, description="Filter by scope.")
    project_root: str | None = Field(default=None, description="Filter by project root.")
    verification_status: str | None = Field(default=None, description="Filter by status.")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results to return.")
    offset: int = Field(default=0, ge=0, description="Pagination offset.")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MemoryEntry(BaseModel):
    """Full memory record returned to the client."""

    id: int
    category: str
    scope: str
    project_root: str | None
    content: str
    summary: str
    source: str
    verification_status: str
    confidence: str | None
    file_refs: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    """Paginated list of memory entries."""

    total: int
    limit: int
    offset: int
    entries: list[MemoryEntry]


class MemoryDeleteResponse(BaseModel):
    """Response for DELETE operations."""

    success: bool
    deleted_id: int
    message: str
