"""Heuristic pattern detection: frameworks, test tools, build systems, structure."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from codebase_mcp.schemas.models import DetectedPattern, FileAnalysis

FRAMEWORK_IMPORTS: dict[str, tuple[str, str]] = {
    "fastapi": ("fastapi", "framework"),
    "django": ("django", "framework"),
    "flask": ("flask", "framework"),
    "starlette": ("starlette", "framework"),
    "tornado": ("tornado", "framework"),
    "aiohttp": ("aiohttp", "framework"),
    "react": ("react", "framework"),
    "next": ("nextjs", "framework"),
    "express": ("express", "framework"),
    "vue": ("vue", "framework"),
    "angular": ("angular", "framework"),
    "gin": ("gin", "framework"),
    "sqlalchemy": ("sqlalchemy", "database"),
    "alembic": ("alembic", "database"),
    "prisma": ("prisma", "database"),
    "celery": ("celery", "task-queue"),
    "redis": ("redis", "cache"),
}

TEST_IMPORTS: dict[str, str] = {
    "pytest": "pytest",
    "unittest": "unittest",
    "jest": "jest",
    "mocha": "mocha",
    "nose": "nose2",
}

BUILD_FILES: dict[str, tuple[str, str]] = {
    "pyproject.toml": ("pyproject", "python"),
    "setup.py": ("setup.py", "python"),
    "setup.cfg": ("setup.cfg", "python"),
    "package.json": ("npm", "javascript"),
    "Cargo.toml": ("cargo", "rust"),
    "go.mod": ("go-modules", "go"),
    "pom.xml": ("maven", "java"),
    "build.gradle": ("gradle", "java"),
    "Makefile": ("make", "general"),
    "CMakeLists.txt": ("cmake", "c/cpp"),
    "Gemfile": ("bundler", "ruby"),
}

CI_PATHS = {
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci",
    "Jenkinsfile",
    ".travis.yml",
}

DOCKER_FILES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}


def detect_patterns(analyses: list[FileAnalysis]) -> list[DetectedPattern]:
    """Run all heuristic detectors and return discovered patterns."""
    patterns: list[DetectedPattern] = []
    patterns.extend(_detect_frameworks(analyses))
    patterns.extend(_detect_test_frameworks(analyses))
    patterns.extend(_detect_build_tools(analyses))
    patterns.extend(_detect_structure(analyses))
    return patterns


def _detect_frameworks(analyses: list[FileAnalysis]) -> list[DetectedPattern]:
    hits: dict[str, list[str]] = defaultdict(list)
    for a in analyses:
        for imp in a.imports:
            top_module = imp.module.split(".")[0]
            if top_module in FRAMEWORK_IMPORTS:
                name, _cat = FRAMEWORK_IMPORTS[top_module]
                hits[top_module].append(a.info.path)

    patterns: list[DetectedPattern] = []
    for mod, files in hits.items():
        name, category = FRAMEWORK_IMPORTS[mod]
        patterns.append(DetectedPattern(
            name=name,
            category=category,
            confidence=min(1.0, len(files) / 3),
            evidence=files[:5],
        ))
    return patterns


def _detect_test_frameworks(analyses: list[FileAnalysis]) -> list[DetectedPattern]:
    hits: dict[str, list[str]] = defaultdict(list)
    for a in analyses:
        for imp in a.imports:
            top_module = imp.module.split(".")[0]
            if top_module in TEST_IMPORTS:
                hits[top_module].append(a.info.path)

    patterns: list[DetectedPattern] = []
    for mod, files in hits.items():
        patterns.append(DetectedPattern(
            name=TEST_IMPORTS[mod],
            category="testing",
            confidence=min(1.0, len(files) / 2),
            evidence=files[:5],
        ))
    return patterns


def _detect_build_tools(analyses: list[FileAnalysis]) -> list[DetectedPattern]:
    all_paths = {a.info.path for a in analyses}
    all_names = {Path(p).name for p in all_paths}
    patterns: list[DetectedPattern] = []

    for filename, (name, _lang) in BUILD_FILES.items():
        if filename in all_names:
            matching = [p for p in all_paths if Path(p).name == filename]
            patterns.append(DetectedPattern(
                name=name,
                category="build",
                confidence=1.0,
                evidence=matching[:3],
            ))
    return patterns


def _detect_structure(analyses: list[FileAnalysis]) -> list[DetectedPattern]:
    all_paths = {a.info.path for a in analyses}
    patterns: list[DetectedPattern] = []

    # Monorepo: multiple top-level directories with their own build files
    top_dirs: set[str] = set()
    for p in all_paths:
        parts = Path(p).parts
        if len(parts) > 1:
            top_dirs.add(parts[0])
    build_names = set(BUILD_FILES.keys())
    packages_with_build = [
        d for d in top_dirs
        if any(Path(p).parts[0] == d and Path(p).name in build_names for p in all_paths)
    ]
    if len(packages_with_build) >= 2:
        patterns.append(DetectedPattern(
            name="monorepo",
            category="structure",
            confidence=min(1.0, len(packages_with_build) / 3),
            evidence=packages_with_build[:5],
        ))

    # CI detection
    for ci_path in CI_PATHS:
        if any(p.startswith(ci_path) or p == ci_path for p in all_paths):
            patterns.append(DetectedPattern(
                name="ci-pipeline",
                category="structure",
                confidence=1.0,
                evidence=[p for p in all_paths if p.startswith(ci_path) or p == ci_path][:3],
            ))
            break

    # Docker detection
    docker_names = {Path(p).name for p in all_paths} & DOCKER_FILES
    if docker_names:
        patterns.append(DetectedPattern(
            name="docker",
            category="structure",
            confidence=1.0,
            evidence=sorted(docker_names),
        ))

    return patterns
