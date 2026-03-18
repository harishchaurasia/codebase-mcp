"""Rule-based task decomposition into searchable sub-goals.

Extracts an *action* (add, fix, refactor, ...) and one or more *domains*
(authentication, api, data, ...) from the task description, then generates
prioritised sub-tasks whose ``search_query`` can be fed directly into
``find_relevant()``.
"""

from __future__ import annotations

import re

from codebase_mcp.schemas.models import SubTask

_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")

# ---------------------------------------------------------------------------
# Action classification
# ---------------------------------------------------------------------------

_ACTION_KEYWORDS: dict[str, list[str]] = {
    "add": ["add", "create", "implement", "build", "introduce", "new"],
    "fix": ["fix", "debug", "resolve", "patch", "repair", "hotfix"],
    "refactor": ["refactor", "restructure", "clean", "reorganize", "simplify"],
    "remove": ["remove", "delete", "drop", "deprecate"],
    "test": ["test", "verify", "validate", "cover", "spec"],
    "modify": ["update", "modify", "change", "adjust", "tweak", "upgrade"],
}

# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "authentication": {
        "auth", "login", "jwt", "oauth", "session", "token",
        "password", "credential", "signup", "signin",
    },
    "api": {
        "api", "endpoint", "route", "handler", "rest",
        "graphql", "request", "response", "controller",
    },
    "data": {
        "database", "db", "model", "schema", "migration",
        "orm", "query", "table", "entity", "repository",
    },
    "configuration": {
        "config", "settings", "env", "environment", "dotenv",
        "option", "parameter",
    },
    "middleware": {
        "middleware", "interceptor", "hook", "filter", "pipe",
    },
    "testing": {
        "test", "spec", "fixture", "mock", "stub", "assertion",
        "pytest", "unittest", "jest",
    },
    "frontend": {
        "ui", "frontend", "component", "template", "view",
        "page", "layout", "style", "css", "html",
    },
    "observability": {
        "log", "logging", "monitor", "trace", "metric",
        "alert", "debug", "profil",
    },
}

# Determines the order in which sub-tasks appear.  Lower = earlier.
_DOMAIN_PRIORITY: dict[str, int] = {
    "configuration": 1,
    "data": 2,
    "authentication": 3,
    "middleware": 4,
    "api": 5,
    "frontend": 6,
    "observability": 7,
    "testing": 8,
}

# Search-query fragments used when generating the "core" sub-task per domain.
_DOMAIN_SEARCH_TERMS: dict[str, str] = {
    "authentication": "auth login session token",
    "api": "route endpoint handler api",
    "data": "model schema database migration",
    "configuration": "config settings environment",
    "middleware": "middleware interceptor hook",
    "testing": "test fixture mock",
    "frontend": "component template view page",
    "observability": "log logging monitor trace",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def decompose_task(description: str) -> list[SubTask]:
    """Break a task description into prioritised sub-tasks.

    Returns an empty list when *description* is blank.
    """
    tokens = _tokenize(description)
    if not tokens:
        return []

    action = _extract_action(tokens)
    domains = _extract_domains(tokens)
    raw_query = " ".join(tokens)

    subtasks: list[SubTask] = []

    # id=1 is a placeholder; _assign_priorities overwrites all ids.
    if domains:
        for domain in domains:
            search_terms = _DOMAIN_SEARCH_TERMS.get(domain, raw_query)
            query = f"{raw_query} {search_terms}"
            subtasks.append(SubTask(
                id=1,
                label=f"Find core {domain} files",
                search_query=query,
                reasoning=f"Domain '{domain}' detected in task description",
            ))

        subtasks.append(SubTask(
            id=1,
            label="Find configuration",
            search_query="config settings environment",
            reasoning="Configuration files may need updating for this task",
        ))

        if action == "add":
            subtasks.append(SubTask(
                id=1,
                label="Find entry points and routes",
                search_query=f"{raw_query} route endpoint main entry",
                reasoning="New feature likely requires wiring into entry points",
            ))

        if action == "fix":
            subtasks.append(SubTask(
                id=1,
                label="Find error handling",
                search_query=f"{raw_query} error exception handler",
                reasoning="Bug fix may involve error handling paths",
            ))

        if "testing" not in domains:
            subtasks.append(SubTask(
                id=1,
                label="Find related tests",
                search_query=f"test {raw_query}",
                reasoning="Tests should be updated alongside implementation",
            ))
    else:
        subtasks.append(SubTask(
            id=1,
            label="Find relevant files",
            search_query=raw_query,
            reasoning=(
                "No specific domain detected; "
                "searching with full task description"
            ),
        ))
        subtasks.append(SubTask(
            id=1,
            label="Find related tests",
            search_query=f"test {raw_query}",
            reasoning="Tests should be updated alongside implementation",
        ))

    _assign_priorities(subtasks)
    return subtasks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    parts = _SPLIT_RE.split(text.lower())
    return [p for p in parts if p and len(p) > 1]


def _extract_action(tokens: list[str]) -> str:
    for action, keywords in _ACTION_KEYWORDS.items():
        if any(t in keywords for t in tokens):
            return action
    return "modify"


def _extract_domains(tokens: list[str]) -> list[str]:
    found: list[str] = []
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(t in keywords for t in tokens):
            found.append(domain)
    found.sort(key=lambda d: _DOMAIN_PRIORITY.get(d, 99))
    return found


def _assign_priorities(subtasks: list[SubTask]) -> None:
    """Assign sequential 1-based ids reflecting execution order."""
    label_prio = {
        "Find configuration": 1,
        "Find error handling": 2,
    }
    suffix_prio = {
        "tests": 90,
        "routes": 50,
    }

    def _sort_key(st: SubTask) -> int:
        if st.label in label_prio:
            return label_prio[st.label]
        for suffix, prio in suffix_prio.items():
            if suffix in st.label.lower():
                return prio
        return 10

    subtasks.sort(key=_sort_key)
    for idx, st in enumerate(subtasks, start=1):
        st.id = idx
