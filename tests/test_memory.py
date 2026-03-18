"""Tests for the memory store: persistence, fingerprinting, diffing, partial reanalysis."""

from __future__ import annotations

from pathlib import Path

from codebase_mcp.core.codebase import CodebaseAnalyzer
from codebase_mcp.core.config import Settings
from codebase_mcp.core.memory import MemoryStore
from codebase_mcp.schemas.models import (
    ArchitectureSummary,
    FileFingerprint,
    RepoMemory,
)


def _settings_with_memory_dir(tmp_path: Path) -> Settings:
    mem_dir = tmp_path.parent / (tmp_path.name + "_memcache")
    mem_dir.mkdir(exist_ok=True)
    return Settings(memory_dir=str(mem_dir))


# -- MemoryStore unit tests --------------------------------------------------


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = MemoryStore(memory_dir=str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir()

    memory = RepoMemory(
        root_path=str(root),
        analyzed_at=MemoryStore.now_iso(),
        fingerprints={"a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100)},
        summary=ArchitectureSummary(root_path=str(root), total_files=1, total_lines=10),
    )
    store.save(memory)

    loaded = store.load(root)
    assert loaded is not None
    assert loaded.root_path == str(root)
    assert "a.py" in loaded.fingerprints
    assert loaded.summary is not None
    assert loaded.summary.total_files == 1


def test_load_missing_returns_none(tmp_path: Path) -> None:
    store = MemoryStore(memory_dir=str(tmp_path / "cache"))
    assert store.load(tmp_path / "nonexistent") is None


def test_load_corrupt_returns_none(tmp_path: Path) -> None:
    store = MemoryStore(memory_dir=str(tmp_path / "cache"))
    root = tmp_path / "repo"
    root.mkdir()
    path = store.cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("NOT VALID JSON {{{")
    assert store.load(root) is None


def test_fingerprint_directory(tmp_codebase: Path) -> None:
    fps = MemoryStore.fingerprint_directory(tmp_codebase)
    paths = set(fps.keys())
    assert "mypackage/main.py" in paths
    assert "mypackage/utils.py" in paths
    assert "README.md" in paths
    for fp in fps.values():
        assert fp.mtime > 0
        assert fp.size_bytes >= 0


def test_compute_diff_detects_added() -> None:
    cached: dict[str, FileFingerprint] = {
        "a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100),
    }
    current: dict[str, FileFingerprint] = {
        "a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100),
        "b.py": FileFingerprint(path="b.py", mtime=2.0, size_bytes=200),
    }
    diff = MemoryStore.compute_diff(cached, current)
    assert diff.added == ["b.py"]
    assert diff.unchanged == ["a.py"]
    assert diff.has_changes


def test_compute_diff_detects_changed() -> None:
    cached = {"a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100)}
    current = {"a.py": FileFingerprint(path="a.py", mtime=2.0, size_bytes=100)}
    diff = MemoryStore.compute_diff(cached, current)
    assert diff.changed == ["a.py"]
    assert diff.has_changes


def test_compute_diff_detects_removed() -> None:
    cached = {
        "a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100),
        "b.py": FileFingerprint(path="b.py", mtime=1.0, size_bytes=50),
    }
    current = {"a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100)}
    diff = MemoryStore.compute_diff(cached, current)
    assert diff.removed == ["b.py"]
    assert diff.has_changes


def test_compute_diff_no_changes() -> None:
    fps = {"a.py": FileFingerprint(path="a.py", mtime=1.0, size_bytes=100)}
    diff = MemoryStore.compute_diff(fps, fps)
    assert not diff.has_changes
    assert diff.unchanged == ["a.py"]


# -- Integration: CodebaseAnalyzer with memory --------------------------------


def test_full_analysis_creates_cache(tmp_codebase: Path) -> None:
    settings = _settings_with_memory_dir(tmp_codebase)
    analyzer = CodebaseAnalyzer(settings)
    analyzer.analyze(str(tmp_codebase))

    store = MemoryStore(memory_dir=settings.memory_dir)
    assert store.load(tmp_codebase) is not None


def test_cached_analysis_skips_recompute(tmp_codebase: Path) -> None:
    settings = _settings_with_memory_dir(tmp_codebase)

    analyzer1 = CodebaseAnalyzer(settings)
    summary1 = analyzer1.analyze(str(tmp_codebase))

    analyzer2 = CodebaseAnalyzer(settings)
    summary2 = analyzer2.analyze(str(tmp_codebase))

    assert summary1.total_files == summary2.total_files
    assert analyzer2._loaded_from_cache is True


def test_partial_reanalysis(tmp_codebase: Path) -> None:
    settings = _settings_with_memory_dir(tmp_codebase)

    analyzer = CodebaseAnalyzer(settings)
    summary1 = analyzer.analyze(str(tmp_codebase))
    original_count = summary1.total_files

    # Add a new file
    new_file = tmp_codebase / "mypackage" / "new_module.py"
    new_file.write_text('"""New module."""\n\ndef new_func():\n    pass\n')

    analyzer2 = CodebaseAnalyzer(settings)
    summary2 = analyzer2.analyze(str(tmp_codebase))
    assert summary2.total_files == original_count + 1
    assert analyzer2._loaded_from_cache is False

    explanation = analyzer2.explain_file("mypackage/new_module.py")
    assert explanation is not None
    assert explanation.path == "mypackage/new_module.py"


def test_force_ignores_cache(tmp_codebase: Path) -> None:
    settings = _settings_with_memory_dir(tmp_codebase)

    analyzer = CodebaseAnalyzer(settings)
    analyzer.analyze(str(tmp_codebase))

    analyzer2 = CodebaseAnalyzer(settings)
    analyzer2.analyze(str(tmp_codebase), force=True)
    assert analyzer2._loaded_from_cache is False


def test_memory_status_reports_state(tmp_codebase: Path) -> None:
    settings = _settings_with_memory_dir(tmp_codebase)
    analyzer = CodebaseAnalyzer(settings)

    status_before = analyzer.get_memory_status()
    assert status_before["is_loaded"] is False

    analyzer.analyze(str(tmp_codebase))
    status_after = analyzer.get_memory_status()
    assert status_after["is_loaded"] is True
    assert status_after["cached_on_disk"] is True
    assert status_after["file_count"] > 0
    assert "staleness" in status_after
    assert status_after["staleness"]["is_stale"] is False
