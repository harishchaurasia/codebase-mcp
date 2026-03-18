"""Tool: suggest_files_for_task -- recommend files to examine/edit for a task."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class SuggestFilesForTaskTool(BaseTool):
    """Combines keyword search with dependency analysis to suggest which files
    an agent should look at (or modify) for a given task.  Each suggestion
    includes the file's immediate dependency neighbourhood."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="suggest_files_for_task",
            description=(
                "Given a task description, suggest which files in the codebase an "
                "agent should examine or edit.  Combines relevance search with "
                "dependency graph analysis so the agent sees every file in the "
                "affected neighbourhood, not just direct hits."
            ),
            trigger_keywords=[
                "suggest", "recommend", "task", "implement", "feature",
                "change", "modify", "edit", "which files", "where to",
                "refactor", "bug", "fix",
            ],
            usage_examples=[
                'suggest_files_for_task(task_description="Add rate limiting to the API", top_n=5)',
                "Which files should I change to add dark mode?",
            ],
            capabilities=["planning", "search", "dependency-analysis"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        task_description: str = kwargs["task_description"]
        top_n: int = kwargs.get("top_n", 5)
        analyzer = get_analyzer()
        suggestions = analyzer.suggest_files_for_task(task_description, top_n=top_n)
        return ToolResult.ok(
            self.name,
            {"suggestions": [s.model_dump() for s in suggestions]},
        )


tool_instance = SuggestFilesForTaskTool()
