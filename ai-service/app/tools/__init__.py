"""
Tools package for AI software engineering companion (Phase 7).

Provides the foundation for tool definition, registration, permission checks,
and safe read-only project inspection.
"""

from app.tools.base import PermissionLevel, Tool, ToolError, ToolResult
from app.tools.project_tools import (
    InspectFileTool,
    ListFilesTool,
    ReadFileTool,
    SearchCodeTool,
    create_default_tool_registry,
)
from app.tools.registry import ToolRegistry

__all__ = [
    "InspectFileTool",
    "ListFilesTool",
    "PermissionLevel",
    "ReadFileTool",
    "SearchCodeTool",
    "Tool",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "create_default_tool_registry",
]
