"""Integration tests for the MCP server tool wrappers."""

from __future__ import annotations

from pathlib import Path

import codebase_mcp.mcp_server.server as server_mod
from codebase_mcp.mcp_server.server import (
    analyze_repo,
    explain_file,
    find_codebase_references,
    list_tools,
    route_query,
    suggest_files_for_task,
)


def _reset() -> None:
    from codebase_mcp.tools._context import reset_analyzer

    reset_analyzer()
    server_mod._registry = None


def test_analyze_repo_returns_summary(tmp_codebase: Path) -> None:
    _reset()
    result = analyze_repo(str(tmp_codebase))
    assert result["success"]
    assert result["data"]["total_files"] > 0


def test_explain_file_after_analyze(tmp_codebase: Path) -> None:
    _reset()
    analyze_repo(str(tmp_codebase))
    result = explain_file("mypackage/utils.py")
    assert result["success"]
    data = result["data"]
    assert data["path"] == "mypackage/utils.py"
    assert len(data["symbols"]) > 0
    assert data["purpose"] != ""
    assert data["role"] == "utility"
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["reasoning"], list)
    assert len(data["reasoning"]) > 0
    assert isinstance(data["next_files"], list)


def test_explain_file_not_found(tmp_codebase: Path) -> None:
    _reset()
    analyze_repo(str(tmp_codebase))
    result = explain_file("nonexistent.py")
    assert not result["success"]


def test_find_codebase_references(tmp_codebase: Path) -> None:
    _reset()
    analyze_repo(str(tmp_codebase))
    result = find_codebase_references("helper function")
    assert result["success"]
    results = result["data"]["results"]
    paths = [r["file_path"] for r in results]
    assert "mypackage/utils.py" in paths

    top = results[0]
    assert 0.0 <= top["confidence"] <= 1.0
    assert isinstance(top["reasoning"], list)
    assert len(top["reasoning"]) > 0
    assert "match_breakdown" in top
    bd = top["match_breakdown"]
    assert "keyword_score" in bd
    assert "dependency_boost" in bd


def test_suggest_files_for_task(tmp_codebase: Path) -> None:
    _reset()
    analyze_repo(str(tmp_codebase))
    result = suggest_files_for_task("add helper utilities")
    assert result["success"]
    data = result["data"]
    assert "subtasks" in data
    assert len(data["subtasks"]) > 0
    assert "execution_order" in data
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["reasoning"], list)


def test_list_tools_returns_metadata() -> None:
    _reset()
    tools = list_tools()
    assert isinstance(tools, list)
    names = {t["name"] for t in tools}
    assert "analyze_repo" in names
    assert "explain_file" in names
    assert "find_codebase_references" in names
    assert "suggest_files_for_task" in names
    for t in tools:
        assert "trigger_keywords" in t
        assert "usage_examples" in t


def test_route_query_finds_matching_tools(tmp_codebase: Path) -> None:
    _reset()
    matches = route_query("analyze scan repository")
    assert len(matches) > 0
    assert matches[0]["name"] == "analyze_repo"


def test_route_query_for_search(tmp_codebase: Path) -> None:
    _reset()
    matches = route_query("find files relevant to authentication")
    names = [m["name"] for m in matches]
    assert "find_codebase_references" in names
