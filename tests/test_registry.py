"""Tests for the tool registry: registration, discovery, routing, execution."""

from __future__ import annotations

from typing import Any

import pytest

from codebase_mcp.tools.base import BaseTool, ToolMetadata, ToolResult
from codebase_mcp.tools.registry import ToolRegistry


class _DummyTool(BaseTool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="dummy",
            description="A dummy tool for testing",
            trigger_keywords=["test", "dummy"],
            capabilities=["testing"],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(self.name, {"echo": kwargs})


class _FailingTool(BaseTool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="failing", description="Always fails")

    def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("boom")


def test_register_and_get() -> None:
    reg = ToolRegistry()
    tool = _DummyTool()
    reg.register(tool)
    assert reg.get("dummy") is tool
    assert reg.get("nonexistent") is None


def test_duplicate_registration_raises() -> None:
    reg = ToolRegistry()
    reg.register(_DummyTool())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_DummyTool())


def test_list_tools() -> None:
    reg = ToolRegistry()
    reg.register(_DummyTool())
    metas = reg.list_tools()
    assert len(metas) == 1
    assert metas[0].name == "dummy"
    assert "test" in metas[0].trigger_keywords


def test_execute_returns_result() -> None:
    reg = ToolRegistry()
    reg.register(_DummyTool())
    result = reg.execute("dummy", key="value")
    assert result.success
    assert result.data == {"echo": {"key": "value"}}
    assert result.tool_name == "dummy"


def test_execute_unknown_tool() -> None:
    reg = ToolRegistry()
    result = reg.execute("nope")
    assert not result.success
    assert "Unknown tool" in (result.error or "")


def test_execute_catches_exceptions() -> None:
    reg = ToolRegistry()
    reg.register(_FailingTool())
    result = reg.execute("failing")
    assert not result.success
    assert "boom" in (result.error or "")


def test_route_ranks_by_keyword_match() -> None:
    reg = ToolRegistry()
    reg.register(_DummyTool())
    matches = reg.route("run a test", top_n=3)
    assert len(matches) >= 1
    assert matches[0].name == "dummy"


def test_route_returns_empty_for_no_match() -> None:
    reg = ToolRegistry()
    reg.register(_DummyTool())
    matches = reg.route("zzzzz xxxx")
    assert matches == []


def test_discover_finds_real_tools() -> None:
    reg = ToolRegistry()
    reg.discover()
    names = reg.list_names()
    assert "analyze_repo" in names
    assert "explain_file" in names
    assert "find_codebase_references" in names
    assert "suggest_files_for_task" in names
