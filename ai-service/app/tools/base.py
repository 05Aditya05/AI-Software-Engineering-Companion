"""
Base abstractions for the tool system (Phase 7).

Defines the core Tool interface, execution result structures, and
permission classifications.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PermissionLevel(str, Enum):
    """
    Permission classification for tools.

    Phase 7 strictly implements READ_ONLY tools.
    Future phases may introduce WRITE, EXECUTE, and DESTRUCTIVE levels.
    """

    READ_ONLY = "read_only"
    WRITE = "write"
    EXECUTE = "execute"
    DESTRUCTIVE = "destructive"


class ToolError(BaseModel):
    """Structured tool error payload."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")


class ToolResult(BaseModel):
    """Normalized result envelope returned by all tool executions."""

    success: bool = Field(..., description="True if the tool executed successfully")
    tool: str = Field(..., description="Name of the tool that executed")
    data: dict[str, Any] | list[Any] | None = Field(
        default=None,
        description="Structured output data if execution succeeded",
    )
    error: ToolError | None = Field(
        default=None,
        description="Structured error details if execution failed",
    )

    @classmethod
    def ok(cls, tool_name: str, data: dict[str, Any] | list[Any]) -> "ToolResult":
        """Factory for successful tool executions."""
        return cls(success=True, tool=tool_name, data=data, error=None)

    @classmethod
    def fail(cls, tool_name: str, code: str, message: str) -> "ToolResult":
        """Factory for failed tool executions."""
        return cls(
            success=False,
            tool=tool_name,
            data=None,
            error=ToolError(code=code, message=message),
        )


class Tool(ABC):
    """
    Abstract base class for all tools in the AI companion tool system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable explanation of what the tool does."""

    @property
    @abstractmethod
    def permission(self) -> PermissionLevel:
        """Required permission level to execute this tool."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON-schema dictionary defining expected parameters."""

    @abstractmethod
    def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool with validated parameters and return a ToolResult."""
