"""Unit tests for ChatService business layer."""

import pytest

from app.exceptions import ValidationError
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.conversation import ConversationManager
from app.services.prompt import PromptBuilder


def test_chat_service_process_valid_message() -> None:
    """Test processing a valid message produces structured response and records history."""
    conv_mgr = ConversationManager()
    prompt_builder = PromptBuilder()
    service = ChatService(conversation_manager=conv_mgr, prompt_builder=prompt_builder)

    req = ChatRequest(message="What is the project structure?", conversation_id="conv-service-1")
    res = service.process_message(req)

    assert res.status == "success"
    assert res.source == "ai-service"
    assert res.conversation_id == "conv-service-1"
    assert "What is the project structure?" in res.message
    assert res.meta is not None
    assert res.meta["mock"] is True

    # History should now contain 2 messages: user and assistant
    history = conv_mgr.get_history("conv-service-1")
    assert len(history) == 2
    assert history[0].content == "What is the project structure?"
    assert history[1].content == res.message


def test_chat_service_multi_turn_continuity() -> None:
    """Test that second turn in the same session incorporates prior turns."""
    conv_mgr = ConversationManager()
    service = ChatService(conversation_manager=conv_mgr)

    # Turn 1
    req1 = ChatRequest(message="Hello", conversation_id="conv-multi")
    res1 = service.process_message(req1)
    assert res1.conversation_id == "conv-multi"

    # Turn 2
    req2 = ChatRequest(message="Where was I?", conversation_id="conv-multi")
    res2 = service.process_message(req2)
    assert res2.conversation_id == "conv-multi"
    assert res2.meta["history_length"] == 2  # Saw 2 previous messages (user + asst from turn 1)

    history = conv_mgr.get_history("conv-multi")
    assert len(history) == 4


def test_chat_service_empty_message_raises_validation_error() -> None:
    """Test that empty or whitespace-only messages raise domain ValidationError."""
    service = ChatService()
    req = ChatRequest(message="   ")
    with pytest.raises(ValidationError) as exc_info:
        service.process_message(req)
    assert "at least one non-whitespace" in str(exc_info.value)
