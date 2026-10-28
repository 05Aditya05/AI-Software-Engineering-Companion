"""
API integration tests for Long-Term Memory endpoints (Phase 10).

Validates REST contracts, status codes, input validation, 503 database unavailability,
and scoped responses using FastAPI TestClient.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.memory.schemas import MemoryEntry
from app.memory.service import DuplicateMemoryWarning


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_memory_api_503_when_no_db(client: TestClient) -> None:
    """Endpoints must return 503 Service Unavailable when DATABASE_URL is not configured."""
    with patch("app.routers.memory.settings.database_url") as mock_secret:
        mock_secret.get_secret_value.return_value = ""

        # Test POST
        res_post = client.post("/api/memory/", json={
            "category": "bug_fix",
            "content": "A fix",
            "summary": "Fix",
        })
        assert res_post.status_code == 503
        assert "DATABASE_URL is not configured" in res_post.json()["detail"]

        # Test GET
        res_get = client.get("/api/memory/")
        assert res_get.status_code == 503


def test_memory_api_create_validation_error(client: TestClient) -> None:
    """Invalid category or missing required fields should return 422 or 400."""
    with patch("app.routers.memory.settings.database_url") as mock_secret:
        mock_secret.get_secret_value.return_value = "postgresql+asyncpg://user:pass@localhost:5432/db"

        # Invalid category
        res = client.post("/api/memory/", json={
            "category": "not_a_valid_category",
            "content": "Some text",
            "summary": "Summary",
        })
        assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_memory_api_create_and_get_success(client: TestClient) -> None:
    """Test successful POST /api/memory/ and GET /api/memory/{id}."""
    with patch("app.routers.memory.settings.database_url") as mock_secret:
        mock_secret.get_secret_value.return_value = "postgresql+asyncpg://user:pass@localhost:5432/db"

        now = datetime.now(timezone.utc)
        mock_entry = MemoryEntry(
            id=123,
            category="architecture_decision",
            scope="global",
            project_root=None,
            content="Use FastAPI for service endpoints",
            summary="Adopt FastAPI",
            source="user",
            verification_status="unverified",
            confidence="high",
            file_refs=[],
            created_at=now,
            updated_at=now,
        )

        async def fake_session_gen():
            mock_sess = AsyncMock()
            yield mock_sess

        with patch("app.db.get_session", fake_session_gen), \
             patch("app.routers.memory._service.create", new_callable=AsyncMock) as mock_create, \
             patch("app.routers.memory._service.get", new_callable=AsyncMock) as mock_get:

            mock_create.return_value = (mock_entry, None)
            mock_get.return_value = mock_entry

            # POST /api/memory/
            create_payload = {
                "category": "architecture_decision",
                "scope": "global",
                "content": "Use FastAPI for service endpoints",
                "summary": "Adopt FastAPI",
            }
            res_post = client.post("/api/memory/", json=create_payload)
            assert res_post.status_code == 201
            data = res_post.json()
            assert "entry" in data
            assert data["entry"]["id"] == 123
            assert data["entry"]["summary"] == "Adopt FastAPI"

            # GET /api/memory/123
            res_get = client.get("/api/memory/123")
            assert res_get.status_code == 200
            assert res_get.json()["id"] == 123


@pytest.mark.asyncio
async def test_memory_api_get_not_found(client: TestClient) -> None:
    """GET /api/memory/{id} returns 404 when ID does not exist."""
    with patch("app.routers.memory.settings.database_url") as mock_secret:
        mock_secret.get_secret_value.return_value = "postgresql+asyncpg://user:pass@localhost:5432/db"

        async def fake_session_gen():
            yield AsyncMock()

        with patch("app.db.get_session", fake_session_gen), \
             patch("app.routers.memory._service.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            res = client.get("/api/memory/99999")
            assert res.status_code == 404


@pytest.mark.asyncio
async def test_memory_api_delete_success_and_not_found(client: TestClient) -> None:
    """DELETE /api/memory/{id} handles success and not found states."""
    with patch("app.routers.memory.settings.database_url") as mock_secret:
        mock_secret.get_secret_value.return_value = "postgresql+asyncpg://user:pass@localhost:5432/db"

        async def fake_session_gen():
            yield AsyncMock()

        with patch("app.db.get_session", fake_session_gen), \
             patch("app.routers.memory._service.delete", new_callable=AsyncMock) as mock_delete:
            # Success
            mock_delete.return_value = True
            res = client.delete("/api/memory/42?project_root=/my/proj")
            assert res.status_code == 200
            assert res.json()["deleted_id"] == 42

            # Not found
            mock_delete.return_value = False
            res_nf = client.delete("/api/memory/999")
            assert res_nf.status_code == 404
