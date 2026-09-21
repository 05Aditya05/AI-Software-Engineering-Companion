"""
Health check router.

Provides a simple endpoint to verify the AI service is running.
Used by the backend, monitoring, and service orchestration.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
async def health_check() -> dict:
    """Return service health status."""
    return {
        "status": "healthy",
        "service": "ai-companion-ai-service",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
