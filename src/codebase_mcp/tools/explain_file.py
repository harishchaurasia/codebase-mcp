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
                "Explain what a specific file does with structured reasoning: its "
                "high-level purpose, classified role in the system, key symbols, "
                "dependencies, a confidence score, and suggested next files to examine. "
                "Includes a reasoning trace showing how the explanation was derived."
            ),
            trigger_keywords=[
                "explain", "describe", "file", "purpose", "what does",
                "symbols", "overview", "understand", "reasoning", "role",
                "confidence", "next",
            ],
            usage_examples=[
                'explain_file(file_path="src/auth/middleware.py")',
                "What does the file utils/helpers.py do?",
                "What is the role of server.py in the system?",
            ],
            capabilities=["explanation", "analysis", "reasoning"],
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
