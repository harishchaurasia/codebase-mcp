"""Tool: suggest_files_for_task -- task decomposition and file mapping."""

from __future__ import annotations

from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult


class SuggestFilesForTaskTool(BaseTool):
    """Decomposes a task into sub-goals, searches for relevant files per
    sub-goal, and returns a structured plan with execution order and
    confidence scores."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="suggest_files_for_task",
            description=(
                "Given a task description, decompose it into sub-goals, map each "
                "sub-goal to relevant files using keyword search and dependency "
                "analysis, and return a structured plan with per-sub-task results, "
                "a deduplicated execution order, and confidence scores."
            ),
            trigger_keywords=[
                "suggest", "recommend", "task", "implement", "feature",
                "change", "modify", "edit", "which files", "where to",
                "refactor", "bug", "fix",
                "decompose", "subtask", "plan", "order", "steps",
            ],
            usage_examples=[
                'suggest_files_for_task(task_description="Add JWT auth", top_n=5)',
                "Which files should I change to add dark mode?",
                "Break down the task: add rate limiting to the API",
            ],
            capabilities=["planning", "search", "dependency-analysis", "reasoning"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        from codebase_mcp.tools._context import get_analyzer

        task_description: str = kwargs["task_description"]
        top_n: int = kwargs.get("top_n", 5)
        analyzer = get_analyzer()
        plan = analyzer.suggest_files_for_task(task_description, top_n=top_n)
        return ToolResult.ok(self.name, plan.model_dump())


tool_instance = SuggestFilesForTaskTool()
