"""Tests for the AST analyzer."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.schemas.models import Language, SymbolKind


def test_analyze_extracts_functions(tmp_path: Path) -> None:
    src = tmp_path / "example.py"
    src.write_text(dedent("""\
        \"\"\"Module doc.\"\"\"

        def foo() -> int:
            \"\"\"Do foo.\"\"\"
            return 1

        def bar():
            pass
    """))
    result = analyze_file(src, tmp_path)
    assert result.module_docstring == "Module doc."
    names = {s.name for s in result.symbols}
    assert "foo" in names
    assert "bar" in names
    foo = next(s for s in result.symbols if s.name == "foo")
    assert foo.kind == SymbolKind.FUNCTION
    assert foo.docstring == "Do foo."


def test_analyze_extracts_classes(tmp_path: Path) -> None:
    src = tmp_path / "models.py"
    src.write_text(dedent("""\
        class User:
            \"\"\"A user model.\"\"\"
            name: str

        class Admin(User):
            pass
    """))
    result = analyze_file(src, tmp_path)
    classes = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
    assert len(classes) == 2
    assert classes[0].name == "User"
    assert classes[0].docstring == "A user model."


def test_analyze_extracts_imports(tmp_path: Path) -> None:
    src = tmp_path / "importer.py"
    src.write_text(dedent("""\
        import os
        from pathlib import Path
        from . import sibling
        from ..parent import thing
    """))
    result = analyze_file(src, tmp_path)
    assert len(result.imports) == 4

    os_imp = result.imports[0]
    assert os_imp.module == "os"
    assert not os_imp.is_relative

    path_imp = result.imports[1]
    assert path_imp.module == "pathlib"
    assert "Path" in path_imp.names

    rel1 = result.imports[2]
    assert rel1.is_relative
    assert rel1.level == 1

    rel2 = result.imports[3]
    assert rel2.is_relative
    assert rel2.level == 2


def test_analyze_extracts_variables(tmp_path: Path) -> None:
    src = tmp_path / "consts.py"
    src.write_text("MAX_SIZE = 100\nDEBUG = True\n")
    result = analyze_file(src, tmp_path)
    var_names = {s.name for s in result.symbols if s.kind == SymbolKind.VARIABLE}
    assert "MAX_SIZE" in var_names
    assert "DEBUG" in var_names


def test_analyze_non_python_file(tmp_path: Path) -> None:
    md = tmp_path / "README.md"
    md.write_text("# Hello\n")
    result = analyze_file(md, tmp_path)
    assert result.info.language == Language.MARKDOWN
    assert result.symbols == []
    assert result.imports == []


def test_analyze_handles_syntax_error(tmp_path: Path) -> None:
    src = tmp_path / "broken.py"
    src.write_text("def foo(\n")  # intentional syntax error
    result = analyze_file(src, tmp_path)
    assert result.symbols == []
    assert result.imports == []


def test_analyze_extracts_decorators(tmp_path: Path) -> None:
    src = tmp_path / "decorated.py"
    src.write_text(dedent("""\
        def my_decorator(f):
            return f

        @my_decorator
        def decorated_func():
            pass
    """))
    result = analyze_file(src, tmp_path)
    decorated = next(s for s in result.symbols if s.name == "decorated_func")
    assert "my_decorator" in decorated.decorators
