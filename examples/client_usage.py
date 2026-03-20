#!/usr/bin/env python3
"""Example: using codebase-mcp tools directly (without MCP transport).

This shows how an agent loop or test harness can interact with the tool
registry programmatically -- no stdio/HTTP needed.

Usage:
    python examples/client_usage.py /path/to/some/codebase
"""

from __future__ import annotations

import json
import sys

from codebase_mcp.tools.registry import ToolRegistry


def main(codebase_path: str) -> None:
    registry = ToolRegistry()
    registry.discover()

    # 1. List available tools and their metadata
    print("=== Available Tools ===")
    for meta in registry.list_tools():
        print(f"\n  {meta.name}")
        print(f"    {meta.description[:80]}...")
        print(f"    triggers: {meta.trigger_keywords}")
        print(f"    capabilities: {meta.capabilities}")

    # 2. Route a natural-language query to the best tool
    query = "Which files handle user authentication?"
    print(f"\n=== Routing query: '{query}' ===")
    matches = registry.route(query, top_n=2)
    for m in matches:
        print(f"  -> {m.name}")

    # 3. Analyze the codebase
    print(f"\n=== Analyzing {codebase_path} ===")
    result = registry.execute("analyze_repo", directory=codebase_path)
    print(f"  success={result.success}  files={result.data.get('total_files')}")

    # 4. Suggest files for a task
    print("\n=== Suggest files for 'add logging to API endpoints' ===")
    result = registry.execute(
        "suggest_files_for_task",
        task_description="add logging to API endpoints",
        top_n=3,
    )
    if result.success:
        for s in result.data.get("suggestions", []):
            print(f"  {s['file_path']}  (score={s['relevance_score']})")
            if s["related_files"]:
                print(f"    related: {s['related_files']}")

    # 5. Explain a specific file
    if result.success and result.data.get("suggestions"):
        first = result.data["suggestions"][0]["file_path"]
        print(f"\n=== Explain file: {first} ===")
        explanation = registry.execute("explain_file", file_path=first)
        if explanation.success:
            print(json.dumps(explanation.data, indent=2)[:500])


def agent_loop_demo(codebase_path: str) -> None:
    """Run the minimal agent loop against a codebase."""
    from codebase_mcp.agent import AgentLoopConfig, run_agent_loop

    result = run_agent_loop(
        goal="find where configuration is defined",
        directory=codebase_path,
        config=AgentLoopConfig(max_iterations=6),
    )

    print(f"\n=== Agent Loop (done={result.done}, reason={result.stop_reason}) ===")
    for step in result.trace:
        print(f"  [{step.iteration}] {step.selected_tool}: {step.observation}")
    print(f"\n  Final candidate files: {result.final_result.get('candidate_files', [])}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <codebase-path>")
        sys.exit(1)
    main(sys.argv[1])
    agent_loop_demo(sys.argv[1])
