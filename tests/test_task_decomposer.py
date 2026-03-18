"""Tests for the rule-based task decomposer."""

from __future__ import annotations

from codebase_mcp.analyzers.task_decomposer import decompose_task


def test_decompose_add_auth() -> None:
    subtasks = decompose_task("Add JWT auth")
    assert len(subtasks) >= 3
    labels = [st.label for st in subtasks]
    assert any("auth" in lb.lower() for lb in labels)
    assert any("config" in lb.lower() for lb in labels)
    assert any("test" in lb.lower() for lb in labels)


def test_decompose_fix_bug() -> None:
    subtasks = decompose_task("Fix login error")
    labels = [st.label for st in subtasks]
    assert any("error" in lb.lower() for lb in labels)
    assert any("auth" in lb.lower() for lb in labels)


def test_decompose_generic_fallback() -> None:
    subtasks = decompose_task("improve performance")
    assert len(subtasks) >= 1
    labels = [st.label for st in subtasks]
    assert any("relevant" in lb.lower() or "test" in lb.lower() for lb in labels)


def test_subtask_ids_are_sequential() -> None:
    subtasks = decompose_task("Add authentication middleware")
    ids = [st.id for st in subtasks]
    assert ids == list(range(1, len(subtasks) + 1))


def test_decompose_empty_returns_empty() -> None:
    assert decompose_task("") == []
    assert decompose_task("   ") == []
