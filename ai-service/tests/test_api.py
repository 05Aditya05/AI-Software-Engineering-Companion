"""Integration and API tests for FastAPI endpoints — Phase 4."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.providers.base import LLMProvider, LLMResponse


class FakeProvider(LLMProvider):
    """Deterministic test double for API-layer tests."""

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        return LLMResponse(
            text=f"Echo: {user_msg}",
            model="fake-model",
            provider="fake",
        )


@pytest.fixture()
def client():
    """TestClient with the default ChatService provider replaced by FakeProvider."""
    from app.main import app
    from app.services import chat_service as cs_module

    original_provider = cs_module.default_chat_service._provider
    cs_module.default_chat_service._provider = FakeProvider()
    yield TestClient(app)
    # Restore after each test
    cs_module.default_chat_service._provider = original_provider


def test_root_endpoint(client) -> None:
    """GET / returns basic metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_health_endpoint(client) -> None:
    """GET /api/health/ returns healthy status."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ai-companion-ai-service"


def test_chat_endpoint_valid(client) -> None:
    """POST /api/chat/ returns a structured ChatResponse."""
    payload = {"message": "Hello from API test!"}
    response = client.post("/api/chat/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["source"] == "ai-service"
    assert "conversation_id" in data
    assert data["message"]  # non-empty LLM reply


def test_chat_endpoint_session_continuity(client) -> None:
    """POST /api/chat/ preserves conversation_id across turns."""
    session_id = "test-session-api"
    payload1 = {"message": "Message 1", "conversation_id": session_id}
    res1 = client.post("/api/chat/", json=payload1)
    assert res1.status_code == 200
    assert res1.json()["conversation_id"] == session_id

    payload2 = {"message": "Message 2", "conversation_id": session_id}
    res2 = client.post("/api/chat/", json=payload2)
    assert res2.status_code == 200
    assert res2.json()["conversation_id"] == session_id
    assert res2.json()["meta"]["history_length"] >= 2


def test_chat_endpoint_empty_message(client) -> None:
    """POST /api/chat/ rejects empty message with 422."""
    payload = {"message": ""}
    response = client.post("/api/chat/", json=payload)
    assert response.status_code in (400, 422)


def test_chat_endpoint_whitespace_message(client) -> None:
    """POST /api/chat/ rejects whitespace-only message with 400."""
    payload = {"message": "     "}
    response = client.post("/api/chat/", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_chat_endpoint_provider_error_returns_500(client) -> None:
    """POST /api/chat/ returns 500 when provider raises LLMProviderError."""
    from app.exceptions import LLMProviderError
    from app.providers.base import LLMProvider

    class AlwaysFailProvider(LLMProvider):
        def chat(self, messages):
            raise LLMProviderError("Simulated failure.", code="LLM_PROVIDER_ERROR")

    from app.services import chat_service as cs_module
    original = cs_module.default_chat_service._provider
    cs_module.default_chat_service._provider = AlwaysFailProvider()
    try:
        response = client.post("/api/chat/", json={"message": "test"})
        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "LLM_PROVIDER_ERROR"
    finally:
        cs_module.default_chat_service._provider = original
