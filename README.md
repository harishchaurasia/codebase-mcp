# codebase-mcp

An **agent-capable MCP server** that lets AI tools deeply understand a software repository. It scans a local codebase, parses source files, builds a dependency graph, and exposes everything through an agentic tool system with rich metadata, dynamic discovery, and keyword-based routing.

## Architecture

```
MCP Transport (stdio / HTTP)
        │
   MCP Server        ← thin wrapper, auto-registers tools
        │
   Tool Registry     ← dynamic discovery, routing, execution
        │
  ┌─────┴──────────────────────────┐
  │  analyze_repo                  │
  │  explain_file                  │
  │  find_codebase_references      │
  │  suggest_files_for_task        │
  └────────────────────────────────┘
        │
  CodebaseAnalyzer   ← orchestrator (scan → AST → deps → search)
        │
  ┌─────┴──────────────────────────┐
  │  scanner · ast_analyzer        │
  │  dependency · summarizer       │
  │  search                        │
  └────────────────────────────────┘
```

**Key design principle:** the MCP layer is a thin shell. All tool logic lives in `tools/`, all analysis logic lives in `analyzers/`, and the registry can be used directly by any agent loop -- no MCP transport required.

## Features

- **Agentic tool system** -- every tool carries metadata (description, trigger keywords, usage examples, capabilities) that agents use for tool selection
- **Tool registry** -- dynamic discovery, name-based dispatch, and keyword routing
- **Meta-tools** -- `list_tools` and `route_query` let agents introspect the system
- **Dependency-aware suggestions** -- `suggest_files_for_task` enriches search results with the dependency neighbourhood
- **AST analysis** -- extracts classes, functions, variables, imports, and docstrings from Python files
- **Architecture summary** -- language breakdown, top modules, entry points, most-imported files
- **Keyword search** -- TF-IDF scoring over paths, symbol names, and docstrings

## Quick Start

```bash
git clone https://github.com/harishchaurasia/codebase-mcp.git
cd codebase-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Run the MCP server (stdio)

```bash
python -m codebase_mcp
```

### Use the tool registry directly (no MCP needed)

```python
from codebase_mcp.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.discover()

# Route a query to the best tool
matches = registry.route("which files handle auth?")
print(matches[0].name)  # -> "find_codebase_references"

# Execute a tool
result = registry.execute("analyze_repo", directory="/path/to/project")
print(result.data["total_files"])
```

See `examples/client_usage.py` for a full walkthrough.

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codebase-mcp": {
      "command": "/path/to/codebase-mcp/.venv/bin/python",
      "args": ["-m", "codebase_mcp"]
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "codebase-mcp": {
      "command": "/path/to/codebase-mcp/.venv/bin/python",
      "args": ["-m", "codebase_mcp"]
    }
  }
}
```

## Available Tools

### Core tools

| Tool | Description |
|------|-------------|
| `analyze_repo(directory)` | Scan and analyze a directory. **Call this first.** |
| `explain_file(file_path)` | Symbols, docstring, imports, and dependents |
| `find_codebase_references(query, top_n)` | Keyword search for relevant files |
| `suggest_files_for_task(task_description, top_n)` | Dependency-aware file suggestions |

### Meta-tools (agent introspection)

| Tool | Description |
|------|-------------|
| `list_tools()` | All tools with metadata, keywords, and examples |
| `route_query(query, top_n)` | Which tools best match a natural-language request |

### Tool Metadata

Every tool carries structured metadata for agentic selection:

```python
ToolMetadata(
    name="suggest_files_for_task",
    description="Given a task description, suggest which files...",
    trigger_keywords=["suggest", "recommend", "task", "implement", ...],
    usage_examples=["suggest_files_for_task(task_description='Add rate limiting')"],
    capabilities=["planning", "search", "dependency-analysis"],
)
```

## Project Structure

```
src/codebase_mcp/
├── tools/                  # Agentic tool layer
│   ├── base.py             # BaseTool, ToolMetadata, ToolResult
│   ├── registry.py         # ToolRegistry (discover, route, execute)
│   ├── _context.py         # Shared analyzer singleton
│   ├── analyze_repo.py     # AnalyzeRepoTool
│   ├── explain_file.py     # ExplainFileTool
│   ├── find_references.py  # FindCodebaseReferencesTool
│   └── suggest_files.py    # SuggestFilesForTaskTool
├── mcp_server/
│   └── server.py           # Thin MCP shell (auto-registers from registry)
├── core/
│   ├── codebase.py         # Orchestrator
│   └── config.py           # pydantic-settings
├── analyzers/
│   ├── scanner.py          # .gitignore-aware file walker
│   ├── ast_analyzer.py     # Python AST parser
│   ├── dependency.py       # Import graph builder
│   ├── summarizer.py       # Architecture summary
│   └── search.py           # TF-IDF keyword search
├── schemas/
│   └── models.py           # Pydantic data models + tool I/O types
└── utils/
    ├── logging.py          # structlog configuration
    └── file_utils.py       # File I/O, language detection
```

## Development

```bash
# Run tests (45 tests)
python -m pytest tests/ -v

# Lint
ruff check src/ tests/ examples/
ruff format src/ tests/ examples/
```

## License

MIT
