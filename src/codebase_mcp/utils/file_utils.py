"""File-system utilities: safe reading, language detection, gitignore loading."""

from __future__ import annotations

from pathlib import Path

import pathspec

from codebase_mcp.schemas.models import Language

EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".java": Language.JAVA,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".c": Language.C,
    ".h": Language.C,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".hpp": Language.CPP,
    ".rb": Language.RUBY,
    ".html": Language.HTML,
    ".htm": Language.HTML,
    ".css": Language.CSS,
    ".scss": Language.CSS,
    ".json": Language.JSON,
    ".yaml": Language.YAML,
    ".yml": Language.YAML,
    ".toml": Language.TOML,
    ".md": Language.MARKDOWN,
    ".rst": Language.MARKDOWN,
    ".sh": Language.SHELL,
    ".bash": Language.SHELL,
    ".zsh": Language.SHELL,
    ".sql": Language.SQL,
}

ALWAYS_SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
})


def detect_language(path: Path) -> Language:
    """Detect programming language from file extension."""
    return EXTENSION_MAP.get(path.suffix.lower(), Language.OTHER)


def safe_read_file(path: Path, max_size: int = 1_048_576) -> str | None:
    """Read a file's contents, returning None if unreadable or too large.

    Args:
        path: Path to the file.
        max_size: Maximum file size in bytes (default 1 MB).
    """
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > max_size:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return None


def count_lines(content: str) -> int:
    """Count lines in file content."""
    if not content:
        return 0
    return content.count("\n") + (1 if not content.endswith("\n") else 0)


def load_gitignore(root: Path) -> pathspec.PathSpec | None:
    """Load .gitignore patterns from a directory, if present."""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.is_file():
        return None
    try:
        text = gitignore_path.read_text(encoding="utf-8", errors="replace")
        return pathspec.PathSpec.from_lines("gitignore", text.splitlines())
    except OSError:
        return None


def should_skip_dir(dirname: str) -> bool:
    """Check whether a directory name should always be skipped."""
    return dirname in ALWAYS_SKIP_DIRS or dirname.endswith(".egg-info")
