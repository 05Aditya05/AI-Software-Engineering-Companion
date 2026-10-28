"""
Controlled Coding Agent REST router (Phase 11).

Endpoints:
  POST   /api/agent/proposals                  Create a new change proposal (with unified diffs).
  GET    /api/agent/proposals                  List proposals (filtered by root or status).
  GET    /api/agent/proposals/{id}             Get details of a single proposal.
  POST   /api/agent/proposals/{id}/approve     Approve proposal (requires content_hash verification).
  POST   /api/agent/proposals/{id}/reject      Reject proposal.
  POST   /api/agent/proposals/{id}/apply       Safely apply approved proposal to filesystem.
  POST   /api/agent/validate                   Run allowlisted validation checks against project.
  GET    /api/agent/git-status                 Inspect git working tree status safely.

Security:
  - No file changes occur before an explicit POST /approve and POST /apply.
  - Changes are strictly bounded to project_root with symlink traversal prevention.
  - Subprocess executions are restricted to safe allowlisted commands without shell=True.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.coding_agent.git_safety import PathSafetyError, inspect_git_status
from app.coding_agent.proposal import (
    ProposalError,
    ProposalManager,
    ProposalNotFoundError,
    ProposalStaleError,
    ProposalStateError,
    ProposalTamperError,
)
from app.coding_agent.schemas import (
    GitStatusResponse,
    Proposal,
    ProposalApplyRequest,
    ProposalApproveRequest,
    ProposalCreateRequest,
    ProposalRejectRequest,
    ValidationRequest,
    ValidationResult,
)
from app.coding_agent.validator import CommandValidationError, run_validations

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])
_manager = ProposalManager()


@router.post(
    "/proposals",
    response_model=Proposal,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new change proposal",
)
async def create_proposal(req: ProposalCreateRequest) -> Proposal:
    """Create an immutable change proposal with unified diffs and SHA-256 fingerprint."""
    try:
        return await _manager.create_proposal(req)
    except PathSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProposalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed creating proposal: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed creating proposal.") from exc


@router.get(
    "/proposals",
    response_model=list[Proposal],
    summary="List proposals",
)
async def list_proposals(
    project_root: Annotated[str | None, Query(description="Filter by project root")] = None,
    status: Annotated[str | None, Query(description="Filter by status (proposed/approved/applied/rejected)")] = None,
) -> list[Proposal]:
    """Retrieve all proposals matching optional project_root and status filters."""
    return _manager.list(project_root=project_root, status=status)


@router.get(
    "/proposals/{proposal_id}",
    response_model=Proposal,
    summary="Get proposal by ID",
)
async def get_proposal(proposal_id: str) -> Proposal:
    """Retrieve full details of a single proposal including diffs."""
    proposal = _manager.get(proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{proposal_id}' not found.",
        )
    return proposal


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=Proposal,
    summary="Approve a change proposal",
)
async def approve_proposal(proposal_id: str, req: ProposalApproveRequest) -> Proposal:
    """
    Approve a proposed change.

    Requires verifying the proposal's SHA-256 content_hash to ensure no tampering
    or concurrent modification took place between proposal and approval.
    """
    try:
        return _manager.approve_proposal(proposal_id, req.content_hash)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProposalTamperError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProposalStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=Proposal,
    summary="Reject a change proposal",
)
async def reject_proposal(proposal_id: str, req: ProposalRejectRequest | None = None) -> Proposal:
    """Reject a change proposal and transition its status to 'rejected'."""
    try:
        reason = req.reason if req else None
        return _manager.reject_proposal(proposal_id, reason=reason)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProposalStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/proposals/{proposal_id}/apply",
    response_model=dict,
    summary="Apply an approved change proposal to filesystem",
)
async def apply_proposal(proposal_id: str, req: ProposalApplyRequest) -> dict:
    """
    Safely apply an approved proposal to the filesystem.

    Enforces:
      - Proposal must be in 'approved' status.
      - Provided content_hash must match proposal.
      - Rollback snapshot restored automatically if apply encounters any error.
      - Post-apply validation executed if requested.
    """
    try:
        proposal, validation_results = await _manager.apply_proposal(
            proposal_id=proposal_id,
            content_hash=req.content_hash,
            run_validation=req.run_validation,
        )
        return {
            "proposal": proposal.model_dump(mode="json"),
            "validation_results": [r.model_dump(mode="json") for r in validation_results],
        }
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProposalTamperError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProposalStaleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProposalStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProposalError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post(
    "/validate",
    response_model=list[ValidationResult],
    summary="Run validation commands against project",
)
async def validate_project(req: ValidationRequest) -> list[ValidationResult]:
    """Execute allowlisted validation checks against the target project root."""
    try:
        return await run_validations(
            project_root=req.project_root,
            commands=req.commands,
            timeout_seconds=req.timeout_seconds,
        )
    except CommandValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Validation error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/git-status",
    response_model=GitStatusResponse,
    summary="Inspect git working tree status",
)
async def get_git_status(
    project_root: Annotated[str, Query(description="Absolute path to project directory")],
) -> GitStatusResponse:
    """Inspect git repository branch, uncommitted files, and working tree cleanliness."""
    return await inspect_git_status(project_root)
