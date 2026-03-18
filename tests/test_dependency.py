"""Tests for the dependency graph builder."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.dependency import build_dependency_graph
from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.core.config import Settings


def test_build_graph_resolves_internal_imports(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]

    graph = build_dependency_graph(analyses, tmp_codebase)

    assert len(graph.nodes) > 0
    edge_pairs = {(e.source, e.target) for e in graph.edges}

    assert ("mypackage/main.py", "mypackage/utils.py") in edge_pairs
    assert ("mypackage/sub/module_a.py", "mypackage/utils.py") in edge_pairs


def test_build_graph_ignores_external_imports(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]
    graph = build_dependency_graph(analyses, tmp_codebase)

    targets = {e.target for e in graph.edges}
    assert "os" not in targets
    assert "pathlib" not in targets


def test_get_dependents_and_dependencies(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]
    graph = build_dependency_graph(analyses, tmp_codebase)

    deps = graph.get_dependencies("mypackage/main.py")
    assert any(e.target == "mypackage/utils.py" for e in deps)

    dependents = graph.get_dependents("mypackage/utils.py")
    assert any(e.source == "mypackage/main.py" for e in dependents)
