"""
Tests for Phase 8: Agent Orchestrator.

Validates the tool-selection loop, JSON parsing, safety boundaries,
iteration caps, error handling, and ChatService integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.exceptions import LLMProviderError, ValidationError
from app.providers.base import LLMProvider, LLMResponse
from app.schemas.chat import ChatRequest
from app.services.agent_orchestrator import (
    MAX_TOOL_STEPS,
    AgentDecision,
    AgentOrchestrator,
    build_tool_prompt_section,
    parse_agent_decision,
)
from app.services.chat_service import ChatService
from app.tools.base import PermissionLevel, ToolResult
from app.tools.project_tools import create_default_tool_registry
from app.tools.registry import ToolRegistry


# ------------------------------------------------------------------
# Test Fixtures & Mock Providers
# ------------------------------------------------------------------

class SequenceMockProvider(LLMProvider):
    """Mock provider that returns pre-configured responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0
        self.recorded_messages: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        self.recorded_messages.append(list(messages))
        if self.call_count < len(self.responses):
            text = self.responses[self.call_count]
        else:
            text = "Default fallback response."
        self.call_count += 1
        return LLMResponse(
            text=text,
            model="mock-seq-model",
            provider="mock",
        )


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal project structure with test files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def main():\n    return 'Hello World'\n", encoding="utf-8")
    (src / "service.py").write_text("class UserService:\n    pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Project\nDocumentation.", encoding="utf-8")
    return tmp_path


@pytest.fixture
def sample_registry(sample_project: Path) -> ToolRegistry:
    return create_default_tool_registry(str(sample_project))


# ------------------------------------------------------------------
# 1. Parsing Unit Tests
# ------------------------------------------------------------------

def test_parse_agent_decision_direct_answer() -> None:
    text = "Here is the explanation you requested about Python classes."
    decision = parse_agent_decision(text)
    assert decision.type == "final"
    assert decision.content == text


def test_parse_agent_decision_valid_json_tool_call() -> None:
    text = json.dumps({
        "action": "tool",
        "tool": "search_code",
        "arguments": {"query": "UserService", "path": "."},
    })
    decision = parse_agent_decision(text)
    assert decision.type == "tool_call"
    assert decision.tool == "search_code"
    assert decision.arguments == {"query": "UserService", "path": "."}


def test_parse_agent_decision_markdown_fenced_json() -> None:
    text = (
        "I need to check the file contents first.\n"
        "```json\n"
        '{\n  "action": "tool",\n  "tool": "read_file",\n  "arguments": {"path": "src/app.py"}\n}\n'
        "```\n"
    )
    decision = parse_agent_decision(text)
    assert decision.type == "tool_call"
    assert decision.tool == "read_file"
    assert decision.arguments == {"path": "src/app.py"}


def test_parse_agent_decision_embedded_json() -> None:
    text = (
        'Let me inspect this: {"action": "tool", "tool": "list_files", "arguments": {"path": "."}} thanks!'
    )
    decision = parse_agent_decision(text)
    assert decision.type == "tool_call"
    assert decision.tool == "list_files"
    assert decision.arguments == {"path": "."}


def test_parse_agent_decision_malformed_json_fallback() -> None:
    text = '```json\n{"action": "tool", "tool": "read_file", INVALID}\n```'
    decision = parse_agent_decision(text)
    assert decision.type == "final"
    assert decision.content == text


def test_parse_agent_decision_non_tool_action() -> None:
    text = json.dumps({"action": "think", "thought": "pondering"})
    decision = parse_agent_decision(text)
    assert decision.type == "final"
    assert decision.content == text


def test_parse_agent_decision_missing_or_invalid_tool_name() -> None:
    text = json.dumps({"action": "tool", "tool": "", "arguments": {}})
    decision = parse_agent_decision(text)
    assert decision.type == "final"

    text2 = json.dumps({"action": "tool", "arguments": {}})
    decision2 = parse_agent_decision(text2)
    assert decision2.type == "final"


def test_parse_agent_decision_non_dict_arguments() -> None:
    text = json.dumps({"action": "tool", "tool": "list_files", "arguments": "invalid"})
    decision = parse_agent_decision(text)
    assert decision.type == "final"


# ------------------------------------------------------------------
# 2. Tool Prompt Section
# ------------------------------------------------------------------

def test_build_tool_prompt_section(sample_registry: ToolRegistry) -> None:
    section = build_tool_prompt_section(sample_registry)
    assert "read-only" in section.lower()
    assert "list_files" in section
    assert "read_file" in section
    assert "search_code" in section
    assert "inspect_file" in section
    assert "cannot execute shell commands" in section.lower() or "shell" in section.lower()


def test_build_tool_prompt_section_empty_registry() -> None:
    empty_reg = ToolRegistry()
    assert build_tool_prompt_section(empty_reg) == ""


# ------------------------------------------------------------------
# 3. Agent Orchestrator Execution Loop
# ------------------------------------------------------------------

def test_orchestrator_direct_answer_no_tool_calls(sample_registry: ToolRegistry) -> None:
    provider = SequenceMockProvider(["I can answer directly: Python is an interpreted language."])
    orchestrator = AgentOrchestrator(provider=provider, registry=sample_registry)

    response = orchestrator.process([{"role": "user", "content": "What is Python?"}])

    assert response.message == "I can answer directly: Python is an interpreted language."
    assert response.steps_used == 0
    assert len(response.tool_calls_made) == 0
    assert provider.call_count == 1


def test_orchestrator_single_tool_call_flow(sample_registry: ToolRegistry) -> None:
    tool_request = json.dumps({
        "action": "tool",
        "tool": "read_file",
        "arguments": {"path": "src/app.py"},
    })
    final_reply = "The main function returns 'Hello World'."
    provider = SequenceMockProvider([tool_request, final_reply])
    orchestrator = AgentOrchestrator(provider=provider, registry=sample_registry)

    response = orchestrator.process([{"role": "user", "content": "What does src/app.py do?"}])

    assert response.message == final_reply
    assert response.steps_used == 1
    assert len(response.tool_calls_made) == 1
    assert response.tool_calls_made[0]["tool"] == "read_file"
    assert response.tool_calls_made[0]["success"] is True
    assert provider.call_count == 2

    # Second LLM call received tool result observation
    second_call_messages = provider.recorded_messages[1]
    assert any("[Tool Result]" in msg.get("content", "") for msg in second_call_messages)
    assert any("Hello World" in msg.get("content", "") for msg in second_call_messages)


def test_orchestrator_multi_step_tool_calls(sample_registry: ToolRegistry) -> None:
    step1 = json.dumps({"action": "tool", "tool": "list_files", "arguments": {"path": "src"}})
    step2 = json.dumps({"action": "tool", "tool": "read_file", "arguments": {"path": "src/service.py"}})
    final_reply = "src contains app.py and service.py. UserService is defined in service.py."
    provider = SequenceMockProvider([step1, step2, final_reply])
    orchestrator = AgentOrchestrator(provider=provider, registry=sample_registry)

    response = orchestrator.process([{"role": "user", "content": "Inspect src directory"}])

    assert response.steps_used == 2
    assert len(response.tool_calls_made) == 2
    assert response.tool_calls_made[0]["tool"] == "list_files"
    assert response.tool_calls_made[1]["tool"] == "read_file"
    assert response.message == final_reply
    assert provider.call_count == 3


def test_orchestrator_max_steps_cap(sample_registry: ToolRegistry) -> None:
    # 2 tool calls, then provider answers on the final prompt
    step_tool = json.dumps({"action": "tool", "tool": "list_files", "arguments": {"path": "."}})
    final_fallback = "Summary based on all gathered information."
    provider = SequenceMockProvider([step_tool, step_tool, final_fallback])
    orchestrator = AgentOrchestrator(
        provider=provider,
        registry=sample_registry,
        max_steps=2,
    )

    response = orchestrator.process([{"role": "user", "content": "Analyze everything"}])

    assert response.steps_used == 2
    assert len(response.tool_calls_made) == 2
    assert response.message == final_fallback
    assert provider.call_count == 3
    last_prompt = provider.recorded_messages[-1]
    assert "maximum number of tool calls" in last_prompt[-1]["content"]


def test_orchestrator_max_steps_tool_call_after_cap_handled(sample_registry: ToolRegistry) -> None:
    # Provider tries to make a tool call even after max steps cap reached
    step_tool = json.dumps({"action": "tool", "tool": "list_files", "arguments": {"path": "."}})
    provider = SequenceMockProvider([step_tool, step_tool, step_tool])
    orchestrator = AgentOrchestrator(
        provider=provider,
        registry=sample_registry,
        max_steps=2,
    )

    response = orchestrator.process([{"role": "user", "content": "Analyze loop"}])

    assert response.steps_used == 2
    assert len(response.tool_calls_made) == 2
    assert "Reached the maximum number of tool calls" in response.message


def test_orchestrator_unknown_tool_handled_gracefully(sample_registry: ToolRegistry) -> None:
    tool_request = json.dumps({
        "action": "tool",
        "tool": "nonexistent_tool",
        "arguments": {"foo": "bar"},
    })
    final_reply = "I noticed the tool is unavailable, so I cannot perform that check."
    provider = SequenceMockProvider([tool_request, final_reply])
    orchestrator = AgentOrchestrator(provider=provider, registry=sample_registry)

    response = orchestrator.process([{"role": "user", "content": "Run nonexistent"}])

    assert response.steps_used == 1
    assert len(response.tool_calls_made) == 1
    assert response.tool_calls_made[0]["tool"] == "nonexistent_tool"
    assert response.tool_calls_made[0]["success"] is False
    assert response.message == final_reply

    # Observation told LLM that tool is not registered
    second_call_messages = provider.recorded_messages[1]
    assert any("TOOL_NOT_FOUND" in msg.get("content", "") for msg in second_call_messages)


def test_orchestrator_tool_failure_passed_to_llm(sample_registry: ToolRegistry) -> None:
    # Request reading a file that doesn't exist
    tool_request = json.dumps({
        "action": "tool",
        "tool": "read_file",
        "arguments": {"path": "does_not_exist.txt"},
    })
    final_reply = "The file does_not_exist.txt was not found."
    provider = SequenceMockProvider([tool_request, final_reply])
    orchestrator = AgentOrchestrator(provider=provider, registry=sample_registry)

    response = orchestrator.process([{"role": "user", "content": "Read ghost file"}])

    assert response.steps_used == 1
    assert response.tool_calls_made[0]["success"] is False
    assert response.message == final_reply
    second_call_messages = provider.recorded_messages[1]
    assert any("FILE_NOT_FOUND" in msg.get("content", "") for msg in second_call_messages)


# ------------------------------------------------------------------
# 4. ChatService Integration with Tool Registry
# ------------------------------------------------------------------

def test_chat_service_without_tools_uses_direct_path() -> None:
    provider = SequenceMockProvider(["Phase 5/6 direct answer"])
    service = ChatService(provider=provider, tool_registry=None)

    req = ChatRequest(message="Hello there")
    resp = service.process_message(req)

    assert resp.message == "Phase 5/6 direct answer"
    assert resp.meta.get("provider") == "mock"
    assert "agent_steps_used" not in resp.meta


def test_chat_service_with_tools_uses_orchestrator(sample_registry: ToolRegistry) -> None:
    tool_request = json.dumps({
        "action": "tool",
        "tool": "search_code",
        "arguments": {"query": "def main", "path": "."},
    })
    final_reply = "I found main defined in src/app.py."
    provider = SequenceMockProvider([tool_request, final_reply])
    service = ChatService(provider=provider, tool_registry=sample_registry)

    req = ChatRequest(message="Where is main defined?")
    resp = service.process_message(req)

    assert resp.message == final_reply
    assert resp.meta["agent_steps_used"] == 1
    assert len(resp.meta["agent_tool_calls"]) == 1
    assert resp.meta["agent_tool_calls"][0]["tool"] == "search_code"
