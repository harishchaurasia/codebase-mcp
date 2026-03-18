"""Dependency graph builder: resolves imports to file paths within the repository."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.schemas.models import DependencyEdge, DependencyGraph, FileAnalysis
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


def build_dependency_graph(
    analyses: list[FileAnalysis],
    root: Path,
) -> DependencyGraph:
    """Build a file-level dependency graph from analyzed files.

    Only intra-repo dependencies are resolved (third-party imports are ignored).
    """
    module_map = _build_module_map(analyses, root)
    nodes = [a.info.path for a in analyses]
    edges: list[DependencyEdge] = []

    for analysis in analyses:
        source = analysis.info.path
        for imp in analysis.imports:
            resolved = _resolve_import(imp.module, imp.level, source, module_map, root)
            if resolved and resolved != source:
                edges.append(DependencyEdge(
                    source=source,
                    target=resolved,
                    imported_names=imp.names,
                ))

    logger.info(
        "dependency graph built",
        nodes=len(nodes),
        edges=len(edges),
    )
    return DependencyGraph(nodes=nodes, edges=edges)


def _build_module_map(analyses: list[FileAnalysis], root: Path) -> dict[str, str]:
    """Map dotted module names to relative file paths.

    For ``src/codebase_mcp/utils/file_utils.py`` the map contains both:
      - ``codebase_mcp.utils.file_utils`` -> ``src/codebase_mcp/utils/file_utils.py``
      - ``src.codebase_mcp.utils.file_utils`` -> ...

    Also maps package __init__.py to the package module name.
    """
    module_map: dict[str, str] = {}

    for analysis in analyses:
        rel = analysis.info.path
        p = Path(rel)

        if p.suffix != ".py":
            continue

        parts = list(p.parts)
        if parts[-1] == "__init__.py":
            module_parts = parts[:-1]
        else:
            parts[-1] = parts[-1].removesuffix(".py")
            module_parts = parts

        if module_parts:
            dotted = ".".join(module_parts)
            module_map[dotted] = rel

            # Also try without the top-level src/ directory
            if len(module_parts) > 1 and module_parts[0] == "src":
                module_map[".".join(module_parts[1:])] = rel

    return module_map


def _resolve_import(
    module: str,
    level: int,
    source_path: str,
    module_map: dict[str, str],
    root: Path,
) -> str | None:
    """Resolve a (possibly relative) import to a repo-relative file path."""
    if level > 0:
        source_parts = Path(source_path).parts
        # Go up `level` directories from the source file's directory
        package_parts = list(source_parts[:-1])  # drop filename
        for _ in range(level - 1):
            if package_parts:
                package_parts.pop()
        full_module = ".".join(package_parts) + "." + module if module else ".".join(package_parts)
        return module_map.get(full_module)

    return module_map.get(module)
