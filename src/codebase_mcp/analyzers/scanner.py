"""File-system scanner: walks a directory tree, respects .gitignore, collects FileInfo."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.core.config import Settings
from codebase_mcp.schemas.models import FileInfo
from codebase_mcp.utils.file_utils import (
    count_lines,
    detect_language,
    load_gitignore,
    safe_read_file,
    should_skip_dir,
)
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


def scan_directory(root: Path, settings: Settings) -> list[FileInfo]:
    """Recursively scan *root* and return metadata for every eligible file.

    Skips:
    - Directories in the always-skip list (.git, node_modules, etc.)
    - Paths matching .gitignore patterns
    - Files exceeding max_file_size
    """
    root = root.resolve()
    if not root.is_dir():
        logger.warning("scan_directory called on non-directory", path=str(root))
        return []

    gitignore = load_gitignore(root)
    files: list[FileInfo] = []

    for item in _walk(root, root, gitignore, settings):
        files.append(item)

    logger.info("scan complete", root=str(root), file_count=len(files))
    return files


def _walk(
    current: Path,
    root: Path,
    gitignore: object | None,
    settings: Settings,
) -> list[FileInfo]:
    """Depth-first walk yielding FileInfo for each eligible file."""
    results: list[FileInfo] = []

    try:
        entries = sorted(current.iterdir(), key=lambda p: p.name)
    except PermissionError:
        logger.debug("permission denied, skipping", path=str(current))
        return results

    for entry in entries:
        rel = entry.relative_to(root)
        rel_str = str(rel)

        if entry.is_dir():
            if should_skip_dir(entry.name):
                continue
            if gitignore and gitignore.match_file(rel_str + "/"):
                continue
            results.extend(_walk(entry, root, gitignore, settings))

        elif entry.is_file():
            if gitignore and gitignore.match_file(rel_str):
                continue

            content = safe_read_file(entry, max_size=settings.max_file_size)
            if content is None:
                continue

            info = FileInfo(
                path=rel_str,
                absolute_path=str(entry),
                language=detect_language(entry),
                size_bytes=entry.stat().st_size,
                line_count=count_lines(content),
                extension=entry.suffix,
            )
            results.append(info)

    return results
