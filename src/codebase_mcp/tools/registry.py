"""Tool registry: dynamic discovery, lookup, and keyword-based routing."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Central catalogue of all available tools.

    Supports three access patterns used by different consumers:

    1. **By name** -- MCP server dispatches ``tool_name`` → ``execute()``.
    2. **List all** -- Agent UIs enumerate available tools with metadata.
    3. **Route by query** -- An agent loop matches a user query against
       trigger keywords to propose candidate tools.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # -- Registration --------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Add a tool instance.  Raises on duplicate names."""
        name = tool.name
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = tool
        logger.info("tool registered", tool=name)

    # -- Lookup --------------------------------------------------------------

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolMetadata]:
        """Return metadata for every registered tool."""
        return [t.metadata for t in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    # -- Execution -----------------------------------------------------------

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Look up a tool by name and run it.  Returns a ToolResult."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.fail(name, f"Unknown tool: {name}")
        try:
            return tool.execute(**kwargs)
        except Exception as exc:
            logger.error("tool execution failed", tool=name, error=str(exc))
            return ToolResult.fail(name, str(exc))

    # -- Routing / selection -------------------------------------------------

    def route(self, query: str, top_n: int = 3) -> list[ToolMetadata]:
        """Return the tools whose trigger keywords best match *query*.

        Simple keyword-overlap scoring -- good enough for v1, replaceable by
        an embedding-based ranker later.
        """
        query_tokens = set(query.lower().split())
        scored: list[tuple[float, ToolMetadata]] = []

        for tool in self._tools.values():
            meta = tool.metadata
            keywords = {kw.lower() for kw in meta.trigger_keywords}
            caps = {c.lower() for c in meta.capabilities}
            desc_tokens = set(meta.description.lower().split())

            kw_hits = len(query_tokens & keywords)
            cap_hits = len(query_tokens & caps)
            desc_hits = len(query_tokens & desc_tokens)
            score = kw_hits * 3.0 + cap_hits * 2.0 + desc_hits * 0.5

            if score > 0:
                scored.append((score, meta))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [meta for _, meta in scored[:top_n]]

    # -- Auto-discovery ------------------------------------------------------

    def discover(self) -> None:
        """Import all modules in the ``codebase_mcp.tools`` package and register
        any ``BaseTool`` subclasses that expose a module-level ``tool_instance``.
        """
        import codebase_mcp.tools as tools_pkg

        for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
            if modname.startswith("_") or modname in ("base", "registry"):
                continue
            fqn = f"codebase_mcp.tools.{modname}"
            try:
                mod = importlib.import_module(fqn)
            except Exception:
                logger.warning("failed to import tool module", module=fqn, exc_info=True)
                continue

            instance = getattr(mod, "tool_instance", None)
            if isinstance(instance, BaseTool) and instance.name not in self._tools:
                self.register(instance)

        logger.info("tool discovery complete", tools=self.list_names())
