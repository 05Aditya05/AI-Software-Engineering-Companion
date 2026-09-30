"""
Tool registry for discovering and executing tools (Phase 7).

Provides registration, lookup, permission validation, and safe execution.
"""

from typing import Any

from app.tools.base import PermissionLevel, Tool, ToolResult


class ToolRegistry:
    """
    Central registry for managing and invoking tools.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance in the registry."""
        if not tool.name or not tool.name.strip():
            raise ValueError("Tool name must be non-empty.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Retrieve a registered tool by name, or None if not found."""
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check whether a tool with the given name is registered."""
        return name in self._tools

    def list_tools(self) -> list[dict[str, Any]]:
        """Return descriptions and schemas of all registered tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "permission": t.permission.value,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def execute(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        max_allowed_permission: PermissionLevel = PermissionLevel.READ_ONLY,
    ) -> ToolResult:
        """
        Safely execute a registered tool by name with permission checking.

        Guarantees that an unhandled exception will never escape this call.
        """
        tool = self.get(name)
        if not tool:
            return ToolResult.fail(
                tool_name=name,
                code="TOOL_NOT_FOUND",
                message=f"Tool '{name}' is not registered in the tool registry.",
            )

        # Enforce permission boundary: READ_ONLY < WRITE < EXECUTE < DESTRUCTIVE
        permission_order = {
            PermissionLevel.READ_ONLY: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.EXECUTE: 3,
            PermissionLevel.DESTRUCTIVE: 4,
        }
        required_level = permission_order.get(tool.permission, 99)
        granted_level = permission_order.get(max_allowed_permission, 1)

        if required_level > granted_level:
            return ToolResult.fail(
                tool_name=name,
                code="PERMISSION_DENIED",
                message=(
                    f"Execution of tool '{name}' requires '{tool.permission.value}' permission, "
                    f"but caller only granted '{max_allowed_permission.value}'."
                ),
            )

        safe_params = params or {}
        try:
            return tool.execute(safe_params)
        except Exception as exc:
            return ToolResult.fail(
                tool_name=name,
                code="TOOL_EXECUTION_ERROR",
                message=f"Unhandled error executing tool '{name}': {exc}",
            )
