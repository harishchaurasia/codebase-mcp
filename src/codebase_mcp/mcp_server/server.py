"""MCP server that auto-discovers tools from the registry and exposes them
over stdio (or HTTP).

The MCP layer is intentionally thin: it builds a ToolRegistry, discovers all
tool modules, and creates one ``@mcp.tool()`` wrapper per registered tool.
All business logic lives in ``tools/`` and ``core/``.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from codebase_mcp.core.config import get_settings
from codebase_mcp.tools.registry import ToolRegistry
from codebase_mcp.utils.logging import get_logger, setup_logging

mcp = FastMCP("codebase-mcp")
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Return the shared ToolRegistry, running discovery on first call."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _registry.discover()
    return _registry


# ---------------------------------------------------------------------------
# Auto-registered MCP tools (wrappers around the registry)
# ---------------------------------------------------------------------------


@mcp.tool()
def analyze_repo(directory: str) -> dict:
    """Scan and analyze a local codebase directory.

    This must be called before using any other tool.  It walks the directory,
    parses source files, builds a dependency graph, and caches the results.

    Args:
        directory: Absolute path to the codebase root directory.
    """
    result = get_registry().execute("analyze_repo", directory=directory)
    return result.model_dump()


@mcp.tool()
def explain_file(file_path: str) -> dict:
    """Explain what a specific file does: its purpose, symbols, and relationships.

    Args:
        file_path: Relative path of the file (as shown in analysis output).
    """
    result = get_registry().execute("explain_file", file_path=file_path)
    return result.model_dump()


@mcp.tool()
def find_codebase_references(query: str, top_n: int = 10) -> dict:
    """Find files most relevant to a natural-language query or feature description.

    Args:
        query: What you are looking for (e.g. "authentication middleware").
        top_n: Maximum number of results to return (default 10).
    """
    result = get_registry().execute("find_codebase_references", query=query, top_n=top_n)
    return result.model_dump()


@mcp.tool()
def suggest_files_for_task(task_description: str, top_n: int = 5) -> dict:
    """Suggest which files to examine or edit for a given task.

    Combines relevance search with dependency analysis so you see every file
    in the affected neighbourhood.

    Args:
        task_description: What you want to accomplish (e.g. "Add rate limiting").
        top_n: Maximum number of suggestions (default 5).
    """
    result = get_registry().execute(
        "suggest_files_for_task", task_description=task_description, top_n=top_n,
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# Meta-tools: let the agent introspect the tool system itself
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tools() -> list[dict]:
    """List all available tools with their metadata, trigger keywords, and usage examples.

    Useful for agents that need to decide which tool to call next.
    """
    registry = get_registry()
    return [m.model_dump() for m in registry.list_tools()]


@mcp.tool()
def route_query(query: str, top_n: int = 3) -> list[dict]:
    """Given a natural-language query, return the tools most likely to help.

    Uses keyword matching against each tool's trigger keywords and capabilities.

    Args:
        query: The user's request in plain English.
        top_n: How many tool suggestions to return (default 3).
    """
    registry = get_registry()
    matches = registry.route(query, top_n=top_n)
    return [m.model_dump() for m in matches]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server."""
    settings = get_settings()
    setup_logging(level=settings.log_level, fmt=settings.log_format)

    logger = get_logger(__name__)

    registry = get_registry()
    logger.info(
        "starting codebase-mcp server",
        transport=settings.transport,
        tools=registry.list_names(),
    )

    mcp.run(transport=settings.transport)
