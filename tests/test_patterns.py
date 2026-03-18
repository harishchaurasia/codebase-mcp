"""Tests for heuristic pattern detection."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.patterns import detect_patterns
from codebase_mcp.schemas.models import FileAnalysis, FileInfo, Language


def _make_py_analysis(tmp_path: Path, name: str, content: str) -> FileAnalysis:
    """Helper: write a .py file and return its analysis."""
    src = tmp_path / name
    src.write_text(content)
    return analyze_file(src, tmp_path)


def test_detects_framework_from_imports(tmp_path: Path) -> None:
    analysis = _make_py_analysis(tmp_path, "app.py", dedent("""\
        from fastapi import FastAPI

        app = FastAPI()
    """))
    patterns = detect_patterns([analysis])
    names = {p.name for p in patterns}
    assert "fastapi" in names
    fastapi_p = next(p for p in patterns if p.name == "fastapi")
    assert fastapi_p.category == "framework"
    assert "app.py" in fastapi_p.evidence


def test_detects_test_framework(tmp_path: Path) -> None:
    analysis = _make_py_analysis(tmp_path, "test_foo.py", dedent("""\
        import pytest

        def test_something():
            assert True
    """))
    patterns = detect_patterns([analysis])
    names = {p.name for p in patterns}
    assert "pytest" in names
    pytest_p = next(p for p in patterns if p.name == "pytest")
    assert pytest_p.category == "testing"


def test_detects_build_tool(tmp_path: Path) -> None:
    toml = tmp_path / "pyproject.toml"
    toml.write_text("[project]\nname = 'test'\n")
    # Build tool detection works on file paths, not AST, so we need a FileAnalysis
    # with the right path. Use a non-python file analysis.
    analysis = FileAnalysis(
        info=FileInfo(
            path="pyproject.toml",
            absolute_path=str(toml),
            language=Language.TOML,
            size_bytes=30,
            line_count=2,
            extension=".toml",
        ),
    )
    patterns = detect_patterns([analysis])
    names = {p.name for p in patterns}
    assert "pyproject" in names
    p = next(p for p in patterns if p.name == "pyproject")
    assert p.category == "build"


def test_detects_multiple_patterns(tmp_path: Path) -> None:
    app = _make_py_analysis(tmp_path, "app.py", "from flask import Flask\n")
    test = _make_py_analysis(tmp_path, "test_app.py", "import pytest\n")
    toml_analysis = FileAnalysis(
        info=FileInfo(
            path="pyproject.toml",
            absolute_path=str(tmp_path / "pyproject.toml"),
            language=Language.TOML,
            size_bytes=10,
            line_count=1,
            extension=".toml",
        ),
    )
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    patterns = detect_patterns([app, test, toml_analysis])
    names = {p.name for p in patterns}
    assert "flask" in names
    assert "pytest" in names
    assert "pyproject" in names


def test_no_false_positives(tmp_path: Path) -> None:
    analysis = _make_py_analysis(tmp_path, "simple.py", dedent("""\
        import os
        from pathlib import Path

        def hello():
            return "world"
    """))
    patterns = detect_patterns([analysis])
    # Should not detect any framework, test tool, or build pattern
    categories = {p.category for p in patterns}
    assert "framework" not in categories
    assert "testing" not in categories
