"""Tool: explain_file -- explain a file's purpose, symbols, and relationships."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class ExplainFileTool(BaseTool):
    """Returns a structured explanation of a single file: what it defines,
    what it imports, and what depends on it."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="explain_file",
            description=(
                "Explain what a specific file does: its module docstring, the classes "
                "and functions it defines, what it imports, and which other files depend "
                "on it.  Useful for understanding a file before editing it."
            ),
            trigger_keywords=[
                "explain", "describe", "file", "purpose", "what does",
                "symbols", "overview", "understand",
            ],
            usage_examples=[
                'explain_file(file_path="src/auth/middleware.py")',
                "What does the file utils/helpers.py do?",
            ],
            capabilities=["explanation", "analysis"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        file_path: str = kwargs["file_path"]
        analyzer = get_analyzer()
        explanation = analyzer.explain_file(file_path)

        if explanation is None:
            return ToolResult.fail(self.name, f"File not found in analysis: {file_path}")

        return ToolResult.ok(self.name, explanation.model_dump())


tool_instance = ExplainFileTool()
