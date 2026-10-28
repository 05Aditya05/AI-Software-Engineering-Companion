"""
Long-term memory model (Phase 10).

Stores durable engineering lessons, bug fixes, architecture decisions,
user preferences, and failed approaches.  Each record carries rich
provenance metadata so that the assistant can explain *why* a stored
memory is relevant and *how confident* the system is in it.

Verification policy:
  - ``proposed``:   Suggested by the AI without external confirmation.
  - ``unverified``: Entered by the user but not yet independently confirmed.
  - ``verified``:   Confirmed by a test run, build, or explicit user approval.

Never auto-upgrade ``proposed`` to ``verified`` without evidence.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

# Import the shared Base so all models share the same metadata/registry.
from app.models.project_knowledge import Base


class MemoryCategory:
    """Allowed memory category strings (not an enum to keep DB queries simple)."""

    BUG_FIX = "bug_fix"
    FAILED_APPROACH = "failed_approach"
    ARCHITECTURE_DECISION = "architecture_decision"
    USER_PREFERENCE = "user_preference"
    ENGINEERING_LESSON = "engineering_lesson"

    ALL: list[str] = [
        BUG_FIX,
        FAILED_APPROACH,
        ARCHITECTURE_DECISION,
        USER_PREFERENCE,
        ENGINEERING_LESSON,
    ]


class MemoryVerificationStatus:
    """Allowed verification status strings."""

    PROPOSED = "proposed"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"

    ALL: list[str] = [PROPOSED, UNVERIFIED, VERIFIED]


class MemoryScope:
    """Allowed memory scope strings."""

    GLOBAL = "global"       # Engineering lesson not tied to any project.
    PROJECT = "project"     # Fact specific to a given project root.

    ALL: list[str] = [GLOBAL, PROJECT]


class LongTermMemory(Base):
    """
    A single durable memory entry.

    Attributes:
        id:                  Auto-increment primary key.
        category:            One of MemoryCategory.ALL.
        scope:               ``global`` or ``project``.
        project_root:        Absolute path to project; None for global memories.
        content:             Full text of the memory.
        summary:             Concise one-line summary (<=512 chars).
        source:              Human-readable provenance description.
        verification_status: ``proposed``, ``unverified``, or ``verified``.
        confidence:          Optional qualitative confidence note.
        file_refs:           JSONB list of related file paths or symbols.
        created_at:          Row creation timestamp (UTC, server-set).
        updated_at:          Last update timestamp (UTC, server-set).
    """

    __tablename__ = "long_term_memory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global", index=True)
    project_root: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False, default="user")
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", index=True
    )
    confidence: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
