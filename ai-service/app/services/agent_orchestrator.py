"""
Agent orchestrator (Phase 8).

Manages an agentic reasoning loop between the LLM provider and the
Phase 7 ToolRegistry.  The orchestrator:

  1. Receives a user request with optional conversation context.
  2. Asks the LLM whether project inspection is needed.
  3. If a tool call is requested, validates the name, arguments, and
     permission before delegating to the ToolRegistry.
  4. Feeds the tool result back to the LLM for analysis.
  5. Repeats up to MAX_TOOL_STEPS, then forces a final answer.
  6. Returns a structured AgentResponse.

Safety guarantees:
  - Only READ_ONLY tools may be executed.
  - Tool names and arguments are validated against the registry.
  - Malformed LLM output is handled gracefully (no crash, no bypass).
  - A hard iteration cap prevents infinite loops.
  - No shell execution, file modification, or Git commands.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import LLMProvider, LLMResponse
from app.tools.base import PermissionLevel, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Hard cap on tool iterations per request.
MAX_TOOL_STEPS: int = 3


# ------------------------------------------------------------------
# Agent decision model
# ------------------------------------------------------------------

@dataclass
class AgentDecision:
    """Structured representation of what the agent decided to do."""

    type: str  # "final" | "tool_call"
    content: str | None = None         # final answer text
    tool: str | None = None            # tool name for tool_call
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Final output returned to the caller after orchestration completes."""

    message: str
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    steps_used: int = 0


# ------------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------------

def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Try to extract the first JSON object from *text*.

    Handles both bare JSON and ```json fenced code blocks.
    Returns None if no valid JSON object is found.
    """
    # Strategy 1: look for ```json ... ``` fenced block
    import re
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: find first { ... } pair
    start = text.find("{")
    if start == -1:
        return None

    # Walk forward looking for matching closing brace
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_agent_decision(llm_text: str) -> AgentDecision:
    """Parse the LLM's textual response into an AgentDecision.

    Expected JSON format for tool calls::

        {
            "action": "tool",
            "tool": "search_code",
            "arguments": {"query": "ChatService", "path": "."}
        }

    If the response does not contain a valid tool-call JSON block,
    it is treated as a direct final answer.
    """
    obj = _extract_json_block(llm_text)
    if obj is None:
        return AgentDecision(type="final", content=llm_text)

    action = obj.get("action")
    if action != "tool":
        return AgentDecision(type="final", content=llm_text)

    tool_name = obj.get("tool")
    arguments = obj.get("arguments", {})

    if not isinstance(tool_name, str) or not tool_name.strip():
        return AgentDecision(type="final", content=llm_text)

    if not isinstance(arguments, dict):
        return AgentDecision(type="final", content=llm_text)

    return AgentDecision(
        type="tool_call",
        tool=tool_name.strip(),
        arguments=arguments,
    )


# ------------------------------------------------------------------
# Tool-instruction prompt fragment
# ------------------------------------------------------------------

def build_tool_prompt_section(registry: ToolRegistry) -> str:
    """Build a concise tool-description block for inclusion in the system prompt."""
    tools = registry.list_tools()
    if not tools:
        return ""

    lines = [
        "You have access to the following read-only project inspection tools.",
        "When you need to answer a question about this project's source code, "
        "structure, or files, you MUST use these tools rather than guessing.",
        "",
        "To use a tool, respond with ONLY a JSON block in this exact format:",
        '{"action": "tool", "tool": "<tool_name>", "arguments": {<args>}}',
        "",
        "Available tools:",
    ]
    for t in tools:
        schema_keys = list((t.get("input_schema") or {}).get("properties", {}).keys())
        lines.append(f"  - {t['name']}: {t['description']}  Args: {schema_keys}")

    lines += [
        "",
        "Rules:",
        "- All tools are read-only.  You cannot modify, create, or delete files.",
        "- You cannot execute shell commands.",
        "- Do NOT invent file contents.  Use tools to obtain real data.",
        "- Tool results are authoritative.  If a tool says a file does not exist, it does not exist.",
        "- If you do NOT need project information, answer directly without a tool call.",
        "- When answering, clearly state if information is unavailable.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------

class AgentOrchestrator:
    """Minimal agentic orchestrator for Phase 8.

    Coordinates the LLM and the ToolRegistry in a bounded loop.
    """

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        max_steps: int = MAX_TOOL_STEPS,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._max_steps = max_steps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        messages: list[dict[str, str]],
    ) -> AgentResponse:
        """Run the agentic loop and return a final AgentResponse.

        *messages* is the pre-built prompt sequence produced by
        ``PromptBuilder`` (system + history + user).  The orchestrator
        may append tool-interaction messages during its loop.
        """
        working_messages = list(messages)  # shallow copy to avoid mutation
        tool_calls_made: list[dict[str, Any]] = []
        steps = 0

        while steps < self._max_steps:
            # Ask the LLM
            llm_response = self._call_llm(working_messages)
            decision = parse_agent_decision(llm_response.text)

            if decision.type == "final":
                return AgentResponse(
                    message=decision.content or llm_response.text,
                    tool_calls_made=tool_calls_made,
                    steps_used=steps,
                )

            # Decision is a tool call — validate and execute
            steps += 1
            tool_result = self._execute_tool(decision)

            tool_call_record = {
                "step": steps,
                "tool": decision.tool,
                "arguments": decision.arguments,
                "success": tool_result.success,
            }
            tool_calls_made.append(tool_call_record)

            # Feed the tool result back to the LLM
            working_messages.append({
                "role": "assistant",
                "content": llm_response.text,
            })
            working_messages.append({
                "role": "user",
                "content": self._format_tool_result(tool_result),
            })

        # Max steps reached — ask for a final answer
        working_messages.append({
            "role": "user",
            "content": (
                "You have used the maximum number of tool calls. "
                "Please provide your final answer now based on the information gathered so far."
            ),
        })
        llm_response = self._call_llm(working_messages)
        final_decision = parse_agent_decision(llm_response.text)

        if final_decision.type == "final":
            final_text = final_decision.content or llm_response.text
        else:
            final_text = (
                "Reached the maximum number of tool calls. "
                "Unable to perform further project inspections. "
                "Please refine or narrow your question."
            )

        return AgentResponse(
            message=final_text,
            tool_calls_made=tool_calls_made,
            steps_used=steps,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Delegate to the injected LLM provider."""
        return self._provider.chat(messages)

    def _execute_tool(self, decision: AgentDecision) -> ToolResult:
        """Validate and execute a tool call through the registry with telemetry tracing."""
        import time
        from app.services.telemetry import default_telemetry_service

        tool_name = decision.tool or ""

        # 1. Registry existence check
        if not self._registry.has_tool(tool_name):
            err_msg = f"Tool '{tool_name}' is not registered."
            default_telemetry_service.record_tool_execution(
                tool_name=tool_name,
                arguments=decision.arguments,
                duration_ms=0.0,
                success=False,
                error_message=err_msg,
            )
            return ToolResult.fail(
                tool_name=tool_name,
                code="TOOL_NOT_FOUND",
                message=err_msg,
            )

        # 2. Execute through registry (includes permission check)
        t0 = time.perf_counter()
        result = self._registry.execute(
            name=tool_name,
            params=decision.arguments,
            max_allowed_permission=PermissionLevel.READ_ONLY,
        )
        duration_ms = (time.perf_counter() - t0) * 1000

        try:
            default_telemetry_service.record_tool_execution(
                tool_name=tool_name,
                arguments=decision.arguments,
                duration_ms=duration_ms,
                success=result.success,
                error_message=result.error.message if result.error else None,
            )
        except Exception:
            pass

        return result

    @staticmethod
    def _format_tool_result(result: ToolResult) -> str:
        """Format a ToolResult into a message string for the LLM."""
        payload = result.model_dump(exclude_none=True)
        return f"[Tool Result]\n{json.dumps(payload, indent=2, default=str)}"
