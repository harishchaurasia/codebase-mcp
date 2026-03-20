"""Minimal deterministic agent loop that drives the ToolRegistry.

The loop follows the pattern:
  plan next step -> select tool -> execute -> observe -> evaluate -> repeat

No LLM calls -- all planning and evaluation is rule-based heuristic.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from codebase_mcp.tools.base import ToolResult
from codebase_mcp.tools.registry import ToolRegistry
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class AgentStep(BaseModel):
    """Record of a single iteration inside the agent loop."""

    iteration: int
    plan: str = Field(description="What the agent decided to do this step")
    selected_tool: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    observation: str = ""
    progress: str = ""
    stop_reason: str | None = None


class AgentLoopConfig(BaseModel):
    """Tuning knobs for the agent loop."""

    max_iterations: int = Field(default=6, ge=1)
    top_n: int = Field(default=5, ge=1)
    stop_on_failure: bool = False


class AgentLoopResult(BaseModel):
    """Everything the agent produced."""

    goal: str
    done: bool = False
    final_result: dict[str, Any] = Field(default_factory=dict)
    trace: list[AgentStep] = Field(default_factory=list)
    iterations: int = 0
    stop_reason: str = ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_agent_loop(
    goal: str,
    directory: str,
    registry: ToolRegistry | None = None,
    config: AgentLoopConfig | None = None,
    should_stop: Callable[[int, list[AgentStep]], bool] | None = None,
) -> AgentLoopResult:
    """Run a minimal agent loop to accomplish *goal* against *directory*.

    Args:
        goal: Natural-language description of what the user wants.
        directory: Absolute path to the codebase to analyze.
        registry: Pre-built registry (created + discovered if None).
        config: Loop parameters (defaults are sensible).
        should_stop: Optional callback ``(iteration, trace) -> bool``
                     for external early-stop control.

    Returns:
        An :class:`AgentLoopResult` with the final output and full trace.
    """
    if registry is None:
        registry = ToolRegistry()
        registry.discover()
    if config is None:
        config = AgentLoopConfig()

    result = AgentLoopResult(goal=goal)
    state = _LoopState(goal=goal, directory=directory, config=config)

    logger.info("agent loop started", goal=goal, max_iter=config.max_iterations)

    for iteration in range(1, config.max_iterations + 1):
        # External early-stop check
        if should_stop and should_stop(iteration, result.trace):
            step = AgentStep(
                iteration=iteration,
                plan="external stop requested",
                selected_tool="",
                stop_reason="external_callback",
            )
            result.trace.append(step)
            result.stop_reason = "external_callback"
            break

        plan = _plan_next_step(state)
        tool_name = _select_tool(state, plan, registry)
        tool_args = _build_tool_args(state, tool_name)

        logger.info(
            "agent step",
            iteration=iteration,
            plan=plan,
            tool=tool_name,
        )

        tool_result = registry.execute(tool_name, **tool_args)
        observation = _summarise_result(tool_result)

        step = AgentStep(
            iteration=iteration,
            plan=plan,
            selected_tool=tool_name,
            tool_input=tool_args,
            success=tool_result.success,
            observation=observation,
        )

        _update_state(state, tool_name, tool_result)

        progress = _evaluate_progress(state)
        step.progress = progress

        logger.info(
            "agent observation",
            iteration=iteration,
            success=tool_result.success,
            progress=progress,
        )

        if config.stop_on_failure and not tool_result.success:
            step.stop_reason = "tool_failure"
            result.trace.append(step)
            result.stop_reason = "tool_failure"
            break

        if _is_done(state):
            step.stop_reason = "goal_complete"
            result.trace.append(step)
            result.stop_reason = "goal_complete"
            break

        result.trace.append(step)
    else:
        result.stop_reason = "max_iterations"

    result.iterations = len(result.trace)
    result.done = result.stop_reason == "goal_complete"
    result.final_result = _build_final_result(state)

    logger.info(
        "agent loop finished",
        iterations=result.iterations,
        done=result.done,
        stop_reason=result.stop_reason,
    )
    return result


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_SEARCH_RE = re.compile(
    r"\b(find|search|where|locate|which|references|grep|lookup)\b",
    re.I,
)
_TASK_RE = re.compile(
    r"\b(add|implement|change|modify|create|build|refactor|fix|update|remove)\b",
    re.I,
)


class _LoopState:
    """Mutable scratchpad tracking what the loop has done so far."""

    def __init__(
        self,
        goal: str,
        directory: str,
        config: AgentLoopConfig,
    ) -> None:
        self.goal = goal
        self.directory = directory
        self.config = config
        self.analyzed = False
        self.searched = False
        self.suggested = False
        self.explained_files: list[str] = []
        self.candidate_files: list[str] = []
        self.last_result: ToolResult | None = None
        self.all_results: dict[str, ToolResult] = {}


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------


def _plan_next_step(state: _LoopState) -> str:
    if not state.analyzed:
        return "Analyze the codebase first"
    if not state.searched and not state.suggested:
        if _TASK_RE.search(state.goal):
            return "Decompose task and suggest files"
        return "Search for files relevant to the goal"
    if state.candidate_files and not state.explained_files:
        return f"Explain top candidate file: {state.candidate_files[0]}"
    if len(state.explained_files) < min(2, len(state.candidate_files)):
        remaining = [f for f in state.candidate_files if f not in state.explained_files]
        if remaining:
            return f"Explain next candidate file: {remaining[0]}"
    return "Gather more context about the goal"


def _select_tool(
    state: _LoopState,
    plan: str,
    registry: ToolRegistry,
) -> str:
    if not state.analyzed:
        return "analyze_repo"
    if "suggest" in plan.lower() or "decompose" in plan.lower():
        return "suggest_files_for_task"
    if "search" in plan.lower():
        return "find_codebase_references"
    if "explain" in plan.lower() and state.candidate_files:
        return "explain_file"

    matches = registry.route(state.goal, top_n=1)
    if matches:
        name = matches[0].name
        if name == "explain_file" and not state.candidate_files:
            pass  # can't explain without candidates
        elif name != "analyze_repo":
            return name

    if _TASK_RE.search(state.goal):
        return "suggest_files_for_task"
    return "find_codebase_references"


def _build_tool_args(state: _LoopState, tool_name: str) -> dict[str, Any]:
    if tool_name == "analyze_repo":
        return {"directory": state.directory}
    if tool_name == "find_codebase_references":
        return {"query": state.goal, "top_n": state.config.top_n}
    if tool_name == "suggest_files_for_task":
        return {"task_description": state.goal, "top_n": state.config.top_n}
    if tool_name == "explain_file":
        remaining = [f for f in state.candidate_files if f not in state.explained_files]
        if remaining:
            path = remaining[0]
        elif state.candidate_files:
            path = state.candidate_files[0]
        else:
            return {"file_path": "__unknown__"}
        return {"file_path": path}
    if tool_name == "get_memory_status":
        return {}
    return {"query": state.goal}


def _summarise_result(result: ToolResult) -> str:
    if not result.success:
        return f"FAILED: {result.error}"
    data = result.data
    if "total_files" in data:
        return f"Analyzed {data['total_files']} files"
    if "results" in data:
        paths = [r.get("file_path", "?") for r in data["results"][:3]]
        return f"Found {len(data['results'])} result(s): {', '.join(paths)}"
    if "subtasks" in data:
        n_st = len(data["subtasks"])
        n_files = len(data.get("execution_order", []))
        return f"Decomposed into {n_st} sub-task(s), {n_files} file(s)"
    if "path" in data:
        return f"Explained {data['path']} (role={data.get('role', '?')})"
    return f"OK ({len(data)} keys)"


def _update_state(
    state: _LoopState,
    tool_name: str,
    result: ToolResult,
) -> None:
    state.last_result = result
    state.all_results[tool_name] = result

    if not result.success:
        return

    if tool_name == "analyze_repo":
        state.analyzed = True

    elif tool_name == "find_codebase_references":
        state.searched = True
        for r in result.data.get("results", []):
            fp = r.get("file_path")
            if fp and fp not in state.candidate_files:
                state.candidate_files.append(fp)

    elif tool_name == "suggest_files_for_task":
        state.suggested = True
        for fp in result.data.get("execution_order", []):
            if fp not in state.candidate_files:
                state.candidate_files.append(fp)

    elif tool_name == "explain_file":
        path = result.data.get("path")
        if path and path not in state.explained_files:
            state.explained_files.append(path)


def _evaluate_progress(state: _LoopState) -> str:
    parts: list[str] = []
    if state.analyzed:
        parts.append("analyzed")
    if state.searched or state.suggested:
        parts.append(f"{len(state.candidate_files)} candidates")
    if state.explained_files:
        parts.append(f"{len(state.explained_files)} explained")
    return ", ".join(parts) if parts else "starting"


def _is_done(state: _LoopState) -> bool:
    if not state.analyzed:
        return False
    has_files = bool(state.candidate_files)
    has_explanation = bool(state.explained_files)
    return has_files and has_explanation


def _build_final_result(state: _LoopState) -> dict[str, Any]:
    out: dict[str, Any] = {"candidate_files": state.candidate_files}
    if state.explained_files:
        out["explained_files"] = state.explained_files
    if "suggest_files_for_task" in state.all_results:
        r = state.all_results["suggest_files_for_task"]
        if r.success:
            out["task_plan"] = r.data
    if "find_codebase_references" in state.all_results:
        r = state.all_results["find_codebase_references"]
        if r.success:
            out["search_results"] = r.data
    for path in state.explained_files:
        if "explain_file" in state.all_results:
            r = state.all_results["explain_file"]
            if r.success:
                out.setdefault("explanations", {})[path] = r.data
    return out
