"""
Git information tool for ToolRegistry (Phase 12).

Registers a READ_ONLY tool ``git_info`` that allows the AI agent to
inspect git repository state during the agentic reasoning loop.

Supported sub-commands:
  - log: Recent commit history
  - diff: Working tree, staged, or ref-to-ref diffs
  - blame: File-level blame annotations
  - branches: List local and remote branches
  - show: Inspect a specific commit
  - status: Working tree status (delegates to existing Phase 11 utility)

All operations are strictly read-only; no mutations are permitted
through this tool.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.tools.base import PermissionLevel, Tool, ToolResult

logger = logging.getLogger(__name__)


class GitInfoTool(Tool):
    """Read-only git inspection tool for the agent ToolRegistry."""

    def __init__(self, project_root: str) -> None:
        self._project_root = project_root

    @property
    def name(self) -> str:
        return "git_info"

    @property
    def description(self) -> str:
        return (
            "Inspect git repository state: recent commits (log), "
            "file diffs (diff), line-level blame (blame), branch listing "
            "(branches), commit details (show), or working tree status (status). "
            "All operations are read-only."
        )

    @property
    def permission(self) -> PermissionLevel:
        return PermissionLevel.READ_ONLY

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Git sub-command: log, diff, blame, branches, show, or status",
                    "enum": ["log", "diff", "blame", "branches", "show", "status"],
                },
                "path": {
                    "type": "string",
                    "description": "Relative file path (for blame, or to scope diff)",
                    "default": "",
                },
                "ref": {
                    "type": "string",
                    "description": "Git ref / commit hash (for show, or ref_from for diff)",
                    "default": "HEAD",
                },
                "ref_to": {
                    "type": "string",
                    "description": "Target ref (for diff between refs)",
                    "default": "",
                },
                "max_count": {
                    "type": "integer",
                    "description": "Maximum entries for log (default: 10, max: 50)",
                    "default": 10,
                },
                "diff_type": {
                    "type": "string",
                    "description": "Diff type: working, staged, or refs",
                    "default": "working",
                },
            },
            "required": ["command"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        command = params.get("command", "").strip().lower()
        if not command:
            return ToolResult.fail(self.name, "MISSING_PARAMETER", "Parameter 'command' is required.")

        if command not in {"log", "diff", "blame", "branches", "show", "status"}:
            return ToolResult.fail(
                self.name, "INVALID_COMMAND",
                f"Unknown git command: '{command}'. Use: log, diff, blame, branches, show, status"
            )

        try:
            result = self._run_command(command, params)
            return ToolResult.ok(self.name, result)
        except Exception as exc:
            return ToolResult.fail(self.name, "GIT_ERROR", str(exc))

    def _run_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the git command synchronously (bridges to async)."""
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self._dispatch(command, params)).result()
        else:
            return asyncio.run(self._dispatch(command, params))

    async def _dispatch(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Route to the appropriate git service function."""
        if command == "log":
            return await self._handle_log(params)
        elif command == "diff":
            return await self._handle_diff(params)
        elif command == "blame":
            return await self._handle_blame(params)
        elif command == "branches":
            return await self._handle_branches()
        elif command == "show":
            return await self._handle_show(params)
        elif command == "status":
            return await self._handle_status()
        else:
            raise ValueError(f"Unknown command: {command}")

    async def _handle_log(self, params: dict[str, Any]) -> dict[str, Any]:
        from app.git.service import git_log
        max_count = min(max(int(params.get("max_count", 10)), 1), 50)
        result = await git_log(self._project_root, max_count=max_count)
        return result.model_dump(mode="json")

    async def _handle_diff(self, params: dict[str, Any]) -> dict[str, Any]:
        from app.git.service import git_diff
        diff_type = params.get("diff_type", "working")
        ref = params.get("ref", "")
        ref_to = params.get("ref_to", "")
        path = params.get("path", "") or None
        result = await git_diff(
            self._project_root,
            diff_type=diff_type,
            ref_from=ref if ref else None,
            ref_to=ref_to if ref_to else None,
            path=path,
        )
        return result.model_dump(mode="json")

    async def _handle_blame(self, params: dict[str, Any]) -> dict[str, Any]:
        from app.git.service import git_blame
        path = params.get("path", "")
        if not path:
            raise ValueError("Parameter 'path' is required for blame command.")
        result = await git_blame(self._project_root, path)
        # Truncate blame entries for prompt size
        data = result.model_dump(mode="json")
        if len(data.get("entries", [])) > 50:
            data["entries"] = data["entries"][:50]
            data["truncated"] = True
            data["total_lines"] = result.total_lines
        return data

    async def _handle_branches(self) -> dict[str, Any]:
        from app.git.service import git_branches
        result = await git_branches(self._project_root)
        return result.model_dump(mode="json")

    async def _handle_show(self, params: dict[str, Any]) -> dict[str, Any]:
        from app.git.service import git_show
        ref = params.get("ref", "HEAD")
        result = await git_show(self._project_root, ref=ref)
        # Truncate diff text for prompt context
        data = result.model_dump(mode="json")
        if len(data.get("diff_text", "")) > 3000:
            data["diff_text"] = data["diff_text"][:3000] + "\n... [diff truncated]"
        return data

    async def _handle_status(self) -> dict[str, Any]:
        from app.coding_agent.git_safety import inspect_git_status
        result = await inspect_git_status(self._project_root)
        return result.model_dump(mode="json")
