"""
Telemetry and Observability Service (Phase 16).

Tracks turn metrics, agent reasoning steps, tool execution traces, and
performance latency in a thread-safe, bounded in-memory ring buffer.

Safety and Invariants:
- Sensitive parameters (API keys, secrets, authorization tokens, raw image buffers)
  are strictly redacted before storage.
- Token counts are heuristic character-based approximations and are explicitly
  labeled as estimated (never fabricated as actual provider token counts).
- In-memory ring buffer prevents memory exhaustion and explicitly resets on service restart.
- Thread-safe using threading.Lock.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# Sensitive keys to redact
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|auth|authorization|credential|private[_-]?key)"
)


def redact_sensitive_value(key: str, val: Any) -> Any:
    """Recursively sanitize potentially sensitive fields in argument dictionaries."""
    if SENSITIVE_KEY_PATTERN.search(key):
        return "[REDACTED]"

    if key in ("image_base64", "thumbnail_base64", "data_base64") and isinstance(val, str):
        return f"[IMAGE_DATA:{len(val)} chars]"

    if isinstance(val, dict):
        return {k: redact_sensitive_value(k, v) for k, v in val.items()}

    if isinstance(val, list):
        return [redact_sensitive_value(key, item) for item in val]

    if isinstance(val, str) and len(val) > 400:
        return val[:400] + "... [TRUNCATED]"

    return val


def estimate_tokens(text: str) -> int:
    """Compute lightweight character-heuristic token count (1 token ~= 4 chars)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class ToolExecutionTrace:
    """Structured audit record of an individual tool call execution."""

    trace_id: str
    timestamp: str
    tool_name: str
    arguments: dict[str, Any]
    duration_ms: float
    success: bool
    error_message: str | None = None
    step: int | None = None


@dataclass
class TurnTelemetry:
    """Aggregated telemetry record for an end-to-end conversation turn."""

    turn_id: str
    conversation_id: str
    timestamp: str
    total_duration_ms: float
    llm_duration_ms: float
    tool_duration_ms: float
    tool_calls_count: int
    prompt_chars: int
    response_chars: int
    estimated_prompt_tokens: int
    estimated_response_tokens: int
    is_token_count_estimated: bool
    model: str | None
    provider: str | None
    success: bool
    error: str | None
    tool_traces: list[ToolExecutionTrace] = field(default_factory=list)


class TelemetryService:
    """Thread-safe bounded in-memory telemetry and observability manager."""

    def __init__(self, max_turns: int = 100, max_traces: int = 200) -> None:
        self._max_turns = max_turns
        self._max_traces = max_traces
        self._turn_history: deque[TurnTelemetry] = deque(maxlen=max_turns)
        self._tool_traces: deque[ToolExecutionTrace] = deque(maxlen=max_traces)
        self._lock = threading.Lock()
        self._active_since = datetime.now(timezone.utc).isoformat()
        self._total_turns_counter = 0
        self._successful_turns_counter = 0
        self._failed_turns_counter = 0
        self._total_tool_calls_counter = 0

    def record_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        duration_ms: float,
        success: bool,
        error_message: str | None = None,
        step: int | None = None,
    ) -> ToolExecutionTrace:
        """Record an individual tool execution in the audit trace log."""
        sanitized_args = {
            k: redact_sensitive_value(k, v) for k, v in (arguments or {}).items()
        }
        trace = ToolExecutionTrace(
            trace_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_name=tool_name,
            arguments=sanitized_args,
            duration_ms=round(duration_ms, 2),
            success=success,
            error_message=str(error_message)[:300] if error_message else None,
            step=step,
        )

        with self._lock:
            self._tool_traces.append(trace)
            self._total_tool_calls_counter += 1

        return trace

    def record_turn(
        self,
        conversation_id: str,
        total_duration_ms: float,
        llm_duration_ms: float = 0.0,
        tool_duration_ms: float = 0.0,
        tool_calls_count: int = 0,
        prompt_chars: int = 0,
        response_chars: int = 0,
        model: str | None = None,
        provider: str | None = None,
        success: bool = True,
        error: str | None = None,
        tool_traces: list[ToolExecutionTrace] | None = None,
    ) -> TurnTelemetry:
        """Record an end-to-end conversation turn."""
        turn = TurnTelemetry(
            turn_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_duration_ms=round(total_duration_ms, 2),
            llm_duration_ms=round(llm_duration_ms, 2),
            tool_duration_ms=round(tool_duration_ms, 2),
            tool_calls_count=tool_calls_count,
            prompt_chars=prompt_chars,
            response_chars=response_chars,
            estimated_prompt_tokens=estimate_tokens("a" * prompt_chars),
            estimated_response_tokens=estimate_tokens("a" * response_chars),
            is_token_count_estimated=True,
            model=model,
            provider=provider,
            success=success,
            error=str(error)[:300] if error else None,
            tool_traces=list(tool_traces or []),
        )

        with self._lock:
            self._turn_history.append(turn)
            self._total_turns_counter += 1
            if success:
                self._successful_turns_counter += 1
            else:
                self._failed_turns_counter += 1

        return turn

    def get_metrics(self) -> dict[str, Any]:
        """Return aggregated observability metrics."""
        with self._lock:
            turns = list(self._turn_history)
            traces = list(self._tool_traces)
            total_turns = self._total_turns_counter
            successful_turns = self._successful_turns_counter
            failed_turns = self._failed_turns_counter
            total_tool_calls = self._total_tool_calls_counter

        # Compute averages from recent history
        if turns:
            avg_turn_latency = sum(t.total_duration_ms for t in turns) / len(turns)
            avg_llm_latency = sum(t.llm_duration_ms for t in turns) / len(turns)
            avg_tool_latency = sum(t.tool_duration_ms for t in turns) / len(turns)
            est_prompt_tokens = sum(t.estimated_prompt_tokens for t in turns)
            est_response_tokens = sum(t.estimated_response_tokens for t in turns)
        else:
            avg_turn_latency = 0.0
            avg_llm_latency = 0.0
            avg_tool_latency = 0.0
            est_prompt_tokens = 0
            est_response_tokens = 0

        # Tool breakdown
        tool_breakdown: dict[str, int] = {}
        for trace in traces:
            tool_breakdown[trace.tool_name] = tool_breakdown.get(trace.tool_name, 0) + 1

        return {
            "status": "healthy",
            "active_since": self._active_since,
            "storage_type": "in-memory ring buffer (resets on restart)",
            "buffered_turns_count": len(turns),
            "buffered_traces_count": len(traces),
            "summary": {
                "total_turns": total_turns,
                "successful_turns": successful_turns,
                "failed_turns": failed_turns,
                "success_rate_percent": (
                    round((successful_turns / total_turns) * 100, 1)
                    if total_turns > 0
                    else 100.0
                ),
                "total_tool_calls": total_tool_calls,
                "avg_turn_latency_ms": round(avg_turn_latency, 2),
                "avg_llm_latency_ms": round(avg_llm_latency, 2),
                "avg_tool_latency_ms": round(avg_tool_latency, 2),
            },
            "token_estimates": {
                "estimated_prompt_tokens_recent": est_prompt_tokens,
                "estimated_response_tokens_recent": est_response_tokens,
                "is_token_count_estimated": True,
                "note": "Tokens are estimated using character heuristics (~4 chars/token).",
            },
            "tool_usage_breakdown": tool_breakdown,
        }

    def get_traces(
        self,
        limit: int = 50,
        outcome: str | None = None,
        tool_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return audit tool execution traces with optional filtering."""
        with self._lock:
            raw_traces = list(self._tool_traces)

        # Newest first
        raw_traces.reverse()

        filtered: list[ToolExecutionTrace] = []
        for trace in raw_traces:
            if outcome == "success" and not trace.success:
                continue
            if outcome == "failure" and trace.success:
                continue
            if tool_name and trace.tool_name.lower() != tool_name.lower():
                continue
            filtered.append(trace)
            if len(filtered) >= limit:
                break

        return [asdict(t) for t in filtered]

    def clear(self) -> None:
        """Clear telemetry buffers (used primarily for test isolation)."""
        with self._lock:
            self._turn_history.clear()
            self._tool_traces.clear()
            self._total_turns_counter = 0
            self._successful_turns_counter = 0
            self._failed_turns_counter = 0
            self._total_tool_calls_counter = 0


# Global singleton instance
default_telemetry_service = TelemetryService()
