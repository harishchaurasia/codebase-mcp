"""Codebase orchestrator: ties together scanning, analysis, and querying."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.dependency import build_dependency_graph
from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.analyzers.search import find_relevant
from codebase_mcp.analyzers.summarizer import summarize_architecture
from codebase_mcp.core.config import Settings
from codebase_mcp.schemas.models import (
    ArchitectureSummary,
    DependencyGraph,
    FileAnalysis,
    FileDependencyInfo,
    FileExplanation,
    FileSuggestion,
    SearchResult,
    SymbolSummary,
)
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class CodebaseAnalyzer:
    """Central facade that scans, analyzes, and caches results for a codebase."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root: Path | None = None
        self._analyses: list[FileAnalysis] = []
        self._graph: DependencyGraph | None = None
        self._summary: ArchitectureSummary | None = None
        self._analyses_by_path: dict[str, FileAnalysis] = {}

    @property
    def is_loaded(self) -> bool:
        return self._root is not None and len(self._analyses) > 0

    def analyze(self, root: str) -> ArchitectureSummary:
        """Scan and fully analyze the codebase rooted at *root*."""
        self._root = Path(root).resolve()
        logger.info("analyzing codebase", root=str(self._root))

        file_infos = scan_directory(self._root, self._settings)

        self._analyses = [
            analyze_file(Path(fi.absolute_path), self._root, self._settings.max_file_size)
            for fi in file_infos
        ]
        self._analyses_by_path = {a.info.path: a for a in self._analyses}

        self._graph = build_dependency_graph(self._analyses, self._root)
        self._summary = summarize_architecture(self._analyses, self._graph, self._root)

        logger.info(
            "analysis complete",
            files=len(self._analyses),
            edges=len(self._graph.edges),
        )
        return self._summary

    def get_summary(self) -> ArchitectureSummary:
        """Return the cached architecture summary."""
        self._ensure_loaded()
        assert self._summary is not None
        return self._summary

    def find_relevant_files(self, query: str, top_n: int = 10) -> list[SearchResult]:
        """Search for files relevant to a natural-language query."""
        self._ensure_loaded()
        return find_relevant(query, self._analyses, top_n=top_n)

    def explain_file(self, file_path: str) -> FileExplanation | None:
        """Return a structured explanation of what a file does."""
        self._ensure_loaded()
        assert self._graph is not None

        analysis = self._analyses_by_path.get(file_path)
        if analysis is None:
            return None

        deps = self._graph.get_dependencies(file_path)
        dependents = self._graph.get_dependents(file_path)

        return FileExplanation(
            path=analysis.info.path,
            language=analysis.info.language.value,
            lines=analysis.info.line_count,
            module_docstring=analysis.module_docstring,
            symbols=[
                SymbolSummary(
                    name=s.name,
                    kind=s.kind.value,
                    line=s.line_number,
                    docstring=s.docstring,
                )
                for s in analysis.symbols
            ],
            imports_from=[e.target for e in deps],
            imported_by=[e.source for e in dependents],
        )

    def get_file_dependencies(self, file_path: str) -> FileDependencyInfo:
        """Return what a file imports and what imports it."""
        self._ensure_loaded()
        assert self._graph is not None

        return FileDependencyInfo(
            file=file_path,
            imports=self._graph.get_dependencies(file_path),
            imported_by=self._graph.get_dependents(file_path),
        )

    def get_dependency_graph(self, filter_path: str | None = None) -> dict:
        """Return the full or filtered dependency graph as a serializable dict."""
        self._ensure_loaded()
        assert self._graph is not None

        if filter_path:
            relevant_edges = [
                e for e in self._graph.edges
                if e.source.startswith(filter_path) or e.target.startswith(filter_path)
            ]
            relevant_nodes = set()
            for e in relevant_edges:
                relevant_nodes.add(e.source)
                relevant_nodes.add(e.target)
            return {
                "filter": filter_path,
                "nodes": sorted(relevant_nodes),
                "edges": [e.model_dump() for e in relevant_edges],
            }

        return {
            "nodes": self._graph.nodes,
            "edges": [e.model_dump() for e in self._graph.edges],
        }

    def suggest_files_for_task(
        self,
        task_description: str,
        top_n: int = 5,
    ) -> list[FileSuggestion]:
        """Suggest files an agent should examine or edit for a given task.

        Combines keyword search with dependency analysis: each hit is enriched
        with its immediate dependency neighbourhood so the agent sees the full
        context it needs.
        """
        self._ensure_loaded()
        assert self._graph is not None

        search_results = find_relevant(task_description, self._analyses, top_n=top_n)
        suggestions: list[FileSuggestion] = []

        for sr in search_results:
            deps = self._graph.get_dependencies(sr.file_path)
            dependents = self._graph.get_dependents(sr.file_path)
            neighbours = sorted({e.target for e in deps} | {e.source for e in dependents})

            analysis = self._analyses_by_path.get(sr.file_path)
            reason = sr.context
            if analysis and analysis.module_docstring:
                reason = analysis.module_docstring.strip().split("\n")[0]

            suggestions.append(
                FileSuggestion(
                    file_path=sr.file_path,
                    relevance_score=sr.score,
                    reason=reason,
                    related_files=neighbours,
                )
            )

        return suggestions

    def _ensure_loaded(self) -> None:
        if not self.is_loaded:
            raise RuntimeError(
                "No codebase loaded. Call 'analyze_repo' first with a directory path."
            )
