"""Tool: analyze_repo -- scan and analyze a local codebase directory."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class AnalyzeRepoTool(BaseTool):
    """Scans a directory, parses source files, builds a dependency graph, and
    caches the results.  Supports incremental re-analysis via memory layer."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="analyze_repo",
            description=(
                "Scan and analyze a local codebase directory. Walks the file tree, "
                "parses source files, extracts symbols and imports, builds a dependency "
                "graph, and caches everything for subsequent queries. Uses persistent "
                "memory to skip unchanged files on re-analysis. Pass force=True to "
                "ignore the cache and do a full rescan."
            ),
            trigger_keywords=[
                "analyze", "scan", "index", "codebase", "repository", "repo",
                "project", "parse", "load", "refresh", "rescan", "force",
            ],
            usage_examples=[
                'analyze_repo(directory="/home/user/my-project")',
                'analyze_repo(directory="/tmp/my-app", force=True)',
                "Analyze the repository at /tmp/my-app so I can ask questions about it.",
            ],
            capabilities=["analysis", "indexing", "caching"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        directory: str = kwargs["directory"]
        force: bool = kwargs.get("force", False)
        analyzer = get_analyzer()
        summary = analyzer.analyze(directory, force=force)
        return ToolResult.ok(self.name, summary.model_dump())


tool_instance = AnalyzeRepoTool()
