"""Tool: get_memory_status -- report cache state, patterns, and staleness."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class MemoryStatusTool(BaseTool):
    """Reports the current state of the repo memory: whether results are cached,
    when the last analysis ran, detected patterns, and how stale the cache is."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="get_memory_status",
            description=(
                "Check the current state of the analysis cache. Reports whether "
                "memory is loaded, when the last analysis was performed, how many "
                "files are cached, detected codebase patterns (frameworks, test "
                "tools, build systems), and a quick staleness check showing how "
                "many files have changed since the last save."
            ),
            trigger_keywords=[
                "memory", "cache", "status", "stale", "patterns",
                "cached", "loaded", "freshness",
            ],
            usage_examples=[
                "get_memory_status()",
                "Is the analysis cache still fresh?",
                "What patterns were detected in the codebase?",
            ],
            capabilities=["introspection", "caching"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        analyzer = get_analyzer()
        status = analyzer.get_memory_status()
        return ToolResult.ok(self.name, status)


tool_instance = MemoryStatusTool()
