"""
Git integration REST router (Phase 12).

Endpoints:
  GET    /api/git/log                  Recent commit log
  POST   /api/git/diff                 Retrieve diff (working/staged/refs)
  POST   /api/git/blame                File-level blame annotations
  GET    /api/git/branches             List all branches
  POST   /api/git/show                 Show specific commit details
  POST   /api/git/stage                Stage files (controlled mutation)
  POST   /api/git/commit               Create commit (requires approval token)
  POST   /api/git/branch               Create/switch branch (controlled mutation)
  GET    /api/git/stage-token           Compute approval token for staged files + message

Safety:
  - Read-only endpoints are unrestricted (safe git queries only).
  - Mutation endpoints require explicit approval tokens to prevent
    automated changes without human review.
  - git push, reset --hard, clean, and force operations are NEVER permitted.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.git.schemas import (
    GitBlameRequest,
    GitBlameResponse,
    GitBranchCreateRequest,
    GitBranchCreateResponse,
    GitBranchListResponse,
    GitCommitRequest,
    GitCommitResponse,
    GitDiffRequest,
    GitDiffResponse,
    GitLogResponse,
    GitShowRequest,
    GitShowResponse,
    GitStageRequest,
    GitStageResponse,
)
from app.git.service import (
    GitApprovalError,
    GitServiceError,
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["git"])


# ---------------------------------------------------------------------------
# Read-only endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/log",
    response_model=GitLogResponse,
    summary="Recent commit log",
)
async def get_log(
    project_root: Annotated[str, Query(description="Absolute path to project directory")],
    max_count: Annotated[int, Query(ge=1, le=100, description="Max entries to return")] = 20,
) -> GitLogResponse:
    """Retrieve recent commit history."""
    try:
        return await git_log(project_root, max_count=max_count)
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git log error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve git log.") from exc


@router.post(
    "/diff",
    response_model=GitDiffResponse,
    summary="Retrieve diff",
)
async def get_diff(req: GitDiffRequest) -> GitDiffResponse:
    """Retrieve working tree, staged, or ref-to-ref diff."""
    try:
        return await git_diff(
            req.project_root,
            diff_type=req.diff_type,
            ref_from=req.ref_from,
            ref_to=req.ref_to,
            path=req.path,
        )
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git diff error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve diff.") from exc


@router.post(
    "/blame",
    response_model=GitBlameResponse,
    summary="File blame annotations",
)
async def get_blame(req: GitBlameRequest) -> GitBlameResponse:
    """Retrieve line-level blame for a file."""
    try:
        return await git_blame(req.project_root, req.path)
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git blame error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve blame.") from exc


@router.get(
    "/branches",
    response_model=GitBranchListResponse,
    summary="List branches",
)
async def get_branches(
    project_root: Annotated[str, Query(description="Absolute path to project directory")],
) -> GitBranchListResponse:
    """List all local and remote branches."""
    try:
        return await git_branches(project_root)
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git branches error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list branches.") from exc


@router.post(
    "/show",
    response_model=GitShowResponse,
    summary="Show commit details",
)
async def show_commit(req: GitShowRequest) -> GitShowResponse:
    """Show details and diff of a specific commit."""
    try:
        return await git_show(req.project_root, ref=req.ref)
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git show error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to show commit.") from exc


# ---------------------------------------------------------------------------
# Controlled mutation endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/stage",
    response_model=GitStageResponse,
    summary="Stage files for commit",
)
async def stage_files(req: GitStageRequest) -> GitStageResponse:
    """Stage specific files for the next commit."""
    try:
        return await git_stage(req.project_root, req.paths)
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git stage error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to stage files.") from exc


@router.post(
    "/commit",
    response_model=GitCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a commit (requires approval)",
)
async def create_commit(req: GitCommitRequest) -> GitCommitResponse:
    """
    Create a commit with the given message.

    Requires an approval_token computed from the staged file list and
    commit message. This ensures the human has reviewed exactly what
    will be committed.
    """
    try:
        return await git_commit(req.project_root, req.message, req.approval_token)
    except GitApprovalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git commit error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create commit.") from exc


@router.post(
    "/branch",
    response_model=GitBranchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new branch",
)
async def create_branch(req: GitBranchCreateRequest) -> GitBranchCreateResponse:
    """Create a new branch and optionally switch to it."""
    try:
        return await git_create_branch(req.project_root, req.branch_name, switch=req.switch)
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("git branch error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create branch.") from exc


@router.get(
    "/stage-token",
    summary="Compute approval token for commit",
)
async def get_stage_token(
    project_root: Annotated[str, Query(description="Absolute path to project directory")],
    message: Annotated[str, Query(description="Intended commit message")],
) -> dict:
    """
    Preview the approval token for a commit.

    The frontend uses this to present the human with the exact
    staged content and message before approval.
    """
    from app.git.service import _run_git, _validate_project_root

    try:
        root = _validate_project_root(project_root)
        stdout, _, rc = await _run_git(root, "diff", "--cached", "--name-only")
        if rc != 0:
            raise GitServiceError("Failed to read staged files.")
        staged = [f.strip() for f in stdout.strip().splitlines() if f.strip()]

        token = compute_stage_approval_token(staged, message)
        return {
            "staged_files": staged,
            "message": message,
            "approval_token": token,
        }
    except GitServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
