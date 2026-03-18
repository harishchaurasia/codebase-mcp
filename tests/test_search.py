"""Tests for the keyword-based search and refined pipeline."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.analyzers.search import find_relevant, find_relevant_refined
from codebase_mcp.core.config import Settings


def _build_analyses(tmp_codebase: Path, default_settings: Settings):
    file_infos = scan_directory(tmp_codebase, default_settings)
    return [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]


# ---------------------------------------------------------------------------
# Legacy find_relevant tests
# ---------------------------------------------------------------------------


def test_search_finds_by_symbol_name(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant("helper", analyses, top_n=5)
    assert len(results) > 0
    paths = [r.file_path for r in results]
    assert "mypackage/utils.py" in paths


def test_search_finds_by_path(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant("module_a", analyses, top_n=5)
    assert len(results) > 0
    assert results[0].file_path == "mypackage/sub/module_a.py"


def test_search_finds_by_docstring(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant("configuration", analyses, top_n=5)
    assert len(results) > 0
    paths = [r.file_path for r in results]
    assert "mypackage/utils.py" in paths


def test_search_returns_empty_for_no_match(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant("xyznonexistent", analyses, top_n=5)
    assert len(results) == 0


def test_search_respects_top_n(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant("mypackage", analyses, top_n=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Refined pipeline tests
# ---------------------------------------------------------------------------


def test_refined_search_has_breakdown(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant_refined("helper", analyses, top_n=5)
    assert len(results) > 0
    top = results[0]
    assert top.file_path == "mypackage/utils.py"
    bd = top.match_breakdown
    assert bd.symbol_score > 0, "symbol_score should be positive for exact match"
    assert bd.keyword_score >= 0
    assert bd.path_score >= 0
    assert bd.docstring_score >= 0


def test_refined_search_has_reasoning(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant_refined("helper", analyses, top_n=5)
    assert len(results) > 0
    top = results[0]
    assert len(top.reasoning) > 0
    for step in top.reasoning:
        assert step.observation
        assert step.evidence


def test_refined_search_confidence_normalized(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant_refined("helper", analyses, top_n=5)
    assert len(results) > 0
    assert results[0].confidence == 1.0
    for r in results:
        assert 0.0 <= r.confidence <= 1.0


def test_refined_search_empty_for_no_match(
    tmp_codebase: Path, default_settings: Settings,
) -> None:
    analyses = _build_analyses(tmp_codebase, default_settings)
    results = find_relevant_refined("xyznonexistent", analyses, top_n=5)
    assert results == []
