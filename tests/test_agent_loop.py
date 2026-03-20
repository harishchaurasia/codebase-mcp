"""Tests for the minimal agent loop."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.agent.loop import (
    AgentLoopConfig,
    AgentLoopResult,
    AgentStep,
    run_agent_loop,
)
from codebase_mcp.tools._context import reset_analyzer
from codebase_mcp.tools.registry import ToolRegistry


def _fresh_registry() -> ToolRegistry:
    reset_analyzer()
    reg = ToolRegistry()
    reg.discover()
    return reg


# -- Basic loop behaviour ---------------------------------------------------


def test_loop_returns_trace_and_result(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="find utility helpers",
        directory=str(tmp_codebase),
        registry=reg,
        config=AgentLoopConfig(max_iterations=6),
    )
    assert isinstance(result, AgentLoopResult)
    assert result.goal == "find utility helpers"
    assert result.iterations > 0
    assert len(result.trace) == result.iterations
    for step in result.trace:
        assert isinstance(step, AgentStep)
        assert step.selected_tool or step.stop_reason


def test_loop_first_step_is_analyze(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="explain auth",
        directory=str(tmp_codebase),
        registry=reg,
    )
    assert result.trace[0].selected_tool == "analyze_repo"


def test_loop_populates_candidate_files(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="find utility helpers",
        directory=str(tmp_codebase),
        registry=reg,
    )
    assert result.final_result.get("candidate_files")


def test_loop_done_when_goal_complete(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="search for helper functions",
        directory=str(tmp_codebase),
        registry=reg,
        config=AgentLoopConfig(max_iterations=10),
    )
    assert result.done is True
    assert result.stop_reason == "goal_complete"


# -- Max-iteration stop -----------------------------------------------------


def test_max_iteration_stop(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="search for helper functions",
        directory=str(tmp_codebase),
        registry=reg,
        config=AgentLoopConfig(max_iterations=1),
    )
    assert result.iterations == 1
    assert result.stop_reason == "max_iterations"
    assert result.done is False


# -- Early-stop callback ----------------------------------------------------


def test_early_stop_callback(tmp_codebase: Path) -> None:
    reg = _fresh_registry()

    def stop_at_2(iteration: int, _trace: list[AgentStep]) -> bool:
        return iteration >= 2

    result = run_agent_loop(
        goal="explain everything",
        directory=str(tmp_codebase),
        registry=reg,
        config=AgentLoopConfig(max_iterations=10),
        should_stop=stop_at_2,
    )
    assert result.stop_reason == "external_callback"
    assert result.iterations <= 2


# -- Stop on failure --------------------------------------------------------


def test_stop_on_failure(tmp_codebase: Path) -> None:
    """When stop_on_failure is set and a tool fails, the loop should halt."""
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="find utility helpers",
        directory=str(tmp_codebase),
        registry=reg,
        config=AgentLoopConfig(max_iterations=10, stop_on_failure=True),
    )
    assert result.iterations > 0
    # Either it completed or any failure caused a stop
    if any(not s.success for s in result.trace):
        assert result.stop_reason == "tool_failure"


# -- Task-oriented goal selects suggest tool --------------------------------


def test_task_goal_uses_suggest(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="add logging to the utility module",
        directory=str(tmp_codebase),
        registry=reg,
    )
    tool_names = [s.selected_tool for s in result.trace]
    assert "suggest_files_for_task" in tool_names


# -- Search-oriented goal uses find tool ------------------------------------


def test_search_goal_uses_find(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = run_agent_loop(
        goal="find where Config is defined",
        directory=str(tmp_codebase),
        registry=reg,
    )
    tool_names = [s.selected_tool for s in result.trace]
    assert "find_codebase_references" in tool_names
