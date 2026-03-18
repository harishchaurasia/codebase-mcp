"""Tool: find_codebase_references -- keyword search for relevant files."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class FindCodebaseReferencesTool(BaseTool):
    """Searches the analyzed codebase for files relevant to a natural-language
    query using keyword-based TF-IDF scoring over paths, symbols, and docstrings."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="find_codebase_references",
            description=(
                "Find files in the codebase most relevant to a natural-language query "
                "or feature description.  Uses keyword scoring over file paths, symbol "
                "names, and docstrings.  Returns ranked results with context."
            ),
            trigger_keywords=[
                "find", "search", "references", "relevant", "files",
                "where", "locate", "lookup", "grep", "query",
            ],
            usage_examples=[
                'find_codebase_references(query="authentication middleware", top_n=5)',
                "Which files deal with payment processing?",
            ],
            capabilities=["search", "discovery"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        query: str = kwargs["query"]
        top_n: int = kwargs.get("top_n", 10)
        analyzer = get_analyzer()
        results = analyzer.find_relevant_files(query, top_n=top_n)
        return ToolResult.ok(self.name, {"results": [r.model_dump() for r in results]})


tool_instance = FindCodebaseReferencesTool()
