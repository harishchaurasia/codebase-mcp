"""MCP server exposing codebase analysis tools over stdio (or HTTP)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from codebase_mcp.core.codebase import CodebaseAnalyzer
from codebase_mcp.core.config import get_settings
from codebase_mcp.utils.logging import get_logger, setup_logging

mcp = FastMCP("codebase-mcp")
_analyzer: CodebaseAnalyzer | None = None


def _get_analyzer() -> CodebaseAnalyzer:
    global _analyzer
    if _analyzer is None:
        settings = get_settings()
        setup_logging(level=settings.log_level, fmt=settings.log_format)
        _analyzer = CodebaseAnalyzer(settings)
    return _analyzer


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def analyze_codebase(directory: str) -> dict:
    """Scan and analyze a local codebase directory.

    This must be called before using any other tool. It walks the directory,
    parses source files, builds a dependency graph, and caches the results.

    Args:
        directory: Absolute path to the codebase root directory.
    """
    analyzer = _get_analyzer()
    summary = analyzer.analyze(directory)
    return summary.model_dump()


@mcp.tool()
def get_architecture_summary() -> dict:
    """Get the high-level architecture summary of the analyzed codebase.

    Returns language breakdown, top-level modules, entry points, and key files.
    Requires analyze_codebase to have been called first.
    """
    analyzer = _get_analyzer()
    return analyzer.get_summary().model_dump()


@mcp.tool()
def find_relevant_files(query: str, top_n: int = 10) -> list[dict]:
    """Find files most relevant to a natural-language query or feature description.

    Uses keyword-based scoring over file paths, symbol names, and docstrings.

    Args:
        query: What you are looking for (e.g. "authentication middleware").
        top_n: Maximum number of results to return (default 10).
    """
    analyzer = _get_analyzer()
    results = analyzer.find_relevant_files(query, top_n=top_n)
    return [r.model_dump() for r in results]


@mcp.tool()
def explain_file(file_path: str) -> dict:
    """Explain what a specific file does: its purpose, symbols, and relationships.

    Args:
        file_path: Relative path of the file (as shown in analysis output).
    """
    analyzer = _get_analyzer()
    return analyzer.explain_file(file_path)


@mcp.tool()
def get_file_dependencies(file_path: str) -> dict:
    """Show what a file imports and which files import it.

    Args:
        file_path: Relative path of the file to inspect.
    """
    analyzer = _get_analyzer()
    return analyzer.get_file_dependencies(file_path)


@mcp.tool()
def get_dependency_graph(filter_path: str | None = None) -> dict:
    """Return the file-level dependency graph for the analyzed codebase.

    Optionally filter to only edges touching files under a specific path prefix.

    Args:
        filter_path: Optional path prefix to filter the graph (e.g. "src/auth/").
    """
    analyzer = _get_analyzer()
    return analyzer.get_dependency_graph(filter_path=filter_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server."""
    settings = get_settings()
    setup_logging(level=settings.log_level, fmt=settings.log_format)

    logger = get_logger(__name__)
    logger.info("starting codebase-mcp server", transport=settings.transport)

    mcp.run(transport=settings.transport)
