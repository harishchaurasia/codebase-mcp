"""Integration tests for the MCP server tools."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.mcp_server.server import (
    analyze_codebase,
    explain_file,
    find_relevant_files,
    get_architecture_summary,
    get_dependency_graph,
    get_file_dependencies,
)


def _reset_analyzer() -> None:
    """Reset the global analyzer between tests."""
    import codebase_mcp.mcp_server.server as mod
    mod._analyzer = None


def test_analyze_codebase_returns_summary(tmp_codebase: Path) -> None:
    _reset_analyzer()
    result = analyze_codebase(str(tmp_codebase))
    assert "total_files" in result
    assert result["total_files"] > 0
    assert "languages" in result


def test_get_architecture_summary_after_analyze(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    summary = get_architecture_summary()
    assert summary["total_files"] > 0
    assert len(summary["languages"]) > 0


def test_find_relevant_files_returns_results(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    results = find_relevant_files("helper function")
    assert len(results) > 0
    paths = [r["file_path"] for r in results]
    assert "mypackage/utils.py" in paths


def test_explain_file_returns_info(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    info = explain_file("mypackage/utils.py")
    assert info["path"] == "mypackage/utils.py"
    assert info["language"] == "python"
    assert len(info["symbols"]) > 0


def test_explain_file_not_found(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    info = explain_file("nonexistent.py")
    assert "error" in info


def test_get_file_dependencies(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    deps = get_file_dependencies("mypackage/main.py")
    assert deps["file"] == "mypackage/main.py"
    assert len(deps["imports"]) > 0


def test_get_dependency_graph_full(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    graph = get_dependency_graph()
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0


def test_get_dependency_graph_filtered(tmp_codebase: Path) -> None:
    _reset_analyzer()
    analyze_codebase(str(tmp_codebase))
    graph = get_dependency_graph(filter_path="mypackage/sub")
    assert "filter" in graph
    assert all(
        "mypackage/sub" in n
        for n in graph["nodes"]
        if n.startswith("mypackage/sub")
    )
