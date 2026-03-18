"""Codebase orchestrator: ties scanning, analysis, memory, and querying together."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.analyzers.ast_analyzer import analyze_file
from codebase_mcp.analyzers.dependency import build_dependency_graph
from codebase_mcp.analyzers.patterns import detect_patterns
from codebase_mcp.analyzers.scanner import scan_directory
from codebase_mcp.analyzers.search import find_relevant, find_relevant_refined
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
    ReasoningStep,
    RefinedSearchResult,
    RepoMemory,
    ScanDiff,
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

    def find_relevant_files(
        self, query: str, top_n: int = 10,
    ) -> list[RefinedSearchResult]:
        """Three-stage pipeline: select candidates, evaluate, refine with deps."""
        self._ensure_loaded()
        assert self._graph is not None
        analyses = list(self._analyses_by_path.values())
        candidates = find_relevant_refined(query, analyses, top_n=top_n)
        return self._refine_with_dependencies(candidates)

    def _refine_with_dependencies(
        self, results: list[RefinedSearchResult],
    ) -> list[RefinedSearchResult]:
        """Stage 3: boost results based on dependency relationships."""
        assert self._graph is not None

        result_paths = {r.file_path for r in results}
        key_files = set(self._summary.key_files) if self._summary else set()

        for r in results:
            boost = 0.0

            dependents = self._graph.get_dependents(r.file_path)
            imported_by_results = [
                e.source for e in dependents if e.source in result_paths
            ]
            if imported_by_results:
                dep_boost = len(imported_by_results) * 0.5
                boost += dep_boost
                r.reasoning.append(ReasoningStep(
                    observation="Imported by other results in this set",
                    evidence=(
                        f"{len(imported_by_results)} result(s): "
                        f"{', '.join(imported_by_results[:3])}"
                    ),
                ))

            if r.file_path in key_files:
                boost += 0.3
                r.reasoning.append(ReasoningStep(
                    observation="File is a key file (high in-degree)",
                    evidence=r.file_path,
                ))

            if boost > 0:
                r.match_breakdown.dependency_boost = round(boost, 4)
                r.score = round(r.score + boost, 4)

        results.sort(key=lambda r: r.score, reverse=True)
        _reassign_confidence(results)
        return results

    def explain_file(self, file_path: str) -> FileExplanation | None:
        self._ensure_loaded()
        assert self._graph is not None

        analysis = self._analyses_by_path.get(file_path)
        if analysis is None:
            return None

        deps = self._graph.get_dependencies(file_path)
        dependents = self._graph.get_dependents(file_path)
        reasoning: list[ReasoningStep] = []

        symbols = [
            SymbolSummary(
                name=s.name,
                kind=s.kind.value,
                line=s.line_number,
                docstring=s.docstring,
            )
            for s in analysis.symbols
        ]
        imports_from = [e.target for e in deps]
        imported_by = [e.source for e in dependents]

        role = _classify_role(file_path, analysis, len(dependents), reasoning)
        purpose = _derive_purpose(file_path, analysis, role, reasoning)
        next_files = _rank_next_files(
            file_path, deps, dependents, self._analyses_by_path, reasoning,
        )
        confidence = _compute_confidence(analysis, deps, dependents, role, reasoning)

        return FileExplanation(
            path=analysis.info.path,
            language=analysis.info.language.value,
            lines=analysis.info.line_count,
            module_docstring=analysis.module_docstring,
            symbols=symbols,
            imports_from=imports_from,
            imported_by=imported_by,
            purpose=purpose,
            role=role,
            next_files=next_files,
            reasoning=reasoning,
            confidence=confidence,
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


# ---------------------------------------------------------------------------
# Confidence re-normalization (used by _refine_with_dependencies)
# ---------------------------------------------------------------------------


def _reassign_confidence(results: list[RefinedSearchResult]) -> None:
    """Re-normalize confidence so the top result is 1.0."""
    if not results:
        return
    max_score = results[0].score
    if max_score <= 0:
        return
    for r in results:
        r.confidence = round(min(1.0, r.score / max_score), 4)


# ---------------------------------------------------------------------------
# Heuristic reasoning helpers (module-level, used by explain_file)
# ---------------------------------------------------------------------------

_ENTRY_POINT_NAMES = frozenset({
    "__main__.py", "main.py", "app.py", "server.py", "cli.py",
    "manage.py", "wsgi.py", "asgi.py",
})

_ROLE_PATH_PATTERNS: list[tuple[list[str], str]] = [
    (["models", "schemas", "types"], "model"),
    (["utils", "helpers", "lib"], "utility"),
    (["api", "routes", "views", "endpoints", "handlers"], "api"),
    (["config", "settings"], "config"),
    (["middleware"], "api"),
]


def _classify_role(
    file_path: str,
    analysis: FileAnalysis,
    dependent_count: int,
    reasoning: list[ReasoningStep],
) -> str:
    """Classify a file's role from filename, path, and symbol patterns."""
    p = Path(file_path)
    name = p.name
    parts = {part.lower() for part in p.parts}

    # Test files
    if name.startswith("test_") or name.endswith("_test.py"):
        reasoning.append(ReasoningStep(
            observation="Filename matches test pattern",
            evidence=name,
        ))
        return "test"
    if name == "conftest.py":
        reasoning.append(ReasoningStep(
            observation="Filename is conftest.py (pytest fixture file)",
            evidence=name,
        ))
        return "test_fixture"

    # Entry points
    if name in _ENTRY_POINT_NAMES:
        reasoning.append(ReasoningStep(
            observation="Filename matches entry-point convention",
            evidence=name,
        ))
        return "entry_point"

    # Path-based patterns
    for keywords, role in _ROLE_PATH_PATTERNS:
        for kw in keywords:
            if kw in parts or kw in name.lower():
                reasoning.append(ReasoningStep(
                    observation=f"Path contains '{kw}' pattern",
                    evidence=file_path,
                ))
                return role

    # Symbol-based: if every class inherits BaseModel -> model
    classes = [s for s in analysis.symbols if s.kind == "class"]
    if classes:
        basemodel_imports = any(
            "BaseModel" in imp.names or imp.module in ("pydantic", "pydantic.main")
            for imp in analysis.imports
        )
        if basemodel_imports and len(classes) == len([
            s for s in analysis.symbols if s.kind == "class"
        ]):
            reasoning.append(ReasoningStep(
                observation="File defines Pydantic BaseModel classes",
                evidence=", ".join(c.name for c in classes),
            ))
            return "model"

    # High in-degree -> core logic
    if dependent_count >= 3:
        reasoning.append(ReasoningStep(
            observation=f"High in-degree: {dependent_count} files depend on this",
            evidence=f"{dependent_count} dependents",
        ))
        return "core_logic"

    # Init files
    if name == "__init__.py":
        reasoning.append(ReasoningStep(
            observation="Package init file",
            evidence=name,
        ))
        return "config"

    reasoning.append(ReasoningStep(
        observation="No strong role signal detected",
        evidence="defaulting to unknown",
    ))
    return "unknown"


def _derive_purpose(
    file_path: str,
    analysis: FileAnalysis,
    role: str,
    reasoning: list[ReasoningStep],
) -> str:
    """Derive a one-line purpose from the docstring or heuristics."""
    if analysis.module_docstring:
        first_sentence = analysis.module_docstring.strip().split("\n")[0].rstrip(".")
        reasoning.append(ReasoningStep(
            observation="Module docstring found",
            evidence=first_sentence[:80],
        ))
        return first_sentence

    # Fall back to symbol-based heuristics
    def _kind(s: object) -> str:
        k = s.kind  # type: ignore[attr-defined]
        return k.value if hasattr(k, "value") else k

    functions = [s for s in analysis.symbols if _kind(s) == "function"]
    classes = [s for s in analysis.symbols if _kind(s) == "class"]

    if classes and not functions:
        names = ", ".join(c.name for c in classes[:3])
        purpose = f"Defines {len(classes)} class(es): {names}"
    elif functions and not classes:
        names = ", ".join(f.name for f in functions[:3])
        purpose = f"Defines {len(functions)} function(s): {names}"
    elif functions and classes:
        purpose = (
            f"Defines {len(classes)} class(es) and "
            f"{len(functions)} function(s)"
        )
    elif role != "unknown":
        purpose = f"Acts as {role.replace('_', ' ')} ({Path(file_path).name})"
    else:
        lang = analysis.info.language.value
        lines = analysis.info.line_count
        purpose = f"{Path(file_path).name} ({lang}, {lines} lines)"

    reasoning.append(ReasoningStep(
        observation="Purpose derived from symbol analysis",
        evidence=purpose[:80],
    ))
    return purpose


def _rank_next_files(
    file_path: str,
    deps: list,
    dependents: list,
    analyses_by_path: dict[str, FileAnalysis],
    reasoning: list[ReasoningStep],
) -> list[str]:
    """Rank files the agent should examine next (up to 5)."""
    scored: dict[str, float] = {}

    # Dependents (files that import this one) -- high priority
    for edge in dependents:
        scored[edge.source] = scored.get(edge.source, 0) + 3.0

    # Dependencies (files this one imports) -- medium priority
    for edge in deps:
        scored[edge.target] = scored.get(edge.target, 0) + 2.0

    # Siblings (same directory) -- low priority
    parent = str(Path(file_path).parent)
    for path in analyses_by_path:
        if path != file_path and str(Path(path).parent) == parent:
            scored[path] = scored.get(path, 0) + 1.0

    # Remove self
    scored.pop(file_path, None)

    ranked = sorted(scored, key=lambda p: scored[p], reverse=True)[:5]
    if ranked:
        reasoning.append(ReasoningStep(
            observation=f"Identified {len(ranked)} related file(s) to examine next",
            evidence=", ".join(ranked[:3]),
        ))
    return ranked


def _compute_confidence(
    analysis: FileAnalysis,
    deps: list,
    dependents: list,
    role: str,
    reasoning: list[ReasoningStep],
) -> float:
    """Compute a confidence score (0.0-1.0) based on available signal strength."""
    score = 0.0
    if analysis.module_docstring:
        score += 0.25
    if analysis.symbols:
        score += 0.20
    if deps or dependents:
        score += 0.20
    if role != "unknown":
        score += 0.20
    if len(reasoning) > 3:
        score += 0.15
    return min(score, 1.0)
