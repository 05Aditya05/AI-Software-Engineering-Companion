"""
Phase 5 tests — Conversational AI Assistant behaviour.

Verifies that the assistant is properly configured as an SE companion:
system instruction is applied, multi-turn context is maintained,
validation still works, and provider failures are surfaced cleanly.

All tests use FakeProvider — no real API key required.
"""

import pytest

from app.config import settings
from app.exceptions import LLMProviderError, ValidationError
from app.providers.base import LLMProvider, LLMResponse
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.conversation import ConversationManager
from app.services.prompt import PromptBuilder


class CapturingProvider(LLMProvider):
    """Records every chat() call for assertion in tests."""

    def __init__(self, reply: str = "SE companion reply.") -> None:
        self._reply = reply
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        self.calls.append(list(messages))
        return LLMResponse(text=self._reply, model="fake", provider="fake")


def _make_service(provider: LLMProvider | None = None) -> tuple[ChatService, LLMProvider]:
    p = provider or CapturingProvider()
    svc = ChatService(
        conversation_manager=ConversationManager(),
        prompt_builder=PromptBuilder(),
        provider=p,
    )
    return svc, p


# ------------------------------------------------------------------
# System instruction tests
# ------------------------------------------------------------------

def test_system_instruction_is_sent_to_provider() -> None:
    """Every chat call includes the configured system instruction."""
    svc, provider = _make_service()
    assert isinstance(provider, CapturingProvider)

    svc.process_message(ChatRequest(message="What is hexagonal architecture?"))

    assert len(provider.calls) == 1
    roles = [m["role"] for m in provider.calls[0]]
    assert "system" in roles
    system_content = next(m["content"] for m in provider.calls[0] if m["role"] == "system")
    assert len(system_content) > 0


def test_system_instruction_contains_se_companion_persona() -> None:
    """Default system prompt mentions SE companion role."""
    prompt = settings.default_system_prompt
    assert "Software Engineering Companion" in prompt


def test_system_instruction_disavows_file_access() -> None:
    """System prompt explicitly states it does NOT have project file access by default."""
    prompt = settings.default_system_prompt
    # The prompt must warn it cannot claim project knowledge unless context is provided
    assert "project" in prompt.lower()
    assert "not" in prompt.lower() or "do not" in prompt.lower() or "unless" in prompt.lower()


# ------------------------------------------------------------------
# Natural-language SE question tests
# ------------------------------------------------------------------

def test_engineering_question_gets_response() -> None:
    """SE question returns a structured success response."""
    svc, _ = _make_service(CapturingProvider("Use dependency injection."))
    req = ChatRequest(message="How should I structure my service layer?")
    res = svc.process_message(req)

    assert res.status == "success"
    assert res.message == "Use dependency injection."
    assert res.conversation_id


def test_conversation_id_preserved() -> None:
    """conversation_id is preserved across calls."""
    svc, _ = _make_service()
    req = ChatRequest(message="Explain TDD", conversation_id="se-conv-1")
    res = svc.process_message(req)
    assert res.conversation_id == "se-conv-1"


# ------------------------------------------------------------------
# Multi-turn conversation tests
# ------------------------------------------------------------------

def test_multi_turn_context_accumulates() -> None:
    """Provider receives growing history across multiple turns."""
    provider = CapturingProvider()
    svc, _ = _make_service(provider)
    conv_id = "multi-turn-se"

    svc.process_message(ChatRequest(message="What is SOLID?", conversation_id=conv_id))
    svc.process_message(ChatRequest(message="Give me the S specifically.", conversation_id=conv_id))
    svc.process_message(ChatRequest(message="Can you show an example?", conversation_id=conv_id))

    # Third call should see 4 history messages (2 turns × 2 each)
    third_call = provider.calls[2]
    history_messages = [m for m in third_call if m["role"] in ("user", "assistant")]
    assert len(history_messages) >= 4


def test_same_conversation_id_routes_to_same_session() -> None:
    """Two calls with same conversation_id share history."""
    provider = CapturingProvider()
    conv_mgr = ConversationManager()
    svc = ChatService(
        conversation_manager=conv_mgr,
        prompt_builder=PromptBuilder(),
        provider=provider,
    )

    svc.process_message(ChatRequest(message="Hello", conversation_id="shared-conv"))
    svc.process_message(ChatRequest(message="Continue", conversation_id="shared-conv"))

    history = conv_mgr.get_history("shared-conv")
    assert len(history) == 4  # user, assistant, user, assistant


def test_different_conversation_ids_are_isolated() -> None:
    """Two different conversation IDs have independent history."""
    conv_mgr = ConversationManager()
    provider = CapturingProvider()
    svc = ChatService(conversation_manager=conv_mgr, provider=provider)

    svc.process_message(ChatRequest(message="Conv A message", conversation_id="conv-a"))
    svc.process_message(ChatRequest(message="Conv B message", conversation_id="conv-b"))

    history_a = conv_mgr.get_history("conv-a")
    history_b = conv_mgr.get_history("conv-b")
    assert len(history_a) == 2
    assert len(history_b) == 2


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def test_validation_still_works_in_phase5() -> None:
    """Empty message still raises ValidationError after Phase 5 changes."""
    svc, _ = _make_service()
    with pytest.raises(ValidationError):
        svc.process_message(ChatRequest(message="  "))


# ------------------------------------------------------------------
# Provider failure handling
# ------------------------------------------------------------------

def test_provider_failure_raises_llm_error() -> None:
    """Provider failure surfaces as LLMProviderError (not a raw exception)."""

    class FailProvider(LLMProvider):
        def chat(self, messages):
            raise LLMProviderError("Upstream error.", code="LLM_SERVER_ERROR")

    svc, _ = _make_service(FailProvider())
    with pytest.raises(LLMProviderError) as exc_info:
        svc.process_message(ChatRequest(message="Fail", conversation_id="fail-conv"))
    assert exc_info.value.code == "LLM_SERVER_ERROR"


# ------------------------------------------------------------------
# API contract tests (via TestClient)
# ------------------------------------------------------------------

def test_api_contract_preserved() -> None:
    """The /api/chat/ endpoint still returns the expected JSON shape."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import chat_service as cs_module

    original = cs_module.default_chat_service._provider
    cs_module.default_chat_service._provider = CapturingProvider("All good.")
    try:
        client = TestClient(app)
        res = client.post("/api/chat/", json={"message": "What is a microservice?"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["source"] == "ai-service"
        assert "conversation_id" in data
        assert "timestamp" in data
        assert data["message"] == "All good."
    finally:
        cs_module.default_chat_service._provider = original
