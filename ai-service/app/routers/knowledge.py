"""
Knowledge indexing router (Phase 9.6/9.7).

Exposes a POST /api/knowledge/index endpoint that triggers incremental
project indexing on demand.  This endpoint is intended for internal or
admin use (e.g. called after project changes).

Security:
  - Indexing is scoped to the configured PROJECT_ROOT only.
  - No file paths are accepted from the request body.
  - Database credentials and secrets are never logged or returned.
  - The endpoint returns a summary without sensitive file contents.

If the required infrastructure (DATABASE_URL, GEMINI_API_KEY,
PROJECT_ROOT) is not configured, the endpoint returns HTTP 503.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge"])


class IndexResponse(BaseModel):
    """Response body returned by POST /api/knowledge/index."""

    success: bool
    indexed_files: int
    skipped_files: int
    removed_files: int
    failed_files: int
    indexed_chunks: int
    removed_chunks: int
    errors: dict[str, str]
    message: str


@router.post(
    "/index",
    response_model=IndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger incremental project knowledge indexing",
)
async def index_project() -> IndexResponse:
    """
    Trigger an incremental re-index of the configured project.

    Only new or changed files are re-embedded.  Deleted or ineligible
    files have their chunks removed.  Unchanged files are skipped.

    Returns an IndexSummary as JSON.

    Requires PROJECT_ROOT, DATABASE_URL, and GEMINI_API_KEY to be set.
    """
    project_root = settings.project_root.strip() if settings.project_root else ""
    if not project_root:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PROJECT_ROOT is not configured.",
        )

    db_url = settings.database_url.get_secret_value()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured.",
        )

    api_key = settings.gemini_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY is not configured.",
        )

    try:
        from app.db import get_session  # noqa: PLC0415
        from app.knowledge.indexer import incremental_index  # noqa: PLC0415
        from app.knowledge.storage import ensure_unique_constraint  # noqa: PLC0415
        from app.providers.embedding import GeminiEmbeddingProvider  # noqa: PLC0415
        from app.services.project_service import ProjectService  # noqa: PLC0415

        service = ProjectService(project_root)
        embedding_provider = GeminiEmbeddingProvider(
            api_key=api_key,
            model=settings.embedding_model,
        )

        async for session in get_session():
            # Ensure constraint exists (idempotent)
            try:
                await ensure_unique_constraint(session)
            except Exception as exc:
                logger.warning("Could not ensure unique constraint: %s", exc)

            summary = await incremental_index(service, embedding_provider, session)
            return IndexResponse(
                success=len(summary.failed_files) == 0,
                indexed_files=len(summary.indexed_files),
                skipped_files=len(summary.skipped_files),
                removed_files=len(summary.removed_files),
                failed_files=len(summary.failed_files),
                indexed_chunks=summary.indexed_chunks,
                removed_chunks=summary.removed_chunks,
                errors=summary.errors,
                message=str(summary),
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Knowledge indexing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Indexing failed. Check server logs for details.",
        ) from exc

    # Unreachable but satisfies type checker
    raise HTTPException(status_code=500, detail="Unexpected error")  # pragma: no cover
