"""
API integration tests for Controlled Coding Agent endpoints (Phase 11).

Validates REST contracts, HTTP status codes, approval workflows, anti-tampering verification,
and safe execution via FastAPI TestClient.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_coding_agent_create_proposal(client: TestClient, tmp_path: Path) -> None:
    payload = {
        "title": "Add helper module",
        "description": "Adding helper.py",
        "project_root": str(tmp_path),
        "changes": [
            {
                "path": "helper.py",
                "action": "create",
                "proposed_content": "def help(): pass\n",
            }
        ],
    }

    res = client.post("/api/agent/proposals", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Add helper module"
    assert data["status"] == "proposed"
    assert "content_hash" in data
    assert len(data["changes"]) == 1
    assert "+++ b/helper.py" in data["changes"][0]["diff"]


def test_coding_agent_create_proposal_path_traversal_rejected(client: TestClient, tmp_path: Path) -> None:
    payload = {
        "title": "Malicious Proposal",
        "project_root": str(tmp_path),
        "changes": [
            {
                "path": "../evil.py",
                "action": "create",
                "proposed_content": "bad",
            }
        ],
    }
    res = client.post("/api/agent/proposals", json=payload)
    assert res.status_code == 422 or res.status_code == 400


def test_coding_agent_approve_and_apply_flow(client: TestClient, tmp_path: Path) -> None:
    # 1. Create
    create_res = client.post("/api/agent/proposals", json={
        "title": "Feature release",
        "project_root": str(tmp_path),
        "changes": [
            {
                "path": "feature.txt",
                "action": "create",
                "proposed_content": "feature completed\n",
            }
        ],
    })
    assert create_res.status_code == 201
    proposal_data = create_res.json()
    proposal_id = proposal_data["id"]
    content_hash = proposal_data["content_hash"]

    # 2. Get by ID
    get_res = client.get(f"/api/agent/proposals/{proposal_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == proposal_id

    # 3. Approve with bad hash returns 409
    bad_approve = client.post(
        f"/api/agent/proposals/{proposal_id}/approve",
        json={"content_hash": "wrong_hash"},
    )
    assert bad_approve.status_code == 409

    # 4. Approve with correct hash
    good_approve = client.post(
        f"/api/agent/proposals/{proposal_id}/approve",
        json={"content_hash": content_hash},
    )
    assert good_approve.status_code == 200
    assert good_approve.json()["status"] == "approved"

    # 5. Apply
    apply_res = client.post(
        f"/api/agent/proposals/{proposal_id}/apply",
        json={"content_hash": content_hash, "run_validation": False},
    )
    assert apply_res.status_code == 200
    applied_data = apply_res.json()
    assert applied_data["proposal"]["status"] == "applied"
    assert (tmp_path / "feature.txt").read_text(encoding="utf-8") == "feature completed\n"


def test_coding_agent_apply_stale_state_returns_409(client: TestClient, tmp_path: Path) -> None:
    # 1. Existing file
    f = tmp_path / "file.py"
    f.write_text("v1", encoding="utf-8")

    # 2. Proposal created based on v1
    create_res = client.post("/api/agent/proposals", json={
        "title": "Edit file",
        "project_root": str(tmp_path),
        "changes": [{"path": "file.py", "action": "modify", "proposed_content": "v2"}],
    })
    data = create_res.json()
    p_id = data["id"]
    p_hash = data["content_hash"]

    # 3. Approve
    client.post(f"/api/agent/proposals/{p_id}/approve", json={"content_hash": p_hash})

    # 4. Concurrently modify on disk before apply
    f.write_text("v_external", encoding="utf-8")

    # 5. Apply returns 409 Conflict
    apply_res = client.post(
        f"/api/agent/proposals/{p_id}/apply",
        json={"content_hash": p_hash, "run_validation": False},
    )
    assert apply_res.status_code == 409
    assert "Stale state detected" in apply_res.json()["detail"]
    assert f.read_text(encoding="utf-8") == "v_external"


def test_coding_agent_validate_endpoint_allowlist(client: TestClient, tmp_path: Path) -> None:
    # Safe command should succeed (git status or pytest)
    res_safe = client.post("/api/agent/validate", json={
        "project_root": str(tmp_path),
        "commands": [["git", "status"]],
    })
    assert res_safe.status_code == 200
    results = res_safe.json()
    assert isinstance(results, list)

    # Disallowed command should be rejected with 400 Bad Request
    res_bad = client.post("/api/agent/validate", json={
        "project_root": str(tmp_path),
        "commands": [["rm", "-rf", "/"]],
    })
    assert res_bad.status_code == 400
    assert "not in the allowed validation tool set" in res_bad.json()["detail"]


def test_coding_agent_git_status_endpoint(client: TestClient, tmp_path: Path) -> None:
    res = client.get(f"/api/agent/git-status?project_root={tmp_path}")
    assert res.status_code == 200
    data = res.json()
    assert "is_git" in data
    assert "clean" in data
