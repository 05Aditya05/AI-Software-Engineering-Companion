"""Unit tests for ChatService — Phase 4 (provider-injected)."""

import pytest

from app.exceptions import LLMProviderError, ValidationError
from app.providers.base import LLMProvider, LLMResponse
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.conversation import ConversationManager
from app.services.prompt import PromptBuilder


class FakeProvider(LLMProvider):
    """Test double: returns a deterministic response without hitting any API."""

    def __init__(self, reply: str = "Fake LLM reply.", model: str = "fake-model") -> None:
        self._reply = reply
        self._model = model
        self.call_count = 0
        self.last_messages: list[dict[str, str]] = []

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        self.call_count += 1
        self.last_messages = messages
        return LLMResponse(text=self._reply, model=self._model, provider="fake")


class FailingProvider(LLMProvider):
    """Test double: always raises LLMProviderError."""

    def __init__(self, code: str = "LLM_PROVIDER_ERROR") -> None:
        self._code = code

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        raise LLMProviderError("Simulated provider failure.", code=self._code)


def _make_service(provider: LLMProvider | None = None) -> ChatService:
    return ChatService(
        conversation_manager=ConversationManager(),
        prompt_builder=PromptBuilder(),
        provider=provider or FakeProvider(),
    )


# ------------------------------------------------------------------
# Happy-path tests
# ------------------------------------------------------------------

def test_process_valid_message_returns_structured_response() -> None:
    """Valid message produces a structured, success ChatResponse."""
    service = _make_service()
    req = ChatRequest(message="Explain dependency injection.", conversation_id="conv-1")
    res = service.process_message(req)

    assert res.status == "success"
    assert res.source == "ai-service"
    assert res.conversation_id == "conv-1"
    assert res.message == "Fake LLM reply."
    assert res.meta is not None
    assert res.meta["provider"] == "fake"
    assert res.meta["model"] == "fake-model"


def test_provider_receives_system_and_user_messages() -> None:
    """Prompt passed to provider includes system and user roles."""
    provider = FakeProvider()
    service = _make_service(provider)
    req = ChatRequest(message="What is TDD?", conversation_id="conv-tdd")
    service.process_message(req)

    roles = [m["role"] for m in provider.last_messages]
    assert "system" in roles
    assert "user" in roles
    assert provider.last_messages[-1]["role"] == "user"
    assert "What is TDD?" in provider.last_messages[-1]["content"]


def test_multi_turn_conversation_history_grows() -> None:
    """Second turn sees prior user+assistant messages in prompt."""
    provider = FakeProvider()
    conv_mgr = ConversationManager()
    service = ChatService(
        conversation_manager=conv_mgr,
        prompt_builder=PromptBuilder(),
        provider=provider,
    )

    req1 = ChatRequest(message="Hello", conversation_id="conv-multi")
    res1 = service.process_message(req1)
    assert res1.conversation_id == "conv-multi"
    assert provider.call_count == 1

    req2 = ChatRequest(message="What did I say?", conversation_id="conv-multi")
    res2 = service.process_message(req2)
    assert res2.conversation_id == "conv-multi"
    assert provider.call_count == 2

    # Second call prompt should include 2 history messages (user + assistant from turn 1)
    assert res2.meta["history_length"] == 2

    history = conv_mgr.get_history("conv-multi")
    assert len(history) == 4  # user, asst, user, asst


def test_conversation_history_preserved_across_turns() -> None:
    """Conversation history accumulated correctly."""
    provider = FakeProvider()
    conv_mgr = ConversationManager()
    service = ChatService(conversation_manager=conv_mgr, provider=provider)

    for i in range(3):
        req = ChatRequest(message=f"Message {i}", conversation_id="conv-hist")
        service.process_message(req)

    history = conv_mgr.get_history("conv-hist")
    assert len(history) == 6  # 3 user + 3 assistant


def test_project_context_included_in_prompt() -> None:
    """project_context is forwarded to prompt builder and reaches provider."""
    provider = FakeProvider()
    service = _make_service(provider)
    req = ChatRequest(message="What stack?", conversation_id="conv-ctx")
    service.process_message(req, project_context="Stack: FastAPI, Next.js")

    system_msg = next(m for m in provider.last_messages if m["role"] == "system")
    assert "FastAPI" in system_msg["content"]


# ------------------------------------------------------------------
# Validation tests
# ------------------------------------------------------------------

def test_empty_message_raises_validation_error() -> None:
    """Whitespace-only message raises domain ValidationError."""
    service = _make_service()
    req = ChatRequest(message="   ")
    with pytest.raises(ValidationError) as exc_info:
        service.process_message(req)
    assert "non-whitespace" in str(exc_info.value)


# ------------------------------------------------------------------
# Provider error propagation tests
# ------------------------------------------------------------------

def test_provider_error_propagates_as_llm_provider_error() -> None:
    """LLMProviderError from provider bubbles up unchanged."""
    service = _make_service(FailingProvider())
    req = ChatRequest(message="Fail please.", conversation_id="conv-fail")
    with pytest.raises(LLMProviderError) as exc_info:
        service.process_message(req)
    assert exc_info.value.code == "LLM_PROVIDER_ERROR"


def test_auth_error_propagates() -> None:
    """Auth error code preserved through service layer."""
    service = _make_service(FailingProvider(code="LLM_AUTH_ERROR"))
    with pytest.raises(LLMProviderError) as exc_info:
        service.process_message(ChatRequest(message="Hi"))
    assert exc_info.value.code == "LLM_AUTH_ERROR"
