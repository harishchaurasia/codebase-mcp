"""Keyword-based relevance search over analyzed files.

Uses simple TF-IDF-like scoring with no external dependencies --
scikit-learn can replace this in the future for better relevance.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from codebase_mcp.schemas.models import FileAnalysis, SearchResult
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)

_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")


def find_relevant(
    query: str,
    analyses: list[FileAnalysis],
    top_n: int = 10,
) -> list[SearchResult]:
    """Search for files relevant to *query* using keyword scoring.

    Scoring considers: file path tokens, symbol names, docstrings, and module docstrings.
    """
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

    # Bonus for symbol-name exact matches
    symbol_names_lower = {s.name.lower() for s in analysis.symbols}
    for qt in query_tokens:
        if qt in symbol_names_lower:
            score += 2.0
            matched.append(qt)

    # Bonus for path matches
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
