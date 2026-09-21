"""Integration and API tests for FastAPI endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """Test GET / returns basic metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_health_endpoint() -> None:
    """Test GET /api/health/ returns healthy status."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ai-companion-ai-service"


def test_chat_endpoint_valid() -> None:
    """Test POST /api/chat/ returns structured ChatResponse."""
    payload = {"message": "Hello from API test!"}
    response = client.post("/api/chat/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["source"] == "ai-service"
    assert "conversation_id" in data
    assert "Hello from API test!" in data["message"]


def test_chat_endpoint_session_continuity() -> None:
    """Test POST /api/chat/ preserves conversation_id across turns."""
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


def test_chat_endpoint_empty_message() -> None:
    """Test POST /api/chat/ rejects empty message with 422 or 400."""
    payload = {"message": ""}
    response = client.post("/api/chat/", json=payload)
    # FastAPI/Pydantic returns 422 for schema validation failure
    assert response.status_code in (400, 422)


def test_chat_endpoint_whitespace_message() -> None:
    """Test POST /api/chat/ rejects whitespace-only message with 400."""
    payload = {"message": "     "}
    response = client.post("/api/chat/", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "VALIDATION_ERROR"
