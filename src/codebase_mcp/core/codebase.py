"""Codebase orchestrator: ties scanning, analysis, memory, and querying together."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.dependency import build_dependency_graph
from codebase_mcp.analyzers.patterns import detect_patterns
from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.analyzers.search import find_relevant
from codebase_mcp.analyzers.summarizer import summarize_architecture
from codebase_mcp.core.config import Settings
from codebase_mcp.core.memory import MemoryStore
from codebase_mcp.schemas.models import (
    ArchitectureSummary,
    DependencyGraph,
    DetectedPattern,
    FileAnalysis,
    FileDependencyInfo,
    FileExplanation,
    FileFingerprint,
    FileSuggestion,
    RepoMemory,
    ScanDiff,
    SearchResult,
    SymbolSummary,
)
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class CodebaseAnalyzer:
    """Central facade that scans, analyzes, caches, and persists results."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._store = MemoryStore(memory_dir=settings.memory_dir)
        self._root: Path | None = None
        self._analyses_by_path: dict[str, FileAnalysis] = {}
        self._graph: DependencyGraph | None = None
        self._summary: ArchitectureSummary | None = None
        self._patterns: list[DetectedPattern] = []
        self._memory: RepoMemory | None = None
        self._loaded_from_cache: bool = False

    @property
    def is_loaded(self) -> bool:
        return self._root is not None and len(self._analyses_by_path) > 0

    # ------------------------------------------------------------------
    # Main analysis entry point
    # ------------------------------------------------------------------

    def analyze(self, root: str, force: bool = False) -> ArchitectureSummary:
        """Analyze a codebase with memory-aware caching.

        1. If cached memory exists and ``force`` is False, diff fingerprints
           and only re-analyze changed/added files.
        2. If no cache or ``force`` is True, do a full analysis.
        3. Always persist the updated memory to disk afterward.
        """
        self._root = Path(root).resolve()
        logger.info("analyze requested", root=str(self._root), force=force)

        cached = None if force else self._store.load(self._root)

        if cached is not None:
            current_fps = MemoryStore.fingerprint_directory(
                self._root, self._settings.max_file_size,
            )
            diff = MemoryStore.compute_diff(cached.fingerprints, current_fps)

            if not diff.has_changes:
                logger.info("no changes detected, using cached memory")
                self._hydrate(cached)
                self._loaded_from_cache = True
                assert self._summary is not None
                return self._summary

            logger.info(
                "partial re-analysis",
                added=len(diff.added),
                changed=len(diff.changed),
                removed=len(diff.removed),
            )
            summary = self._partial_analyze(cached, diff, current_fps)
        else:
            logger.info("full analysis")
            summary = self._full_analyze()

        assert self._summary is not None
        return summary

    # ------------------------------------------------------------------
    # Full analysis (no cache)
    # ------------------------------------------------------------------

    def _full_analyze(self) -> ArchitectureSummary:
        assert self._root is not None
        file_infos = scan_directory(self._root, self._settings)

        analyses = [
            analyze_file(Path(fi.absolute_path), self._root, self._settings.max_file_size)
            for fi in file_infos
        ]
        self._analyses_by_path = {a.info.path: a for a in analyses}

        fingerprints = MemoryStore.fingerprint_directory(
            self._root, self._settings.max_file_size,
        )

        self._rebuild_derived()
        self._persist(fingerprints)
        self._loaded_from_cache = False

        logger.info("full analysis complete", files=len(self._analyses_by_path))
        return self._summary  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Partial analysis (cached + diff)
    # ------------------------------------------------------------------

    def _partial_analyze(
        self,
        cached: RepoMemory,
        diff: ScanDiff,
        current_fps: dict[str, FileFingerprint],
    ) -> ArchitectureSummary:
        assert self._root is not None

        # Start from cached analyses
        self._analyses_by_path = dict(cached.analyses)

        # Remove deleted files
        for path in diff.removed:
            self._analyses_by_path.pop(path, None)

        # Re-analyze added + changed files
        for path in diff.added + diff.changed:
            abs_path = self._root / path
            analysis = analyze_file(abs_path, self._root, self._settings.max_file_size)
            self._analyses_by_path[analysis.info.path] = analysis

        self._rebuild_derived()
        self._persist(current_fps)
        self._loaded_from_cache = False

        logger.info(
            "partial analysis complete",
            total_files=len(self._analyses_by_path),
            reanalyzed=len(diff.added) + len(diff.changed),
        )
        return self._summary  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _rebuild_derived(self) -> None:
        """Rebuild dependency graph, summary, and patterns from current analyses."""
        assert self._root is not None
        analyses = list(self._analyses_by_path.values())
        self._graph = build_dependency_graph(analyses, self._root)
        self._summary = summarize_architecture(analyses, self._graph, self._root)
        self._patterns = detect_patterns(analyses)

    def _persist(self, fingerprints: dict) -> None:
        """Save the current state as a RepoMemory to disk."""
        assert self._root is not None
        assert self._graph is not None
        assert self._summary is not None

        self._memory = RepoMemory(
            root_path=str(self._root),
            analyzed_at=MemoryStore.now_iso(),
            fingerprints=fingerprints,
            analyses=self._analyses_by_path,
            graph=self._graph,
            summary=self._summary,
            patterns=self._patterns,
        )
        self._store.save(self._memory)

    def _hydrate(self, memory: RepoMemory) -> None:
        """Restore instance state from a loaded RepoMemory."""
        self._memory = memory
        self._analyses_by_path = dict(memory.analyses)
        self._graph = memory.graph
        self._summary = memory.summary
        self._patterns = memory.patterns

    # ------------------------------------------------------------------
    # Query methods (unchanged API surface)
    # ------------------------------------------------------------------

    def get_summary(self) -> ArchitectureSummary:
        self._ensure_loaded()
        assert self._summary is not None
        return self._summary

    def find_relevant_files(self, query: str, top_n: int = 10) -> list[SearchResult]:
        self._ensure_loaded()
        return find_relevant(query, list(self._analyses_by_path.values()), top_n=top_n)

    def explain_file(self, file_path: str) -> FileExplanation | None:
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
        self._ensure_loaded()
        assert self._graph is not None
        return FileDependencyInfo(
            file=file_path,
            imports=self._graph.get_dependencies(file_path),
            imported_by=self._graph.get_dependents(file_path),
        )

    def get_dependency_graph(self, filter_path: str | None = None) -> dict:
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
        self, task_description: str, top_n: int = 5,
    ) -> list[FileSuggestion]:
        self._ensure_loaded()
        assert self._graph is not None

        analyses = list(self._analyses_by_path.values())
        search_results = find_relevant(task_description, analyses, top_n=top_n)
        suggestions: list[FileSuggestion] = []

        for sr in search_results:
            deps = self._graph.get_dependencies(sr.file_path)
            dependents = self._graph.get_dependents(sr.file_path)
            neighbours = sorted({e.target for e in deps} | {e.source for e in dependents})

            analysis = self._analyses_by_path.get(sr.file_path)
            reason = sr.context
            if analysis and analysis.module_docstring:
                reason = analysis.module_docstring.strip().split("\n")[0]

            suggestions.append(FileSuggestion(
                file_path=sr.file_path,
                relevance_score=sr.score,
                reason=reason,
                related_files=neighbours,
            ))

        return suggestions

    def get_memory_status(self) -> dict:
        """Return information about the current memory / cache state."""
        root = self._root
        on_disk = False
        if root:
            on_disk = self._store.cache_path(root).is_file()

        status: dict = {
            "is_loaded": self.is_loaded,
            "cached_on_disk": on_disk,
            "root_path": str(root) if root else None,
            "file_count": len(self._analyses_by_path),
            "loaded_from_cache": self._loaded_from_cache,
            "patterns": [p.model_dump() for p in self._patterns],
        }

        if self._memory:
            status["analyzed_at"] = self._memory.analyzed_at

        if root and on_disk and self.is_loaded:
            current_fps = MemoryStore.fingerprint_directory(
                root, self._settings.max_file_size,
            )
            cached_fps = self._memory.fingerprints if self._memory else {}
            diff = MemoryStore.compute_diff(cached_fps, current_fps)
            status["staleness"] = {
                "added": len(diff.added),
                "changed": len(diff.changed),
                "removed": len(diff.removed),
                "is_stale": diff.has_changes,
            }

        return status

    def _ensure_loaded(self) -> None:
        if not self.is_loaded:
            raise RuntimeError(
                "No codebase loaded. Call 'analyze_repo' first with a directory path."
            )
