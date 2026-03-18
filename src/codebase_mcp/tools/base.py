"""Base abstractions for the agentic tool system.

Every tool in codebase-mcp inherits from BaseTool and declares a ToolMetadata
descriptor.  This keeps tool *capability declarations* (what an agent needs to
select the right tool) separate from *execution logic* (what the tool actually
does).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolMetadata(BaseModel):
    """Rich descriptor that agents and routers use to discover / select tools."""

    name: str = Field(description="Unique tool identifier (snake_case)")
    description: str = Field(description="One-paragraph purpose statement")
    trigger_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords an agent can match against a user query to pick this tool",
    )
    usage_examples: list[str] = Field(
        default_factory=list,
        description="Concrete example invocations (natural-language or JSON)",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Abstract capability tags (e.g. 'analysis', 'search', 'explanation')",
    )


class ToolResult(BaseModel):
    """Uniform envelope returned by every tool execution."""

    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    tool_name: str = ""
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extra info (timing, cache-hit, etc.)",
    )

    @classmethod
    def ok(cls, tool_name: str, data: dict[str, Any], **meta: Any) -> ToolResult:
        return cls(success=True, data=data, tool_name=tool_name, metadata=meta)

    @classmethod
    def fail(cls, tool_name: str, error: str, **meta: Any) -> ToolResult:
        return cls(success=False, error=error, tool_name=tool_name, metadata=meta)


class BaseTool(ABC):
    """Abstract base for every codebase-mcp tool.

    Subclasses must implement ``metadata`` and ``execute``.  The registry and
    MCP server use these two contracts to auto-discover and expose tools.
    """

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return the static metadata descriptor for this tool."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with validated keyword arguments and return a ToolResult."""

    @property
    def name(self) -> str:
        return self.metadata.name
