"""Unit tests for Pydantic domain and API schemas."""

from pydantic import ValidationError as PydanticValidationError
import pytest

from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ErrorDetail,
    ErrorResponse,
    MessageRole,
)


def test_chat_request_valid() -> None:
    """Test creating a valid ChatRequest."""
    req = ChatRequest(message="Hello companion", conversation_id="conv-123")
    assert req.message == "Hello companion"
    assert req.conversation_id == "conv-123"
    assert req.client_metadata is None


def test_chat_request_empty_rejected() -> None:
    """Test that empty string message is rejected by schema validator."""
    with pytest.raises(PydanticValidationError):
        ChatRequest(message="")


def test_chat_message_creation() -> None:
    """Test ChatMessage entity creation and role assignment."""
    msg = ChatMessage(
        role=MessageRole.USER,
        content="Inspect main.ts",
        timestamp="2026-09-22T00:00:00Z",
        metadata={"client": "cli"}
    )
    assert msg.role == MessageRole.USER
    assert msg.content == "Inspect main.ts"
    assert msg.metadata == {"client": "cli"}


def test_chat_response_structure() -> None:
    """Test ChatResponse structure."""
    res = ChatResponse(
        message="I processed your request.",
        source="ai-service",
        conversation_id="conv-abc",
        timestamp="2026-09-22T00:00:00Z",
        status="success",
        meta={"mock": True}
    )
    assert res.status == "success"
    assert res.source == "ai-service"
    assert res.conversation_id == "conv-abc"
    assert res.meta == {"mock": True}


def test_error_response_structure() -> None:
    """Test ErrorResponse structure."""
    err = ErrorResponse(
        error=ErrorDetail(code="TEST_ERROR", message="Something failed")
    )
    assert err.status == "error"
    assert err.error.code == "TEST_ERROR"
    assert err.error.message == "Something failed"
