# codebase-mcp

An MCP (Model Context Protocol) server that lets AI tools deeply understand a software repository. It scans a local codebase, parses source files, builds a dependency graph, and exposes everything through MCP tools that any compatible AI client can call.

## Features

- **Analyze a codebase** -- scan directories, detect languages, respect `.gitignore`
- **Architecture summary** -- language breakdown, top modules, entry points, key files
- **File search** -- find relevant files for a feature or query via keyword scoring
- **File explanation** -- symbols, docstrings, imports, and dependents for any file
- **Dependency tracing** -- see what a file imports and what imports it
- **Dependency graph** -- full or filtered view of the file-level import graph

## Quick Start

### 1. Install

```bash
# Clone and install
git clone <repo-url> && cd codebase-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure (optional)

```bash
cp .env.example .env
# Edit .env to set defaults like LOG_LEVEL, TRANSPORT, etc.
```

### 3. Run

```bash
# stdio transport (default) -- used by MCP clients
python -m codebase_mcp

# Or use the installed CLI entry point
codebase-mcp
```

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

Add to your MCP settings (`.cursor/mcp.json` in your project or global config):

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

| Tool | Description |
|------|-------------|
| `analyze_codebase(directory)` | Scan and analyze a directory. **Call this first.** |
| `get_architecture_summary()` | Language stats, modules, entry points, key files |
| `find_relevant_files(query, top_n)` | Search for files by keyword relevance |
| `explain_file(file_path)` | Symbols, docstring, imports, and dependents |
| `get_file_dependencies(file_path)` | What a file imports and what imports it |
| `get_dependency_graph(filter_path)` | Full or filtered dependency graph |

## Project Structure

```
src/codebase_mcp/
├── core/
│   ├── codebase.py      # Orchestrator: ties scanning, analysis, querying
│   └── config.py        # pydantic-settings configuration
├── analyzers/
│   ├── scanner.py       # Directory walker with .gitignore support
│   ├── ast_analyzer.py  # Python AST parsing for symbols and imports
│   ├── dependency.py    # File-level dependency graph builder
│   ├── summarizer.py    # Architecture summary generator
│   └── search.py        # Keyword-based file search
├── mcp_server/
│   └── server.py        # FastMCP server with tool definitions
├── schemas/
│   └── models.py        # All Pydantic data models
└── utils/
    ├── logging.py       # structlog configuration
    └── file_utils.py    # File I/O, language detection, gitignore
```

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## License

MIT
