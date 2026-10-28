"""
Unit and integration tests for Phase 7 Tool System.

Tests the tool framework, ToolRegistry, permission enforcement, and the four
read-only project inspection tools: list_files, read_file, search_code, inspect_file.
"""

from pathlib import Path

import pytest

from app.services.project_service import MAX_FILE_BYTES, ProjectService
from app.tools import (
    InspectFileTool,
    ListFilesTool,
    PermissionLevel,
    ReadFileTool,
    SearchCodeTool,
    Tool,
    ToolRegistry,
    ToolResult,
    create_default_tool_registry,
)


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Creates a realistic repository filesystem for testing tools."""
    # Root documentation and manifests
    (tmp_path / "README.md").write_text("# Test Repository\nArchitecture overview and setup.", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "test-repo", "version": "1.0.0"}', encoding="utf-8")

    # Source files
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text("import { ChatService } from './chat';\nconst svc = new ChatService();\n", encoding="utf-8")
    (src / "chat.ts").write_text("export class ChatService {\n  process() { return 'ok'; }\n}\n", encoding="utf-8")

    # Nested subfolder
    utils = src / "utils"
    utils.mkdir()
    (utils / "logger.py").write_text("def log(msg: str) -> None:\n    print(f'[LOG] {msg}')\n", encoding="utf-8")

    # Excluded directories
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "secret_module.js").write_text("export const ChatService = 'fake';", encoding="utf-8")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/master", encoding="utf-8")

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin", encoding="utf-8")

    # Excluded secret files
    (tmp_path / ".env").write_text("SECRET_KEY=supersecret123", encoding="utf-8")
    (tmp_path / ".env.local").write_text("LOCAL_SECRET=abc", encoding="utf-8")
    (tmp_path / "secrets.json").write_text('{"password": "secret"}', encoding="utf-8")

    # Binary / disallowed extension files
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
    (tmp_path / "program.exe").write_bytes(b"MZ\x90")

    return tmp_path


@pytest.fixture()
def tool_registry(sample_project: Path) -> ToolRegistry:
    return create_default_tool_registry(str(sample_project))


# ------------------------------------------------------------------
# Permission & Base Model Tests
# ------------------------------------------------------------------

def test_permission_levels_defined() -> None:
    """Ensure all required permission levels are available."""
    assert PermissionLevel.READ_ONLY == "read_only"
    assert PermissionLevel.WRITE == "write"
    assert PermissionLevel.EXECUTE == "execute"
    assert PermissionLevel.DESTRUCTIVE == "destructive"


def test_tool_result_ok() -> None:
    """Test ToolResult.ok factory method."""
    res = ToolResult.ok("sample_tool", {"count": 42})
    assert res.success is True
    assert res.tool == "sample_tool"
    assert res.data == {"count": 42}
    assert res.error is None


def test_tool_result_fail() -> None:
    """Test ToolResult.fail factory method."""
    res = ToolResult.fail("sample_tool", "SAMPLE_ERROR", "Something broke.")
    assert res.success is False
    assert res.tool == "sample_tool"
    assert res.data is None
    assert res.error is not None
    assert res.error.code == "SAMPLE_ERROR"
    assert res.error.message == "Something broke."


# ------------------------------------------------------------------
# ToolRegistry Tests
# ------------------------------------------------------------------

def test_tool_registry_registration_and_lookup() -> None:
    """Can register and retrieve a tool by name."""
    registry = ToolRegistry()

    class DummyTool(Tool):
        @property
        def name(self) -> str:
            return "dummy"

        @property
        def description(self) -> str:
            return "A dummy test tool."

        @property
        def permission(self) -> PermissionLevel:
            return PermissionLevel.READ_ONLY

        @property
        def input_schema(self) -> dict:
            return {"type": "object"}

        def execute(self, params: dict) -> ToolResult:
            return ToolResult.ok(self.name, {"echo": params.get("val")})

    dummy = DummyTool()
    registry.register(dummy)

    assert registry.has_tool("dummy") is True
    assert registry.get("dummy") is dummy
    assert registry.has_tool("unknown") is False
    assert registry.get("unknown") is None


def test_tool_registry_list_tools(tool_registry: ToolRegistry) -> None:
    """list_tools returns at least the four core read-only tools.

    Phase 9.6: semantic_search may also be registered when DATABASE_URL and
    GEMINI_API_KEY are configured, so the count can be 4 or 5.
    """
    tools = tool_registry.list_tools()
    tool_names = [t["name"] for t in tools]

    assert len(tools) >= 4  # 4 core + optional semantic_search
    assert "list_files" in tool_names
    assert "read_file" in tool_names
    assert "search_code" in tool_names
    assert "inspect_file" in tool_names

    for t in tools:
        assert t["permission"] == "read_only"
        assert "description" in t
        assert "input_schema" in t


def test_tool_registry_execute_unknown_tool(tool_registry: ToolRegistry) -> None:
    """Invoking an unregistered tool returns structured TOOL_NOT_FOUND error."""
    res = tool_registry.execute("non_existent_tool", {})
    assert res.success is False
    assert res.tool == "non_existent_tool"
    assert res.error.code == "TOOL_NOT_FOUND"


def test_tool_registry_empty_tool_name_rejected() -> None:
    """Registering a tool with an empty name raises ValueError."""
    registry = ToolRegistry()

    class NamelessTool(Tool):
        @property
        def name(self) -> str:
            return ""

        @property
        def description(self) -> str:
            return "desc"

        @property
        def permission(self) -> PermissionLevel:
            return PermissionLevel.READ_ONLY

        @property
        def input_schema(self) -> dict:
            return {}

        def execute(self, params: dict) -> ToolResult:
            return ToolResult.ok("", {})

    with pytest.raises(ValueError, match="non-empty"):
        registry.register(NamelessTool())


# ------------------------------------------------------------------
# Tool 1: list_files Tests
# ------------------------------------------------------------------

def test_list_files_root(tool_registry: ToolRegistry) -> None:
    """list_files at project root lists top-level files and folders."""
    res = tool_registry.execute("list_files", {"path": "."})
    assert res.success is True
    assert res.tool == "list_files"
    names = [e["name"] for e in res.data["entries"]]

    assert "README.md" in names
    assert "package.json" in names
    assert "src" in names
    # Excluded directories and secret files must not appear
    assert "node_modules" not in names
    assert ".git" not in names
    assert ".venv" not in names
    assert ".env" not in names
    assert "secrets.json" not in names


def test_list_files_valid_subdirectory(tool_registry: ToolRegistry) -> None:
    """list_files on a subdirectory lists its contents."""
    res = tool_registry.execute("list_files", {"path": "src"})
    assert res.success is True
    names = [e["name"] for e in res.data["entries"]]
    assert "index.ts" in names
    assert "chat.ts" in names
    assert "utils" in names


def test_list_files_nonexistent_path(tool_registry: ToolRegistry) -> None:
    """list_files returns PATH_NOT_FOUND for non-existent path."""
    res = tool_registry.execute("list_files", {"path": "invalid/folder"})
    assert res.success is False
    assert res.error.code == "PATH_NOT_FOUND"


def test_list_files_traversal_blocked(tool_registry: ToolRegistry) -> None:
    """list_files rejects attempts to escape project root."""
    res = tool_registry.execute("list_files", {"path": "../../windows"})
    assert res.success is False
    assert res.error.code == "PATH_TRAVERSAL"


def test_list_files_excluded_directory_access_denied(tool_registry: ToolRegistry) -> None:
    """Directly targeting an excluded directory returns ACCESS_DENIED."""
    res = tool_registry.execute("list_files", {"path": "node_modules"})
    assert res.success is False
    assert res.error.code == "ACCESS_DENIED"


def test_list_files_file_target_rejected(tool_registry: ToolRegistry) -> None:
    """list_files called on a file returns NOT_A_DIRECTORY."""
    res = tool_registry.execute("list_files", {"path": "README.md"})
    assert res.success is False
    assert res.error.code == "NOT_A_DIRECTORY"


# ------------------------------------------------------------------
# Tool 2: read_file Tests
# ------------------------------------------------------------------

def test_read_file_success(tool_registry: ToolRegistry) -> None:
    """read_file returns content and metadata for valid text file."""
    res = tool_registry.execute("read_file", {"path": "README.md"})
    assert res.success is True
    assert res.tool == "read_file"
    assert "# Test Repository" in res.data["content"]
    assert res.data["size_bytes"] > 0
    assert res.data["line_count"] >= 2


def test_read_file_nested(tool_registry: ToolRegistry) -> None:
    """read_file reads nested file successfully."""
    res = tool_registry.execute("read_file", {"path": "src/chat.ts"})
    assert res.success is True
    assert "export class ChatService" in res.data["content"]


def test_read_file_missing_parameter(tool_registry: ToolRegistry) -> None:
    """read_file returns MISSING_PARAMETER if path omitted or empty."""
    res = tool_registry.execute("read_file", {})
    assert res.success is False
    assert res.error.code == "MISSING_PARAMETER"


def test_read_file_not_found(tool_registry: ToolRegistry) -> None:
    """read_file returns FILE_NOT_FOUND for non-existent file."""
    res = tool_registry.execute("read_file", {"path": "missing.py"})
    assert res.success is False
    assert res.error.code == "FILE_NOT_FOUND"


def test_read_file_is_a_directory(tool_registry: ToolRegistry) -> None:
    """read_file returns IS_A_DIRECTORY if target is a folder."""
    res = tool_registry.execute("read_file", {"path": "src"})
    assert res.success is False
    assert res.error.code == "IS_A_DIRECTORY"


def test_read_file_traversal_blocked(tool_registry: ToolRegistry) -> None:
    """read_file blocks directory traversal."""
    res = tool_registry.execute("read_file", {"path": "../outside.txt"})
    assert res.success is False
    assert res.error.code == "PATH_TRAVERSAL"


def test_read_file_secret_excluded(tool_registry: ToolRegistry) -> None:
    """read_file rejects .env and secret files."""
    res = tool_registry.execute("read_file", {"path": ".env"})
    assert res.success is False
    assert res.error.code == "ACCESS_DENIED"

    res_local = tool_registry.execute("read_file", {"path": ".env.local"})
    assert res_local.success is False
    assert res_local.error.code == "ACCESS_DENIED"


def test_read_file_disallowed_extension(tool_registry: ToolRegistry) -> None:
    """read_file rejects files with unapproved extensions."""
    res = tool_registry.execute("read_file", {"path": "program.exe"})
    assert res.success is False
    assert res.error.code == "DISALLOWED_EXTENSION"


def test_read_file_oversized_file(sample_project: Path, tool_registry: ToolRegistry) -> None:
    """read_file rejects files exceeding MAX_FILE_BYTES."""
    big_file = sample_project / "large.txt"
    big_file.write_text("A" * (MAX_FILE_BYTES + 500), encoding="utf-8")

    res = tool_registry.execute("read_file", {"path": "large.txt"})
    assert res.success is False
    assert res.error.code == "FILE_TOO_LARGE"


# ------------------------------------------------------------------
# Tool 3: search_code Tests
# ------------------------------------------------------------------

def test_search_code_finds_matches(tool_registry: ToolRegistry) -> None:
    """search_code finds matching query across repository files."""
    res = tool_registry.execute("search_code", {"query": "ChatService"})
    assert res.success is True
    assert res.tool == "search_code"
    assert res.data["total_matches"] >= 2

    files_matched = {m["file"] for m in res.data["matches"]}
    assert "src/index.ts" in files_matched
    assert "src/chat.ts" in files_matched

    # Verify line structure
    first_match = res.data["matches"][0]
    assert "file" in first_match
    assert "line_number" in first_match
    assert "line_content" in first_match


def test_search_code_case_insensitive(tool_registry: ToolRegistry) -> None:
    """search_code is case-insensitive by default."""
    res = tool_registry.execute("search_code", {"query": "chatservice"})
    assert res.success is True
    assert res.data["total_matches"] >= 2


def test_search_code_no_matches(tool_registry: ToolRegistry) -> None:
    """search_code returns empty matches when nothing matches query."""
    res = tool_registry.execute("search_code", {"query": "NonExistentString12345"})
    assert res.success is True
    assert res.data["total_matches"] == 0
    assert len(res.data["matches"]) == 0


def test_search_code_path_scoping(tool_registry: ToolRegistry) -> None:
    """search_code scopes search to specified subdirectory."""
    res = tool_registry.execute("search_code", {"query": "log", "path": "src/utils"})
    assert res.success is True
    files_matched = {m["file"] for m in res.data["matches"]}
    assert "src/utils/logger.py" in files_matched
    assert "src/chat.ts" not in files_matched


def test_search_code_skips_excluded_directories(tool_registry: ToolRegistry) -> None:
    """search_code never searches inside excluded directories (e.g., node_modules)."""
    # node_modules/secret_module.js contains "ChatService", but must NOT be matched
    res = tool_registry.execute("search_code", {"query": "secret_module"})
    assert res.success is True
    assert res.data["total_matches"] == 0

    res_cs = tool_registry.execute("search_code", {"query": "ChatService"})
    files_matched = [m["file"] for m in res_cs.data["matches"]]
    for f in files_matched:
        assert not f.startswith("node_modules")


def test_search_code_result_limit(sample_project: Path, tool_registry: ToolRegistry) -> None:
    """search_code respects max_results parameter."""
    many_matches = sample_project / "many.txt"
    many_matches.write_text("\n".join(f"match line {i}" for i in range(50)), encoding="utf-8")

    res = tool_registry.execute("search_code", {"query": "match", "max_results": 5})
    assert res.success is True
    assert len(res.data["matches"]) == 5
    assert res.data["limit_reached"] is True


def test_search_code_missing_query(tool_registry: ToolRegistry) -> None:
    """search_code requires a non-empty query parameter."""
    res = tool_registry.execute("search_code", {"query": ""})
    assert res.success is False
    assert res.error.code == "MISSING_PARAMETER"


def test_search_code_traversal_blocked(tool_registry: ToolRegistry) -> None:
    """search_code blocks path traversal in search path."""
    res = tool_registry.execute("search_code", {"query": "test", "path": "../../outside"})
    assert res.success is False
    assert res.error.code == "PATH_TRAVERSAL"


# ------------------------------------------------------------------
# Tool 4: inspect_file Tests
# ------------------------------------------------------------------

def test_inspect_file_valid(tool_registry: ToolRegistry) -> None:
    """inspect_file returns accurate metadata without exposing full content."""
    res = tool_registry.execute("inspect_file", {"path": "src/chat.ts"})
    assert res.success is True
    assert res.tool == "inspect_file"
    assert res.data["name"] == "chat.ts"
    assert res.data["extension"] == ".ts"
    assert res.data["size_bytes"] > 0
    assert res.data["line_count"] >= 3
    assert res.data["is_allowed"] is True
    # Ensure raw file content is NOT exposed in inspect_file
    assert "content" not in res.data


def test_inspect_file_not_found(tool_registry: ToolRegistry) -> None:
    """inspect_file returns FILE_NOT_FOUND for non-existent file."""
    res = tool_registry.execute("inspect_file", {"path": "non_existent.py"})
    assert res.success is False
    assert res.error.code == "FILE_NOT_FOUND"


def test_inspect_file_on_directory_rejected(tool_registry: ToolRegistry) -> None:
    """inspect_file returns IS_A_DIRECTORY if target is a directory."""
    res = tool_registry.execute("inspect_file", {"path": "src"})
    assert res.success is False
    assert res.error.code == "IS_A_DIRECTORY"


def test_inspect_file_secret_excluded(tool_registry: ToolRegistry) -> None:
    """inspect_file rejects sensitive/secret files."""
    res = tool_registry.execute("inspect_file", {"path": ".env"})
    assert res.success is False
    assert res.error.code == "ACCESS_DENIED"


def test_inspect_file_traversal_blocked(tool_registry: ToolRegistry) -> None:
    """inspect_file blocks directory traversal."""
    res = tool_registry.execute("inspect_file", {"path": "../outside.txt"})
    assert res.success is False
    assert res.error.code == "PATH_TRAVERSAL"


# ------------------------------------------------------------------
# End-to-End Tool Integration Verification
# ------------------------------------------------------------------

def test_tool_chain_integration_scenario(tool_registry: ToolRegistry) -> None:
    """
    Simulates a realistic tool exploration workflow:
    1. list_files to discover structure
    2. search_code to locate a specific class
    3. inspect_file to check file size and line count
    4. read_file to inspect the implementation
    """
    # Step 1: list files at root
    list_res = tool_registry.execute("list_files", {"path": "."})
    assert list_res.success is True
    assert any(e["name"] == "src" for e in list_res.data["entries"])

    # Step 2: search for ChatService
    search_res = tool_registry.execute("search_code", {"query": "ChatService"})
    assert search_res.success is True
    assert len(search_res.data["matches"]) >= 1
    target_file = search_res.data["matches"][0]["file"]

    # Step 3: inspect the found file
    inspect_res = tool_registry.execute("inspect_file", {"path": target_file})
    assert inspect_res.success is True
    assert inspect_res.data["is_allowed"] is True

    # Step 4: read the file
    read_res = tool_registry.execute("read_file", {"path": target_file})
    assert read_res.success is True
    assert "ChatService" in read_res.data["content"]
