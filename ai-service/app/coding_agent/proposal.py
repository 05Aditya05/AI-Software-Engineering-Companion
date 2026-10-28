"""
Proposal Manager for the Controlled Coding Agent (Phase 11).

Enforces strict lifecycle management:
  1. No filesystem modification until explicit human approval.
  2. Proposals are immutable with SHA-256 fingerprint verification.
  3. Pre-change file content snapshots enable complete rollback on failure.
  4. Post-apply execution runs only allowlisted validation commands.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.coding_agent.diff_engine import compute_proposal_hash, generate_unified_diff
from app.coding_agent.git_safety import PathSafetyError, validate_safe_path
from app.coding_agent.schemas import (
    FileAction,
    FileChange,
    Proposal,
    ProposalCreateRequest,
    ProposalStatus,
    ValidationResult,
)
from app.coding_agent.validator import run_validations

logger = logging.getLogger(__name__)


class ProposalError(Exception):
    """Base exception for proposal management operations."""


class ProposalNotFoundError(ProposalError):
    """Raised when the specified proposal ID does not exist."""


class ProposalStateError(ProposalError):
    """Raised when an operation is invalid for the proposal's current state."""


class ProposalTamperError(ProposalError):
    """Raised when the verification hash does not match the proposal content."""


class ProposalStaleError(ProposalError):
    """Raised when on-disk files were modified after proposal creation (stale state)."""


class ProposalManager:
    """
    Coordinates creation, lifecycle transitions, application, and rollback
    for code modification proposals.
    """

    def __init__(self) -> None:
        self._proposals: dict[str, Proposal] = {}

    def get(self, proposal_id: str) -> Proposal | None:
        """Retrieve a proposal by ID."""
        return self._proposals.get(proposal_id)

    def list(
        self,
        project_root: str | None = None,
        status: str | None = None,
    ) -> list[Proposal]:
        """List proposals, optionally filtered by project root and status."""
        items = list(self._proposals.values())
        if project_root:
            norm_root = str(Path(project_root).resolve()).lower()
            items = [p for p in items if str(Path(p.project_root).resolve()).lower() == norm_root]
        if status:
            items = [p for p in items if p.status == status]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    async def create_proposal(self, req: ProposalCreateRequest) -> Proposal:
        """
        Build an immutable Proposal with unified diffs and SHA-256 fingerprint.

        Inspects the filesystem for existing content without modifying anything.
        """
        root_path = Path(req.project_root).resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ProposalError(f"project_root does not exist or is not a directory: {req.project_root}")

        computed_changes: list[FileChange] = []

        for item in req.changes:
            # Validate safety and containment
            safe_target = validate_safe_path(req.project_root, item.path)
            clean_rel = item.path.replace("\\", "/").strip("/")

            # Read current content if file exists
            original_content: str | None = None
            if safe_target.exists():
                if safe_target.is_dir():
                    raise PathSafetyError(f"Target path '{item.path}' is an existing directory.")
                try:
                    original_content = safe_target.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    raise ProposalError(f"Failed reading existing file '{item.path}': {exc}") from exc

            # Verify action preconditions
            if item.action == FileAction.DELETE.value:
                if not safe_target.exists():
                    raise ProposalError(f"Cannot delete non-existent file '{item.path}'.")
                proposed_content = None
            elif item.action == FileAction.CREATE.value:
                proposed_content = item.proposed_content or ""
            else:  # MODIFY
                proposed_content = item.proposed_content if item.proposed_content is not None else (original_content or "")

            diff = generate_unified_diff(
                relative_path=clean_rel,
                original_content=original_content,
                proposed_content=proposed_content,
            )

            computed_changes.append(
                FileChange(
                    path=clean_rel,
                    action=item.action,
                    original_content=original_content,
                    proposed_content=proposed_content,
                    diff=diff,
                )
            )

        content_hash = compute_proposal_hash(str(root_path), computed_changes)

        proposal = Proposal(
            title=req.title,
            description=req.description,
            project_root=str(root_path),
            changes=computed_changes,
            status=ProposalStatus.PROPOSED.value,
            content_hash=content_hash,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self._proposals[proposal.id] = proposal
        return proposal

    def approve_proposal(self, proposal_id: str, content_hash: str) -> Proposal:
        """
        Transition proposal from PROPOSED to APPROVED.

        Requires exact content_hash verification to prevent race conditions or tampering.
        """
        proposal = self.get(proposal_id)
        if not proposal:
            raise ProposalNotFoundError(f"Proposal '{proposal_id}' not found.")

        if proposal.status != ProposalStatus.PROPOSED.value:
            raise ProposalStateError(
                f"Cannot approve proposal in status '{proposal.status}'. Must be '{ProposalStatus.PROPOSED.value}'."
            )

        if proposal.content_hash != content_hash:
            raise ProposalTamperError(
                "Provided content_hash does not match proposal content. Approval rejected."
            )

        proposal.status = ProposalStatus.APPROVED.value
        proposal.updated_at = datetime.now(timezone.utc)
        return proposal

    def reject_proposal(self, proposal_id: str, reason: str | None = None) -> Proposal:
        """Transition proposal to REJECTED."""
        proposal = self.get(proposal_id)
        if not proposal:
            raise ProposalNotFoundError(f"Proposal '{proposal_id}' not found.")

        if proposal.status not in (ProposalStatus.PROPOSED.value, ProposalStatus.APPROVED.value):
            raise ProposalStateError(f"Cannot reject proposal in status '{proposal.status}'.")

        proposal.status = ProposalStatus.REJECTED.value
        proposal.error_message = reason
        proposal.updated_at = datetime.now(timezone.utc)
        return proposal

    async def apply_proposal(
        self,
        proposal_id: str,
        content_hash: str,
        run_validation: bool = True,
        validation_commands: Sequence[list[str]] | None = None,
    ) -> tuple[Proposal, list[ValidationResult]]:
        """
        Safely apply approved changes to the filesystem with rollback on failure.

        Steps:
          1. Verify status is APPROVED and content_hash matches.
          2. Snapshot existing state of all files for rollback.
          3. Apply writes/deletes. If any error occurs, rollback all applied changes.
          4. Mark status APPLIED.
          5. Run post-apply validation commands if requested.
        """
        proposal = self.get(proposal_id)
        if not proposal:
            raise ProposalNotFoundError(f"Proposal '{proposal_id}' not found.")

        if proposal.status != ProposalStatus.APPROVED.value:
            raise ProposalStateError(
                f"Cannot apply proposal in status '{proposal.status}'. Must be '{ProposalStatus.APPROVED.value}'."
            )

        if proposal.content_hash != content_hash:
            raise ProposalTamperError(
                "Provided content_hash does not match proposal content. Application aborted."
            )

        root = Path(proposal.project_root)
        rollback_snapshot: dict[Path, str | None] = {}
        applied_paths: list[Path] = []

        # Stale state check: ensure target files on disk have not diverged from proposal baseline
        for change in proposal.changes:
            target = validate_safe_path(str(root), change.path)
            current_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() else None

            if change.action == FileAction.CREATE.value:
                if target.exists():
                    raise ProposalStaleError(
                        f"Stale state detected: File '{change.path}' was created on disk after proposal was created. "
                        "Application aborted to prevent data loss."
                    )
            elif change.action in (FileAction.MODIFY.value, FileAction.DELETE.value):
                if not target.exists():
                    raise ProposalStaleError(
                        f"Stale state detected: File '{change.path}' no longer exists on disk. "
                        "Application aborted to prevent data loss."
                    )
                if current_content != change.original_content:
                    raise ProposalStaleError(
                        f"Stale state detected: File '{change.path}' was modified on disk after proposal was created. "
                        "Application aborted to prevent data loss."
                    )

        # Prepare rollback snapshots
        for change in proposal.changes:
            target = validate_safe_path(str(root), change.path)
            if target.exists():
                rollback_snapshot[target] = target.read_text(encoding="utf-8", errors="replace")
            else:
                rollback_snapshot[target] = None  # Did not exist previously

        # Apply changes atomically
        try:
            for change in proposal.changes:
                target = validate_safe_path(str(root), change.path)

                if change.action in (FileAction.CREATE.value, FileAction.MODIFY.value):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = change.proposed_content or ""
                    target.write_text(content, encoding="utf-8")
                    applied_paths.append(target)
                elif change.action == FileAction.DELETE.value:
                    if target.exists():
                        target.unlink()
                        applied_paths.append(target)

            proposal.status = ProposalStatus.APPLIED.value
            proposal.applied_at = datetime.now(timezone.utc)
            proposal.updated_at = datetime.now(timezone.utc)

        except Exception as exc:
            logger.error("Error applying proposal '%s': %s. Rolling back...", proposal_id, exc)
            # Rollback
            for target, original in rollback_snapshot.items():
                try:
                    if original is None:
                        if target.exists():
                            target.unlink()
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(original, encoding="utf-8")
                except Exception as rollback_err:
                    logger.critical("Failed rolling back '%s': %s", target, rollback_err)

            proposal.status = ProposalStatus.FAILED.value
            proposal.error_message = f"Apply failed and changes rolled back: {exc}"
            proposal.updated_at = datetime.now(timezone.utc)
            raise ProposalError(f"Apply failed: {exc}") from exc

        # Post-apply validation
        validation_results: list[ValidationResult] = []
        if run_validation:
            try:
                validation_results = await run_validations(
                    project_root=proposal.project_root,
                    commands=validation_commands,
                )
                proposal.validation_results = validation_results
            except Exception as val_exc:
                logger.warning("Post-apply validation encountered error: %s", val_exc)

        return proposal, validation_results
