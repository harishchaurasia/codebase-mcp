"""Pydantic models for all codebase analysis data structures."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SymbolKind(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"
    IMPORT = "import"


class Language(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    C = "c"
    CPP = "cpp"
    RUBY = "ruby"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    MARKDOWN = "markdown"
    SHELL = "shell"
    SQL = "sql"
    OTHER = "other"


class FileInfo(BaseModel):
    """Basic metadata about a file in the codebase."""

    path: str = Field(description="Relative path from codebase root")
    absolute_path: str = Field(description="Absolute filesystem path")
    language: Language = Field(default=Language.OTHER)
    size_bytes: int = Field(ge=0)
    line_count: int = Field(ge=0)
    extension: str = Field(default="")


class ImportInfo(BaseModel):
    """A single import statement extracted from a file."""

    module: str = Field(description="The module being imported (e.g. 'os.path')")
    names: list[str] = Field(
        default_factory=list,
        description="Specific names imported (e.g. ['join', 'exists'])",
    )
    is_relative: bool = Field(default=False)
    level: int = Field(default=0, description="Number of dots in relative import")
    line_number: int = Field(ge=1)


class Symbol(BaseModel):
    """A code symbol (class, function, variable) extracted from a file."""

    name: str
    kind: SymbolKind
    line_number: int = Field(ge=1)
    end_line_number: int | None = Field(default=None)
    docstring: str | None = Field(default=None)
    decorators: list[str] = Field(default_factory=list)


class FileAnalysis(BaseModel):
    """Full analysis of a single file: metadata + symbols + imports."""

    info: FileInfo
    symbols: list[Symbol] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    module_docstring: str | None = Field(default=None)


class DependencyEdge(BaseModel):
    """A directed edge in the dependency graph: source imports from target."""

    source: str = Field(description="Relative path of the importing file")
    target: str = Field(description="Relative path of the imported file")
    imported_names: list[str] = Field(default_factory=list)


class DependencyGraph(BaseModel):
    """File-level dependency graph for the codebase."""

    nodes: list[str] = Field(description="Relative paths of all files")
    edges: list[DependencyEdge] = Field(default_factory=list)

    def get_dependents(self, file_path: str) -> list[DependencyEdge]:
        """Files that import the given file."""
        return [e for e in self.edges if e.target == file_path]

    def get_dependencies(self, file_path: str) -> list[DependencyEdge]:
        """Files that the given file imports."""
        return [e for e in self.edges if e.source == file_path]


class LanguageBreakdown(BaseModel):
    """Count of files per language."""

    language: Language
    file_count: int
    total_lines: int


class ArchitectureSummary(BaseModel):
    """High-level summary of a codebase's architecture."""

    root_path: str
    total_files: int
    total_lines: int
    languages: list[LanguageBreakdown] = Field(default_factory=list)
    top_level_modules: list[str] = Field(
        default_factory=list,
        description="Top-level directories/packages",
    )
    entry_points: list[str] = Field(
        default_factory=list,
        description="Files that look like entry points (__main__.py, main.py, etc.)",
    )
    key_files: list[str] = Field(
        default_factory=list,
        description="Most-imported or most-connected files",
    )


class SearchResult(BaseModel):
    """A file matching a search query, ranked by relevance (raw pipeline output)."""

    file_path: str
    score: float = Field(ge=0.0)
    matched_symbols: list[str] = Field(default_factory=list)
    context: str = Field(default="", description="Snippet or summary of why this matched")


class MatchBreakdown(BaseModel):
    """Per-signal score breakdown for a search result."""

    keyword_score: float = 0.0
    symbol_score: float = 0.0
    path_score: float = 0.0
    docstring_score: float = 0.0
    dependency_boost: float = 0.0


class RefinedSearchResult(BaseModel):
    """Search result enriched with reasoning, confidence, and score breakdown."""

    file_path: str
    score: float = Field(ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_symbols: list[str] = Field(default_factory=list)
    context: str = Field(default="")
    reasoning: list[ReasoningStep] = Field(
        default_factory=list,
        description="Why this result was selected",
    )
    match_breakdown: MatchBreakdown = Field(default_factory=MatchBreakdown)


# ---------------------------------------------------------------------------
# Structured tool I/O models (agentic layer)
# ---------------------------------------------------------------------------


class SymbolSummary(BaseModel):
    """Compact representation of a code symbol for tool output."""

    name: str
    kind: str
    line: int
    docstring: str | None = None


class ReasoningStep(BaseModel):
    """A single observation in a structured reasoning trace."""

    observation: str
    evidence: str


class FileExplanation(BaseModel):
    """Structured explanation of a single file's role, contents, and reasoning."""

    path: str
    language: str
    lines: int
    module_docstring: str | None = None
    symbols: list[SymbolSummary] = Field(default_factory=list)
    imports_from: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    purpose: str = Field(default="", description="Heuristic one-line purpose summary")
    role: str = Field(
        default="unknown",
        description="Classified role: entry_point, utility, core_logic, test, "
        "test_fixture, config, model, api, or unknown",
    )
    next_files: list[str] = Field(
        default_factory=list,
        description="Files the agent should examine next",
    )
    reasoning: list[ReasoningStep] = Field(
        default_factory=list,
        description="Structured trace of how the explanation was derived",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How confident we are in this explanation (0.0-1.0)",
    )


class FileDependencyInfo(BaseModel):
    """What a file imports and what imports it."""

    file: str
    imports: list[DependencyEdge] = Field(default_factory=list)
    imported_by: list[DependencyEdge] = Field(default_factory=list)


class FileSuggestion(BaseModel):
    """A file suggested for a task, with rationale."""

    file_path: str
    relevance_score: float = Field(ge=0.0)
    reason: str = Field(default="")
    related_files: list[str] = Field(
        default_factory=list,
        description="Files tightly coupled to this one (deps + dependents)",
    )


# ---------------------------------------------------------------------------
# Memory layer models
# ---------------------------------------------------------------------------


class FileFingerprint(BaseModel):
    """Lightweight file identity for change detection (no content read needed)."""

    path: str
    mtime: float
    size_bytes: int


class DetectedPattern(BaseModel):
    """A codebase pattern detected by heuristic analysis."""

    name: str = Field(description="e.g. 'fastapi', 'pytest', 'monorepo'")
    category: str = Field(description="'framework', 'testing', 'structure', 'build'")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(
        default_factory=list,
        description="Files or imports that triggered this detection",
    )


class ScanDiff(BaseModel):
    """Result of comparing cached fingerprints against the current filesystem."""

    added: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.changed or self.removed)


class RepoMemory(BaseModel):
    """Complete persistent memory object for an analyzed repository."""

    version: str = "1"
    root_path: str
    analyzed_at: str = Field(description="ISO-8601 timestamp of last analysis")
    fingerprints: dict[str, FileFingerprint] = Field(default_factory=dict)
    analyses: dict[str, FileAnalysis] = Field(default_factory=dict)
    graph: DependencyGraph = Field(default_factory=lambda: DependencyGraph(nodes=[], edges=[]))
    summary: ArchitectureSummary | None = None
    patterns: list[DetectedPattern] = Field(default_factory=list)
