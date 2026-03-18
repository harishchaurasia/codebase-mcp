"""Tests for the keyword-based search."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.analyzers.search import find_relevant
from codebase_mcp.core.config import Settings


def test_search_finds_by_symbol_name(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]

    results = find_relevant("helper", analyses, top_n=5)
    assert len(results) > 0
    paths = [r.file_path for r in results]
    assert "mypackage/utils.py" in paths


def test_search_finds_by_path(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]

    results = find_relevant("module_a", analyses, top_n=5)
    assert len(results) > 0
    assert results[0].file_path == "mypackage/sub/module_a.py"


def test_search_finds_by_docstring(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]

    results = find_relevant("configuration", analyses, top_n=5)
    assert len(results) > 0
    paths = [r.file_path for r in results]
    assert "mypackage/utils.py" in paths


def test_search_returns_empty_for_no_match(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]

    results = find_relevant("xyznonexistent", analyses, top_n=5)
    assert len(results) == 0


def test_search_respects_top_n(
    tmp_codebase: Path, default_settings: Settings
) -> None:
    file_infos = scan_directory(tmp_codebase, default_settings)
    analyses = [
        analyze_file(Path(fi.absolute_path), tmp_codebase, default_settings.max_file_size)
        for fi in file_infos
    ]

    results = find_relevant("mypackage", analyses, top_n=2)
    assert len(results) <= 2
