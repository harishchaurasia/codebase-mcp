"""Tests for individual tool implementations through the registry."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.tools._context import reset_analyzer
from codebase_mcp.tools.registry import ToolRegistry


def _fresh_registry() -> ToolRegistry:
    reset_analyzer()
    reg = ToolRegistry()
    reg.discover()
    return reg


def test_analyze_repo_tool(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    result = reg.execute("analyze_repo", directory=str(tmp_codebase))
    assert result.success
    assert result.data["total_files"] > 0
    assert "languages" in result.data


def test_explain_file_tool(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))
    result = reg.execute("explain_file", file_path="mypackage/utils.py")
    assert result.success
    assert result.data["path"] == "mypackage/utils.py"
    assert result.data["language"] == "python"
    assert len(result.data["symbols"]) > 0
    assert result.data["purpose"] != ""
    assert result.data["role"] != ""
    assert 0.0 <= result.data["confidence"] <= 1.0
    assert isinstance(result.data["reasoning"], list)
    assert len(result.data["reasoning"]) > 0
    assert isinstance(result.data["next_files"], list)


def test_explain_file_not_found(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))
    result = reg.execute("explain_file", file_path="nonexistent.py")
    assert not result.success
    assert "not found" in (result.error or "").lower()


def test_find_codebase_references_tool(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))
    result = reg.execute("find_codebase_references", query="helper function")
    assert result.success
    paths = [r["file_path"] for r in result.data["results"]]
    assert "mypackage/utils.py" in paths


def test_find_codebase_references_empty(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))
    result = reg.execute("find_codebase_references", query="xyznonexistent")
    assert result.success
    assert result.data["results"] == []


def test_suggest_files_for_task_tool(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))
    result = reg.execute(
        "suggest_files_for_task",
        task_description="add helper utilities",
        top_n=3,
    )
    assert result.success
    suggestions = result.data["suggestions"]
    assert len(suggestions) > 0
    paths = [s["file_path"] for s in suggestions]
    assert "mypackage/utils.py" in paths


def test_explain_file_role_detection(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))

    # utils.py -> utility (has "utils" in name)
    r = reg.execute("explain_file", file_path="mypackage/utils.py")
    assert r.success
    assert r.data["role"] == "utility"

    # main.py -> entry_point
    r = reg.execute("explain_file", file_path="mypackage/main.py")
    assert r.success
    assert r.data["role"] == "entry_point"

    # __init__.py -> config (package init)
    r = reg.execute("explain_file", file_path="mypackage/__init__.py")
    assert r.success
    assert r.data["role"] == "config"


def test_explain_file_next_files(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))

    r = reg.execute("explain_file", file_path="mypackage/utils.py")
    assert r.success
    next_files = r.data["next_files"]
    assert isinstance(next_files, list)
    assert len(next_files) > 0
    # main.py and sub/module_a.py both import utils.py, so they should appear
    assert any("main.py" in f for f in next_files)


def test_suggest_files_includes_related(tmp_codebase: Path) -> None:
    reg = _fresh_registry()
    reg.execute("analyze_repo", directory=str(tmp_codebase))
    result = reg.execute(
        "suggest_files_for_task",
        task_description="modify the helper function",
        top_n=3,
    )
    assert result.success
    for s in result.data["suggestions"]:
        if s["file_path"] == "mypackage/utils.py":
            assert len(s["related_files"]) > 0
            break
