"""Tests for the file scanner."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.core.config import Settings
from codebase_mcp.schemas.models import Language


def test_scan_finds_all_files(tmp_codebase: Path, default_settings: Settings) -> None:
    files = scan_directory(tmp_codebase, default_settings)
    paths = {f.path for f in files}
    assert "mypackage/__init__.py" in paths
    assert "mypackage/main.py" in paths
    assert "mypackage/utils.py" in paths
    assert "mypackage/sub/module_a.py" in paths
    assert "README.md" in paths


def test_scan_detects_languages(tmp_codebase: Path, default_settings: Settings) -> None:
    files = scan_directory(tmp_codebase, default_settings)
    by_path = {f.path: f for f in files}
    assert by_path["mypackage/main.py"].language == Language.PYTHON
    assert by_path["README.md"].language == Language.MARKDOWN


def test_scan_counts_lines(tmp_codebase: Path, default_settings: Settings) -> None:
    files = scan_directory(tmp_codebase, default_settings)
    by_path = {f.path: f for f in files}
    assert by_path["mypackage/main.py"].line_count > 0


def test_scan_skips_pycache(tmp_codebase: Path, default_settings: Settings) -> None:
    cache_dir = tmp_codebase / "mypackage" / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "utils.cpython-311.pyc").write_bytes(b"\x00")

    files = scan_directory(tmp_codebase, default_settings)
    paths = {f.path for f in files}
    assert not any("__pycache__" in p for p in paths)


def test_scan_respects_gitignore(tmp_codebase: Path, default_settings: Settings) -> None:
    (tmp_codebase / ".gitignore").write_text("*.log\n")
    (tmp_codebase / "debug.log").write_text("some log data")

    files = scan_directory(tmp_codebase, default_settings)
    paths = {f.path for f in files}
    assert "debug.log" not in paths


def test_scan_empty_dir(tmp_path: Path, default_settings: Settings) -> None:
    files = scan_directory(tmp_path, default_settings)
    assert files == []
