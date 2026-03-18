"""Keyword-based relevance search over analyzed files.

Implements a two-stage pipeline (select candidates, evaluate with breakdown)
that the orchestrator can further refine with dependency context.
The original find_relevant() is preserved for backward compatibility.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from codebase_mcp.schemas.models import (
    FileAnalysis,
    MatchBreakdown,
    ReasoningStep,
    RefinedSearchResult,
    SearchResult,
)
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)

_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_relevant(
    query: str,
    analyses: list[FileAnalysis],
    top_n: int = 10,
) -> list[SearchResult]:
    """Legacy single-pass search (used by suggest_files_for_task)."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    idf = _compute_idf(analyses)
    results: list[SearchResult] = []

    for analysis in analyses:
        score, matched = _score_file(query_tokens, analysis, idf)
        if score > 0:
            context = _build_context(analysis, matched)
            results.append(SearchResult(
                file_path=analysis.info.path,
                score=round(score, 4),
                matched_symbols=matched,
                context=context,
            ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]


def find_relevant_refined(
    query: str,
    analyses: list[FileAnalysis],
    top_n: int = 10,
) -> list[RefinedSearchResult]:
    """Two-stage pipeline: broad candidate selection then detailed evaluation."""
    candidates = select_candidates(query, analyses, limit=top_n * 3)
    analyses_by_path = {a.info.path: a for a in analyses}
    return evaluate_candidates(query, candidates, analyses_by_path, top_n=top_n)


# ---------------------------------------------------------------------------
# Stage 1: Candidate selection
# ---------------------------------------------------------------------------


def select_candidates(
    query: str,
    analyses: list[FileAnalysis],
    limit: int = 30,
) -> list[SearchResult]:
    """Broad TF-IDF pass returning more candidates than needed for refinement."""
    return find_relevant(query, analyses, top_n=limit)


# ---------------------------------------------------------------------------
# Stage 2: Evaluate candidates with per-signal breakdown
# ---------------------------------------------------------------------------


def evaluate_candidates(
    query: str,
    candidates: list[SearchResult],
    analyses_by_path: dict[str, FileAnalysis],
    top_n: int = 10,
) -> list[RefinedSearchResult]:
    """Score each candidate with a per-signal breakdown and reasoning trace."""
    query_tokens = _tokenize(query)
    if not query_tokens or not candidates:
        return []

    refined: list[RefinedSearchResult] = []
    for candidate in candidates:
        analysis = analyses_by_path.get(candidate.file_path)
        if analysis is None:
            continue

        breakdown, reasoning, matched = _evaluate_single(
            query_tokens, analysis,
        )
        total = (
            breakdown.keyword_score
            + breakdown.symbol_score
            + breakdown.path_score
            + breakdown.docstring_score
        )
        context = _build_context(analysis, matched)

        refined.append(RefinedSearchResult(
            file_path=candidate.file_path,
            score=round(total, 4),
            matched_symbols=matched,
            context=context,
            reasoning=reasoning,
            match_breakdown=breakdown,
        ))

    refined.sort(key=lambda r: r.score, reverse=True)
    refined = refined[:top_n]

    _assign_confidence(refined)
    return refined


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _evaluate_single(
    query_tokens: list[str],
    analysis: FileAnalysis,
) -> tuple[MatchBreakdown, list[ReasoningStep], list[str]]:
    """Compute per-signal scores for a single file."""
    file_tok = _file_tokens(analysis)
    file_counter = Counter(file_tok)
    idf_local: dict[str, float] = {}
    n = max(len(file_tok), 1)
    for t in set(file_tok):
        idf_local[t] = 1.0

    reasoning: list[ReasoningStep] = []
    matched_symbols: list[str] = []

    # Keyword TF-IDF
    keyword_score = 0.0
    kw_hits: list[str] = []
    for qt in query_tokens:
        if qt in file_counter:
            tf = file_counter[qt] / n
            keyword_score += tf * idf_local.get(qt, 1.0)
            kw_hits.append(qt)
    if kw_hits:
        reasoning.append(ReasoningStep(
            observation="Keyword match in file tokens",
            evidence=f"matched: {', '.join(sorted(set(kw_hits)))}",
        ))

    # Symbol name exact match
    symbol_score = 0.0
    sym_names_lower = {s.name.lower() for s in analysis.symbols}
    for qt in query_tokens:
        if qt in sym_names_lower:
            symbol_score += 2.0
            matched_symbols.append(qt)
    if matched_symbols:
        reasoning.append(ReasoningStep(
            observation="Exact symbol name match",
            evidence=f"symbols: {', '.join(matched_symbols)}",
        ))

    # Path token match
    path_score = 0.0
    path_tokens = set(_tokenize(analysis.info.path))
    path_hits: list[str] = []
    for qt in query_tokens:
        if qt in path_tokens:
            path_score += 1.0
            path_hits.append(qt)
    if path_hits:
        reasoning.append(ReasoningStep(
            observation="Query term found in file path",
            evidence=f"path tokens: {', '.join(path_hits)}",
        ))

    # Docstring relevance
    docstring_score = 0.0
    if analysis.module_docstring:
        doc_tokens = set(_tokenize(analysis.module_docstring))
        doc_hits: list[str] = []
        for qt in query_tokens:
            if qt in doc_tokens:
                docstring_score += 1.5
                doc_hits.append(qt)
        if doc_hits:
            first_line = analysis.module_docstring.strip().split("\n")[0]
            reasoning.append(ReasoningStep(
                observation="Query term found in module docstring",
                evidence=first_line[:80],
            ))

    breakdown = MatchBreakdown(
        keyword_score=round(keyword_score, 4),
        symbol_score=round(symbol_score, 4),
        path_score=round(path_score, 4),
        docstring_score=round(docstring_score, 4),
    )
    return breakdown, reasoning, matched_symbols


def _assign_confidence(results: list[RefinedSearchResult]) -> None:
    """Normalize scores to 0.0-1.0 confidence (top result = 1.0)."""
    if not results:
        return
    max_score = results[0].score
    if max_score <= 0:
        return
    for r in results:
        r.confidence = round(min(1.0, r.score / max_score), 4)


def _tokenize(text: str) -> list[str]:
    """Split text into lower-case tokens, expanding camelCase."""
    expanded = _CAMEL_RE.sub(" ", text)
    parts = _SPLIT_RE.split(expanded.lower())
    return [p for p in parts if p and len(p) > 1]


def _compute_idf(analyses: list[FileAnalysis]) -> dict[str, float]:
    """Compute inverse document frequency across all files."""
    n = len(analyses)
    if n == 0:
        return {}

    doc_freq: Counter[str] = Counter()
    for analysis in analyses:
        tokens = set(_file_tokens(analysis))
        for t in tokens:
            doc_freq[t] += 1

    return {
        token: math.log((n + 1) / (freq + 1)) + 1
        for token, freq in doc_freq.items()
    }


def _file_tokens(analysis: FileAnalysis) -> list[str]:
    """Collect all searchable tokens from a file analysis."""
    tokens: list[str] = []
    tokens.extend(_tokenize(analysis.info.path))

    for sym in analysis.symbols:
        tokens.extend(_tokenize(sym.name))
        if sym.docstring:
            tokens.extend(_tokenize(sym.docstring))

    if analysis.module_docstring:
        tokens.extend(_tokenize(analysis.module_docstring))

    return tokens


def _score_file(
    query_tokens: list[str],
    analysis: FileAnalysis,
    idf: dict[str, float],
) -> tuple[float, list[str]]:
    """Compute a relevance score for a file against the query tokens."""
    file_tok = _file_tokens(analysis)
    file_counter = Counter(file_tok)
    score = 0.0
    matched: list[str] = []

    for qt in query_tokens:
        if qt in file_counter:
            tf = file_counter[qt] / max(len(file_tok), 1)
            score += tf * idf.get(qt, 1.0)

    symbol_names_lower = {s.name.lower() for s in analysis.symbols}
    for qt in query_tokens:
        if qt in symbol_names_lower:
            score += 2.0
            matched.append(qt)

    path_tokens = set(_tokenize(analysis.info.path))
    for qt in query_tokens:
        if qt in path_tokens:
            score += 1.0

    return score, matched


def _build_context(analysis: FileAnalysis, matched: list[str]) -> str:
    """Build a short context string explaining why a file matched."""
    parts: list[str] = []
    if analysis.module_docstring:
        doc = analysis.module_docstring.strip().split("\n")[0]
        parts.append(doc)
    if matched:
        parts.append(f"Matched symbols: {', '.join(matched)}")
    if analysis.symbols:
        names = [s.name for s in analysis.symbols[:5]]
        parts.append(f"Defines: {', '.join(names)}")
    return " | ".join(parts) if parts else analysis.info.path
