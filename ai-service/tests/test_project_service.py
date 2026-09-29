"""
Tests for ProjectService and Project Understanding context injection (Phase 6).

Verifies safe read-only exploration of repository files, boundary enforcement
(path traversal rejection, directory exclusions, credential file filtering,
size limits), and prompt context assembly.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.project_service import (
    ALLOWED_EXTENSIONS,
    EXCLUDED_DIRS,
    EXCLUDED_FILE_NAMES,
    MAX_FILE_BYTES,
    ProjectService,
)


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Create a temporary directory structure mimicking a real repository."""
    # Top-level priority files
    (tmp_path / "README.md").write_text("# Test Repository\nOverview of project.", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "test-repo", "version": "1.0.0"}', encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi==0.115.0\npydantic>=2.0", encoding="utf-8")

    # Excluded secret files
    (tmp_path / ".env").write_text("SECRET_KEY=supersecret", encoding="utf-8")
    (tmp_path / ".env.local").write_text("LOCAL_SECRET=local", encoding="utf-8")
    (tmp_path / "secrets.json").write_text('{"api_key": "12345"}', encoding="utf-8")

    # Source code directory
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text("console.log('hello');", encoding="utf-8")
    (src / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")

    # Excluded directories
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.js").write_text("// vendor code", encoding="utf-8")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]", encoding="utf-8")

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /bin", encoding="utf-8")

    # Disallowed binary / extension files
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "program.exe").write_bytes(b"MZ\x90")

    return tmp_path


# ------------------------------------------------------------------
# Initialization & Validation Tests
# ------------------------------------------------------------------

def test_init_valid_root(sample_project: Path) -> None:
    """ProjectService initializes successfully with a valid directory."""
    svc = ProjectService(str(sample_project))
    assert svc.root == sample_project.resolve()


def test_init_empty_or_whitespace_raises_value_error() -> None:
    """Empty or whitespace project root is rejected."""
    with pytest.raises(ValueError, match="non-empty path"):
        ProjectService("")
    with pytest.raises(ValueError, match="non-empty path"):
        ProjectService("   ")


def test_init_nonexistent_directory_raises_value_error(tmp_path: Path) -> None:
    """Non-existent path is rejected."""
    fake_path = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        ProjectService(str(fake_path))


def test_init_file_as_root_raises_value_error(sample_project: Path) -> None:
    """A file path supplied as project root is rejected."""
    file_path = sample_project / "README.md"
    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        ProjectService(str(file_path))


# ------------------------------------------------------------------
# Directory Exploration & Exclusion Tests
# ------------------------------------------------------------------

def test_list_structure_returns_relative_paths(sample_project: Path) -> None:
    """Returns sorted relative paths of allowed files and directories."""
    svc = ProjectService(str(sample_project))
    structure = svc.list_structure()

    assert "README.md" in structure
    assert "package.json" in structure
    assert "requirements.txt" in structure
    assert "src/" in structure
    assert "src/index.ts" in structure
    assert "src/app.py" in structure


def test_list_structure_excludes_ignored_directories(sample_project: Path) -> None:
    """Excluded directories (node_modules, .git, .venv) are completely omitted."""
    svc = ProjectService(str(sample_project))
    structure = svc.list_structure()

    for item in structure:
        assert not item.startswith("node_modules")
        assert not item.startswith(".git")
        assert not item.startswith(".venv")


def test_list_structure_excludes_secret_files(sample_project: Path) -> None:
    """Secret files (.env, .env.local, secrets.json) are completely omitted."""
    svc = ProjectService(str(sample_project))
    structure = svc.list_structure()

    assert ".env" not in structure
    assert ".env.local" not in structure
    assert "secrets.json" not in structure


def test_list_structure_excludes_disallowed_extensions(sample_project: Path) -> None:
    """Files without allowed extensions (.bin, .exe) are omitted."""
    svc = ProjectService(str(sample_project))
    structure = svc.list_structure()

    assert "binary.bin" not in structure
    assert "program.exe" not in structure


def test_list_structure_depth_limiting(tmp_path: Path) -> None:
    """Max depth limits how deep directory traversal proceeds."""
    # d1/d2/d3/d4/d5/file.py
    curr = tmp_path
    for i in range(1, 6):
        curr = curr / f"d{i}"
        curr.mkdir()
        (curr / "test.py").write_text("x = 1\n", encoding="utf-8")

    svc = ProjectService(str(tmp_path))
    res_depth_2 = svc.list_structure(max_depth=2)
    # d1/ and d1/d2/ should appear, but d1/d2/d3/ should not
    assert "d1/" in res_depth_2
    assert "d1/d2/" in res_depth_2
    assert "d1/d2/d3/" not in res_depth_2


# ------------------------------------------------------------------
# Safe File Reading Tests
# ------------------------------------------------------------------

def test_read_file_success(sample_project: Path) -> None:
    """Valid text file within project root is read successfully."""
    svc = ProjectService(str(sample_project))
    content = svc.read_file("README.md")
    assert "# Test Repository" in content


def test_read_file_nested(sample_project: Path) -> None:
    """Nested file inside subfolder is read successfully."""
    svc = ProjectService(str(sample_project))
    content = svc.read_file("src/app.py")
    assert "def run():" in content


def test_read_file_directory_raises_is_a_directory_error(sample_project: Path) -> None:
    """Attempting to read a directory as a file raises IsADirectoryError."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(IsADirectoryError):
        svc.read_file("src")


def test_read_file_not_found_raises_file_not_found_error(sample_project: Path) -> None:
    """Non-existent file raises FileNotFoundError."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(FileNotFoundError):
        svc.read_file("missing_file.py")


def test_read_file_path_traversal_escapes_root(sample_project: Path) -> None:
    """Path traversal attempting to escape project root is blocked."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(ValueError, match="Path traversal detected"):
        svc.read_file("../some_parent_file.txt")
    with pytest.raises(ValueError, match="Path traversal detected"):
        svc.read_file("../../windows/system32/cmd.exe")


def test_read_file_empty_path_raises_value_error(sample_project: Path) -> None:
    """Empty path string raises ValueError."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(ValueError, match="non-empty"):
        svc.read_file("")


def test_read_file_excluded_secret_file_raises_value_error(sample_project: Path) -> None:
    """Reading an excluded file (.env, secrets.json) is rejected."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(ValueError, match="not permitted"):
        svc.read_file(".env")
    with pytest.raises(ValueError, match="not permitted"):
        svc.read_file("secrets.json")


def test_read_file_disallowed_extension_raises_value_error(sample_project: Path) -> None:
    """Reading a file with an unpermitted extension is rejected."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(ValueError, match="not in the allowed list"):
        svc.read_file("program.exe")


def test_read_file_oversized_file_raises_value_error(tmp_path: Path) -> None:
    """Reading a file exceeding MAX_FILE_BYTES raises ValueError."""
    svc = ProjectService(str(tmp_path))
    big_file = tmp_path / "big.txt"
    big_file.write_text("x" * (MAX_FILE_BYTES + 1024), encoding="utf-8")

    with pytest.raises(ValueError, match="exceeds maximum size"):
        svc.read_file("big.txt")


# ------------------------------------------------------------------
# Metadata Tests
# ------------------------------------------------------------------

def test_get_file_metadata(sample_project: Path) -> None:
    """Returns accurate file metadata."""
    svc = ProjectService(str(sample_project))
    meta = svc.get_file_metadata("README.md")
    assert meta["path"] == "README.md"
    assert meta["extension"] == ".md"
    assert meta["is_allowed"] is True
    assert isinstance(meta["size_bytes"], int)
    assert meta["size_bytes"] > 0


def test_get_file_metadata_excluded_file(sample_project: Path) -> None:
    """Excluded file has is_allowed False."""
    svc = ProjectService(str(sample_project))
    meta = svc.get_file_metadata(".env")
    assert meta["is_allowed"] is False


def test_get_file_metadata_path_traversal(sample_project: Path) -> None:
    """Metadata request with path traversal raises ValueError."""
    svc = ProjectService(str(sample_project))
    with pytest.raises(ValueError, match="Path traversal detected"):
        svc.get_file_metadata("../outside.txt")


# ------------------------------------------------------------------
# Context Assembly Tests
# ------------------------------------------------------------------

def test_build_context_contains_structure_and_files(sample_project: Path) -> None:
    """build_context includes project structure and priority file contents."""
    svc = ProjectService(str(sample_project))
    context = svc.build_context()

    assert "## Project Structure" in context
    assert "README.md" in context
    assert "## README.md" in context
    assert "# Test Repository" in context
    assert "## package.json" in context
    assert "## requirements.txt" in context


def test_build_context_prioritizes_readme_and_manifests(sample_project: Path) -> None:
    """Priority files are included before regular source code files."""
    svc = ProjectService(str(sample_project))
    context = svc.build_context()

    readme_pos = context.find("## README.md")
    pkg_pos = context.find("## package.json")
    src_pos = context.find("## src/index.ts")

    assert readme_pos != -1
    assert pkg_pos != -1
    assert src_pos != -1
    # README and package.json should come before src/index.ts
    assert readme_pos < src_pos
    assert pkg_pos < src_pos


def test_build_context_budget_truncation(tmp_path: Path) -> None:
    """Large context is safely truncated within character limit."""
    # Create several files that together would be large
    (tmp_path / "README.md").write_text("# Project\n" + "A" * 1000, encoding="utf-8")
    for i in range(10):
        (tmp_path / f"code_{i}.py").write_text(f"# file {i}\n" + "B" * 5000, encoding="utf-8")

    svc = ProjectService(str(tmp_path))
    context = svc.build_context()
    assert len(context) <= 80_000 + 500  # Within bounds


# ------------------------------------------------------------------
# Chat Router Integration with Project Context
# ------------------------------------------------------------------

def test_chat_router_injects_project_context(sample_project: Path) -> None:
    """When settings.project_root is set, chat router injects project context into prompt."""
    from app.main import app
    from app.providers.base import LLMProvider, LLMResponse
    from app.services import chat_service as cs_module

    last_received_messages = []

    class InspectingProvider(LLMProvider):
        def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
            last_received_messages.extend(messages)
            return LLMResponse(text="Analysis complete.", model="fake", provider="fake")

    original_provider = cs_module.default_chat_service._provider
    cs_module.default_chat_service._provider = InspectingProvider()

    try:
        with patch("app.routers.chat.settings.project_root", str(sample_project)):
            client = TestClient(app)
            response = client.post("/api/chat/", json={"message": "Explain this project."})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

            # Check that provider received project context in system prompt
            system_msg = next((m for m in last_received_messages if m["role"] == "system"), None)
            assert system_msg is not None
            assert "--- Project Context ---" in system_msg["content"]
            assert "## Project Structure" in system_msg["content"]
            assert "Test Repository" in system_msg["content"]
    finally:
        cs_module.default_chat_service._provider = original_provider


def test_chat_router_handles_invalid_project_root_gracefully(tmp_path: Path) -> None:
    """If project_root is invalid, chat continues without project context without 500 error."""
    from app.main import app
    from app.providers.base import LLMProvider, LLMResponse
    from app.services import chat_service as cs_module

    class DummyProvider(LLMProvider):
        def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
            return LLMResponse(text="Hello!", model="fake", provider="fake")

    original_provider = cs_module.default_chat_service._provider
    cs_module.default_chat_service._provider = DummyProvider()

    try:
        with patch("app.routers.chat.settings.project_root", str(tmp_path / "non_existent_folder")):
            client = TestClient(app)
            response = client.post("/api/chat/", json={"message": "Hello"})
            assert response.status_code == 200
            assert response.json()["status"] == "success"
    finally:
        cs_module.default_chat_service._provider = original_provider
