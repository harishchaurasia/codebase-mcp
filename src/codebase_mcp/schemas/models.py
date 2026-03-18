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
    """A file matching a search query, ranked by relevance."""

    file_path: str
    score: float = Field(ge=0.0)
    matched_symbols: list[str] = Field(default_factory=list)
    context: str = Field(default="", description="Snippet or summary of why this matched")
