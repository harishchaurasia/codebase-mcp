"""Persistent memory store: save, load, fingerprint, and diff repo analysis."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from codebase_mcp.schemas.models import FileFingerprint, RepoMemory, ScanDiff
from codebase_mcp.utils.file_utils import load_gitignore, should_skip_dir
from codebase_mcp.utils.logging import get_logger

logger = get_logger(__name__)

MEMORY_FILENAME = "memory.json"
MEMORY_VERSION = "1"


class MemoryStore:
    """Handles persistence of RepoMemory to disk and change detection."""

    def __init__(self, memory_dir: str | None = None) -> None:
        self._memory_dir = Path(memory_dir) if memory_dir else None

    def cache_path(self, root: Path) -> Path:
        """Return the JSON file path for a given repo root."""
        if self._memory_dir:
            dir_hash = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
            cache_dir = self._memory_dir / dir_hash
        else:
            cache_dir = root / ".codebase-mcp"
        return cache_dir / MEMORY_FILENAME

    def load(self, root: Path) -> RepoMemory | None:
        """Load cached memory from disk. Returns None if missing or corrupt."""
        path = self.cache_path(root)
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8")
            memory = RepoMemory.model_validate_json(text)
            if memory.version != MEMORY_VERSION:
                logger.info("memory version mismatch, ignoring cache", path=str(path))
                return None
            logger.info("loaded memory from cache", path=str(path))
            return memory
        except Exception:
            logger.warning("failed to load memory cache", path=str(path), exc_info=True)
            return None

    def save(self, memory: RepoMemory) -> None:
        """Atomically write memory to disk (write tmp, then rename)."""
        root = Path(memory.root_path)
        path = self.cache_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = memory.model_dump_json(indent=2)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix="memory_",
            )
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                Path(tmp_path).replace(path)
            except Exception:
                Path(tmp_path).unlink(missing_ok=True)
                raise
            logger.info("saved memory to cache", path=str(path))
        except OSError:
            logger.warning("failed to save memory cache", path=str(path), exc_info=True)

    @staticmethod
    def fingerprint_directory(
        root: Path,
        max_file_size: int = 1_048_576,
    ) -> dict[str, FileFingerprint]:
        """Fast os.stat walk that builds fingerprints without reading file contents."""
        root = root.resolve()
        if not root.is_dir():
            return {}
        gitignore = load_gitignore(root)
        fingerprints: dict[str, FileFingerprint] = {}
        _fingerprint_walk(root, root, gitignore, max_file_size, fingerprints)
        return fingerprints

    @staticmethod
    def compute_diff(
        cached: dict[str, FileFingerprint],
        current: dict[str, FileFingerprint],
    ) -> ScanDiff:
        """Compare two fingerprint dicts and return what changed."""
        cached_paths = set(cached)
        current_paths = set(current)

        added = sorted(current_paths - cached_paths)
        removed = sorted(cached_paths - current_paths)

        changed: list[str] = []
        unchanged: list[str] = []
        for p in sorted(cached_paths & current_paths):
            old, new = cached[p], current[p]
            if old.mtime != new.mtime or old.size_bytes != new.size_bytes:
                changed.append(p)
            else:
                unchanged.append(p)

        return ScanDiff(added=added, changed=changed, removed=removed, unchanged=unchanged)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()


def _fingerprint_walk(
    current: Path,
    root: Path,
    gitignore: object | None,
    max_file_size: int,
    out: dict[str, FileFingerprint],
) -> None:
    """Recursive walk collecting FileFingerprint entries."""
    try:
        entries = sorted(current.iterdir(), key=lambda p: p.name)
    except PermissionError:
        return

    for entry in entries:
        rel = str(entry.relative_to(root))

        if entry.is_dir():
            if should_skip_dir(entry.name):
                continue
            if entry.name == ".codebase-mcp":
                continue
            if gitignore and gitignore.match_file(rel + "/"):
                continue
            _fingerprint_walk(entry, root, gitignore, max_file_size, out)

        elif entry.is_file():
            if gitignore and gitignore.match_file(rel):
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            if st.st_size > max_file_size:
                continue
            out[rel] = FileFingerprint(
                path=rel,
                mtime=st.st_mtime,
                size_bytes=st.st_size,
            )
