"""Architecture summarizer: generates a high-level view of the codebase."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from codebase_mcp.schemas.models import (
    ArchitectureSummary,
    DependencyGraph,
    FileAnalysis,
    LanguageBreakdown,
)
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)

ENTRY_POINT_NAMES = frozenset({
    "__main__.py",
    "main.py",
    "app.py",
    "cli.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "setup.py",
})


def summarize_architecture(
    analyses: list[FileAnalysis],
    graph: DependencyGraph,
    root: Path,
) -> ArchitectureSummary:
    """Produce an ArchitectureSummary from analysis data and the dependency graph."""
    total_files = len(analyses)
    total_lines = sum(a.info.line_count for a in analyses)

    lang_counts: Counter[str] = Counter()
    lang_lines: defaultdict[str, int] = defaultdict(int)
    for a in analyses:
        lang_counts[a.info.language] += 1
        lang_lines[a.info.language] += a.info.line_count

    languages = sorted(
        [
            LanguageBreakdown(
                language=lang,
                file_count=count,
                total_lines=lang_lines[lang],
            )
            for lang, count in lang_counts.items()
        ],
        key=lambda lb: lb.file_count,
        reverse=True,
    )

    top_level_modules = _detect_top_level_modules(analyses)
    entry_points = _find_entry_points(analyses)
    key_files = _find_key_files(graph, top_n=10)

    summary = ArchitectureSummary(
        root_path=str(root),
        total_files=total_files,
        total_lines=total_lines,
        languages=languages,
        top_level_modules=top_level_modules,
        entry_points=entry_points,
        key_files=key_files,
    )
    logger.info("architecture summary generated", files=total_files, lines=total_lines)
    return summary


def _detect_top_level_modules(analyses: list[FileAnalysis]) -> list[str]:
    """Return the distinct first path component for all analyzed files."""
    top_levels: set[str] = set()
    for a in analyses:
        parts = Path(a.info.path).parts
        if parts:
            top_levels.add(parts[0])
    return sorted(top_levels)


def _find_entry_points(analyses: list[FileAnalysis]) -> list[str]:
    """Identify files that look like entry points by their filename."""
    return sorted(
        a.info.path
        for a in analyses
        if Path(a.info.path).name in ENTRY_POINT_NAMES
    )


def _find_key_files(graph: DependencyGraph, top_n: int = 10) -> list[str]:
    """Return the most-imported files (highest in-degree) from the dependency graph."""
    in_degree: Counter[str] = Counter()
    for edge in graph.edges:
        in_degree[edge.target] += 1
    return [path for path, _ in in_degree.most_common(top_n)]
