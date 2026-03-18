"""Shared runtime context for tool implementations.

Holds the singleton CodebaseAnalyzer that all tools delegate to.
Kept separate so tool modules can import without circular dependencies.
"""

from __future__ import annotations

from codebase_mcp.core.codebase import CodebaseAnalyzer
from codebase_mcp.core.config import get_settings
from codebase_mcp.utils.logging import setup_logging

_analyzer: CodebaseAnalyzer | None = None


def get_analyzer() -> CodebaseAnalyzer:
    """Return the shared CodebaseAnalyzer, creating it on first call."""
    global _analyzer
    if _analyzer is None:
        settings = get_settings()
        setup_logging(level=settings.log_level, fmt=settings.log_format)
        _analyzer = CodebaseAnalyzer(settings)
    return _analyzer


def reset_analyzer() -> None:
    """Reset the shared analyzer (used by tests)."""
    global _analyzer
    _analyzer = None
