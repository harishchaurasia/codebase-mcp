"""Tool: find_codebase_references -- multi-stage search for relevant files."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class FindCodebaseReferencesTool(BaseTool):
    """Searches the analyzed codebase using a three-stage pipeline
    (select → evaluate → refine) with per-result reasoning and confidence."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="find_codebase_references",
            description=(
                "Find files in the codebase most relevant to a natural-language query "
                "or feature description.  Uses a select → evaluate → refine pipeline "
                "with per-signal score breakdowns, dependency-aware re-ranking, "
                "reasoning traces, and confidence scores."
            ),
            trigger_keywords=[
                "find", "search", "references", "relevant", "files",
                "where", "locate", "lookup", "grep", "query",
                "evaluate", "refine", "confidence", "reasoning", "why",
            ],
            usage_examples=[
                'find_codebase_references(query="authentication middleware", top_n=5)',
                "Which files deal with payment processing?",
                "Why was this file selected as relevant?",
            ],
            capabilities=["search", "discovery", "reasoning"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        query: str = kwargs["query"]
        top_n: int = kwargs.get("top_n", 10)
        analyzer = get_analyzer()
        results = analyzer.find_relevant_files(query, top_n=top_n)
        return ToolResult.ok(self.name, {"results": [r.model_dump() for r in results]})


tool_instance = FindCodebaseReferencesTool()
