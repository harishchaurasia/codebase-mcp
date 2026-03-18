"""Python AST analyzer: extracts symbols, imports, and docstrings from .py files."""

from __future__ import annotations

import ast
from pathlib import Path

from codebase_mcp.schemas.models import (
    FileAnalysis,
    FileInfo,
    ImportInfo,
    Language,
    Symbol,
    SymbolKind,
)
from codebase_mcp.utils.file_utils import count_lines, detect_language, safe_read_file
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


def analyze_file(path: Path, root: Path, max_size: int = 1_048_576) -> FileAnalysis:
    """Analyze a single file. Python files get full AST analysis; others get basic metadata."""
    rel_path = str(path.relative_to(root))
    content = safe_read_file(path, max_size=max_size)

    info = FileInfo(
        path=rel_path,
        absolute_path=str(path),
        language=detect_language(path),
        size_bytes=path.stat().st_size if path.exists() else 0,
        line_count=count_lines(content) if content else 0,
        extension=path.suffix,
    )

    if content is None or info.language != Language.PYTHON:
        return FileAnalysis(info=info)

    return _analyze_python(info, content)


def _analyze_python(info: FileInfo, content: str) -> FileAnalysis:
    """Parse Python source with the ast module and extract structured data."""
    try:
        tree = ast.parse(content, filename=info.path)
    except SyntaxError:
        logger.debug("syntax error, skipping AST analysis", file=info.path)
        return FileAnalysis(info=info)

    symbols = _extract_symbols(tree)
    imports = _extract_imports(tree)
    module_docstring = ast.get_docstring(tree)

    return FileAnalysis(
        info=info,
        symbols=symbols,
        imports=imports,
        module_docstring=module_docstring,
    )


def _extract_symbols(tree: ast.Module) -> list[Symbol]:
    """Extract top-level classes and functions from an AST."""
    symbols: list[Symbol] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(Symbol(
                name=node.name,
                kind=SymbolKind.CLASS,
                line_number=node.lineno,
                end_line_number=node.end_lineno,
                docstring=ast.get_docstring(node),
                decorators=[_decorator_name(d) for d in node.decorator_list],
            ))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(Symbol(
                name=node.name,
                kind=SymbolKind.FUNCTION,
                line_number=node.lineno,
                end_line_number=node.end_lineno,
                docstring=ast.get_docstring(node),
                decorators=[_decorator_name(d) for d in node.decorator_list],
            ))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append(Symbol(
                        name=target.id,
                        kind=SymbolKind.VARIABLE,
                        line_number=node.lineno,
                    ))

    return symbols


def _extract_imports(tree: ast.Module) -> list[ImportInfo]:
    """Extract all import and from-import statements."""
    imports: list[ImportInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportInfo(
                    module=alias.name,
                    names=[alias.asname or alias.name],
                    is_relative=False,
                    level=0,
                    line_number=node.lineno,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(ImportInfo(
                module=module,
                names=names,
                is_relative=node.level > 0,
                level=node.level,
                line_number=node.lineno,
            ))

    return imports


def _decorator_name(node: ast.expr) -> str:
    """Best-effort string representation of a decorator node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_decorator_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return "<complex>"
