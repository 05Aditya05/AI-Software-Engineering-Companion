"""
Observability and Telemetry Router (Phase 16).

Exposes system metrics, execution latencies, and tool audit traces.
"""

from typing import Any

from fastapi import APIRouter, Query, status

from app.services.telemetry import default_telemetry_service

router = APIRouter(tags=["observability"])


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Get aggregated telemetry metrics",
)
async def get_observability_metrics() -> dict[str, Any]:
    """
    Retrieve real-time aggregated metrics for conversation turns,
    tool call volume, average latencies, and estimated token usage.
    """
    return default_telemetry_service.get_metrics()


@router.get(
    "/traces",
    status_code=status.HTTP_200_OK,
    summary="Get audit tool execution traces",
)
async def get_observability_traces(
    limit: int = Query(default=50, ge=1, le=200, description="Max traces to return"),
    outcome: str | None = Query(default=None, description="Filter by 'success' or 'failure'"),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
) -> dict[str, Any]:
    """
    Retrieve structured audit logs of individual tool executions,
    including sanitized arguments, execution durations, and outcome status.
    """
    traces = default_telemetry_service.get_traces(
        limit=limit,
        outcome=outcome,
        tool_name=tool_name,
    )
    return {
        "count": len(traces),
        "limit": limit,
        "traces": traces,
    }
