"""
Project inspection tools (Phase 7).

Provides safe, read-only tools for inspecting project structure, reading files,
searching code, and retrieving file metadata within the configured project root.
"""

from pathlib import Path
from typing import Any

from app.services.project_service import (
    ALLOWED_EXTENSIONS,
    EXCLUDED_DIRS,
    MAX_FILE_BYTES,
    ProjectService,
)
from app.tools.base import PermissionLevel, Tool, ToolResult
from app.tools.registry import ToolRegistry


class ListFilesTool(Tool):
    """Safely lists files and directories within a given project directory."""

    def __init__(self, project_service: ProjectService) -> None:
        self._svc = project_service

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return (
            "Safely list files and subdirectories within the specified path "
            "relative to the project root. Respects repository exclusions."
        )

    @property
    def permission(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path to list (default: '.')",
                    "default": ".",
                }
            },
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        rel_path = params.get("path", ".") or "."
        try:
            target = self._svc.resolve_safe(rel_path)
        except ValueError as exc:
            return ToolResult.fail(self.name, "PATH_TRAVERSAL", str(exc))

        if not target.exists():
            return ToolResult.fail(
                self.name,
                "PATH_NOT_FOUND",
                f"Directory does not exist: '{rel_path}'",
            )

        if not target.is_dir():
            return ToolResult.fail(
                self.name,
                "NOT_A_DIRECTORY",
                f"Path is a file, not a directory: '{rel_path}'",
            )

        # Check if the target directory itself is excluded
        if target.name in EXCLUDED_DIRS:
            return ToolResult.fail(
                self.name,
                "ACCESS_DENIED",
                f"Access to excluded directory '{target.name}' is not permitted.",
            )

        entries: list[dict[str, Any]] = []
        try:
            children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return ToolResult.fail(
                self.name,
                "PERMISSION_ERROR",
                f"Permission denied accessing directory: '{rel_path}'",
            )

        max_entries = 150
        for child in children:
            if len(entries) >= max_entries:
                break

            child_rel = child.relative_to(self._svc.root).as_posix()

            if child.is_dir():
                if child.name in EXCLUDED_DIRS:
                    continue
                entries.append({
                    "name": child.name,
                    "type": "directory",
                    "path": child_rel + "/",
                })
            elif child.is_file():
                if self._svc.is_excluded_file(child):
                    continue
                if child.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                entries.append({
                    "name": child.name,
                    "type": "file",
                    "path": child_rel,
                    "size_bytes": child.stat().st_size,
                })

        return ToolResult.ok(self.name, {
            "path": rel_path,
            "total_entries": len(entries),
            "limit_reached": len(entries) >= max_entries,
            "entries": entries,
        })


class ReadFileTool(Tool):
    """Safely reads the contents of an allowed text or code file."""

    def __init__(self, project_service: ProjectService) -> None:
        self._svc = project_service

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the text content of a file within the project root. "
            "Enforces allowed file extensions, size limits, and security exclusions."
        )

    @property
    def permission(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to read",
                }
            },
            "required": ["path"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        rel_path = params.get("path")
        if not rel_path or not str(rel_path).strip():
            return ToolResult.fail(
                self.name,
                "MISSING_PARAMETER",
                "Parameter 'path' is required and must be non-empty.",
            )

        try:
            content = self._svc.read_file(str(rel_path).strip())
            return ToolResult.ok(self.name, {
                "path": rel_path,
                "size_bytes": len(content.encode("utf-8")),
                "line_count": len(content.splitlines()),
                "content": content,
            })
        except FileNotFoundError:
            return ToolResult.fail(
                self.name,
                "FILE_NOT_FOUND",
                f"File not found: '{rel_path}'",
            )
        except IsADirectoryError:
            return ToolResult.fail(
                self.name,
                "IS_A_DIRECTORY",
                f"Path is a directory, not a file: '{rel_path}'",
            )
        except ValueError as exc:
            msg = str(exc)
            if "Path traversal detected" in msg:
                code = "PATH_TRAVERSAL"
            elif "not permitted" in msg:
                code = "ACCESS_DENIED"
            elif "not in the allowed list" in msg:
                code = "DISALLOWED_EXTENSION"
            elif "exceeds maximum size" in msg:
                code = "FILE_TOO_LARGE"
            else:
                code = "INVALID_PATH"
            return ToolResult.fail(self.name, code, msg)


class SearchCodeTool(Tool):
    """Searches allowed project text and code files for a string query."""

    def __init__(self, project_service: ProjectService) -> None:
        self._svc = project_service

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return (
            "Search project source files for a text string. "
            "Returns matching file paths, line numbers, and line snippets. "
            "Respects exclusions and result limits."
        )

    @property
    def permission(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text string to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory path to scope the search within (default: '.')",
                    "default": ".",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return (default: 50, max: 100)",
                    "default": 50,
                },
            },
            "required": ["query"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query")
        if not query or not str(query).strip():
            return ToolResult.fail(
                self.name,
                "MISSING_PARAMETER",
                "Parameter 'query' is required and must be non-empty.",
            )

        query_str = str(query).strip()
        search_path = params.get("path", ".") or "."
        try:
            max_results = min(max(int(params.get("max_results", 50)), 1), 100)
        except (ValueError, TypeError):
            max_results = 50

        try:
            target_dir = self._svc.resolve_safe(search_path)
        except ValueError as exc:
            return ToolResult.fail(self.name, "PATH_TRAVERSAL", str(exc))

        if not target_dir.exists():
            return ToolResult.fail(
                self.name,
                "PATH_NOT_FOUND",
                f"Search directory does not exist: '{search_path}'",
            )

        if not target_dir.is_dir():
            return ToolResult.fail(
                self.name,
                "NOT_A_DIRECTORY",
                f"Search path is not a directory: '{search_path}'",
            )

        if target_dir.name in EXCLUDED_DIRS:
            return ToolResult.fail(
                self.name,
                "ACCESS_DENIED",
                f"Access to excluded directory '{target_dir.name}' is not permitted.",
            )

        matches: list[dict[str, Any]] = []
        query_lower = query_str.lower()

        self._walk_and_search(
            current_dir=target_dir,
            query_lower=query_lower,
            matches=matches,
            max_results=max_results,
        )

        return ToolResult.ok(self.name, {
            "query": query_str,
            "path": search_path,
            "total_matches": len(matches),
            "limit_reached": len(matches) >= max_results,
            "matches": matches,
        })

    def _walk_and_search(
        self,
        current_dir: Path,
        query_lower: str,
        matches: list[dict[str, Any]],
        max_results: int,
    ) -> None:
        try:
            children = sorted(current_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        for child in children:
            if len(matches) >= max_results:
                return

            if child.is_dir():
                if child.name in EXCLUDED_DIRS:
                    continue
                self._walk_and_search(child, query_lower, matches, max_results)
            elif child.is_file():
                if self._svc.is_excluded_file(child):
                    continue
                if child.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                try:
                    if child.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = child.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                rel_file = child.relative_to(self._svc.root).as_posix()
                for line_idx, line in enumerate(text.splitlines(), start=1):
                    if query_lower in line.lower():
                        matches.append({
                            "file": rel_file,
                            "line_number": line_idx,
                            "line_content": line.rstrip()[:200],
                        })
                        if len(matches) >= max_results:
                            return


class InspectFileTool(Tool):
    """Returns safe metadata about a project file without full content exposure."""

    def __init__(self, project_service: ProjectService) -> None:
        self._svc = project_service

    @property
    def name(self) -> str:
        return "inspect_file"

    @property
    def description(self) -> str:
        return (
            "Inspect safe metadata for a project file (size, extension, line count, "
            "allowed status) without reading or returning the complete content."
        )

    @property
    def permission(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to inspect",
                }
            },
            "required": ["path"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        rel_path = params.get("path")
        if not rel_path or not str(rel_path).strip():
            return ToolResult.fail(
                self.name,
                "MISSING_PARAMETER",
                "Parameter 'path' is required and must be non-empty.",
            )

        try:
            target = self._svc.resolve_safe(str(rel_path).strip())
        except ValueError as exc:
            return ToolResult.fail(self.name, "PATH_TRAVERSAL", str(exc))

        if not target.exists():
            return ToolResult.fail(
                self.name,
                "FILE_NOT_FOUND",
                f"File not found: '{rel_path}'",
            )

        if target.is_dir():
            return ToolResult.fail(
                self.name,
                "IS_A_DIRECTORY",
                f"Path is a directory, not a file: '{rel_path}'",
            )

        if self._svc.is_excluded_file(target):
            return ToolResult.fail(
                self.name,
                "ACCESS_DENIED",
                f"Access to file '{rel_path}' is not permitted.",
            )

        ext = target.suffix.lower()
        is_allowed = ext in ALLOWED_EXTENSIONS
        size = target.stat().st_size

        line_count = None
        if is_allowed and size <= MAX_FILE_BYTES:
            try:
                line_count = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                line_count = None

        return ToolResult.ok(self.name, {
            "path": rel_path,
            "name": target.name,
            "extension": ext if ext else None,
            "size_bytes": size,
            "line_count": line_count,
            "is_allowed": is_allowed,
        })


def create_default_tool_registry(project_root: str) -> ToolRegistry:
    """
    Factory creating a ToolRegistry pre-populated with Phase 7 read-only tools.

    Phase 9.6 extension: also registers ``semantic_search`` when both
    DATABASE_URL and GEMINI_API_KEY are configured.  If either is absent
    the registry is returned without the semantic-search tool so that the
    existing chat flow is unaffected.
    """
    svc = ProjectService(project_root)
    registry = ToolRegistry()
    registry.register(ListFilesTool(svc))
    registry.register(ReadFileTool(svc))
    registry.register(SearchCodeTool(svc))
    registry.register(InspectFileTool(svc))

    # Phase 9.6 — register semantic search if infrastructure is available
    try:
        from app.config import settings  # noqa: PLC0415
        from app.knowledge.retrieval import RetrievalService  # noqa: PLC0415
        from app.providers.embedding import GeminiEmbeddingProvider  # noqa: PLC0415
        from app.tools.semantic_search_tool import SemanticSearchTool  # noqa: PLC0415

        db_url = settings.database_url.get_secret_value()
        api_key = settings.gemini_api_key
        if db_url and api_key:
            provider = GeminiEmbeddingProvider(
                api_key=api_key,
                model=settings.embedding_model,
            )
            retrieval = RetrievalService(provider)
            registry.register(SemanticSearchTool(retrieval, project_root))
    except Exception:  # noqa: BLE001
        # Never let semantic-search wiring errors break the core tool registry
        pass

    # Integration Bridge — register memory search if DB is configured
    try:
        from app.config import settings  # noqa: PLC0415
        from app.memory.service import MemoryService  # noqa: PLC0415
        from app.tools.memory_tool import SearchMemoryTool  # noqa: PLC0415

        db_url = settings.database_url.get_secret_value()
        if db_url:
            mem_svc = MemoryService()
            registry.register(SearchMemoryTool(mem_svc, project_root))
    except Exception:  # noqa: BLE001
        # Never let memory search wiring errors break the core tool registry
        pass

    # Phase 12 — register git info tool for agent-driven git inspection
    try:
        from app.tools.git_tool import GitInfoTool  # noqa: PLC0415

        registry.register(GitInfoTool(project_root))
    except Exception:  # noqa: BLE001
        # Never let git tool wiring errors break the core tool registry
        pass

    return registry


