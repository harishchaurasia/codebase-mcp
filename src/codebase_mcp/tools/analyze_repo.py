"""Tool: analyze_repo -- scan and analyze a local codebase directory."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class AnalyzeRepoTool(BaseTool):
    """Scans a directory, parses source files, builds a dependency graph, and
    caches the results.  Must be called before any other tool can function."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="analyze_repo",
            description=(
                "Scan and analyze a local codebase directory. Walks the file tree, "
                "parses source files, extracts symbols and imports, builds a dependency "
                "graph, and caches everything for subsequent queries. This must be called "
                "before using any other tool."
            ),
            trigger_keywords=[
                "analyze", "scan", "index", "codebase", "repository", "repo",
                "project", "parse", "load",
            ],
            usage_examples=[
                'analyze_repo(directory="/home/user/my-project")',
                "Analyze the repository at /tmp/my-app so I can ask questions about it.",
            ],
            capabilities=["analysis", "indexing"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        directory: str = kwargs["directory"]
        analyzer = get_analyzer()
        summary = analyzer.analyze(directory)
        return ToolResult.ok(self.name, summary.model_dump())


tool_instance = AnalyzeRepoTool()
