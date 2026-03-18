"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from codebase_mcp.core.config import Settings


@pytest.fixture()
def tmp_codebase(tmp_path: Path) -> Path:
    """Create a small synthetic Python project inside tmp_path."""
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""My sample package."""\n')

    (pkg / "main.py").write_text(dedent("""\
        \"\"\"Entry point for the app.\"\"\"

        from mypackage.utils import helper


        def run() -> None:
            \"\"\"Start the application.\"\"\"
            print(helper())


        if __name__ == "__main__":
            run()
    """))

    (pkg / "utils.py").write_text(dedent("""\
        \"\"\"Utility helpers.\"\"\"

        import os
        from pathlib import Path


        CONSTANT = 42


        def helper() -> str:
            \"\"\"Return a greeting.\"\"\"
            return "hello"


        class Config:
            \"\"\"Application configuration.\"\"\"
            debug: bool = False
    """))

    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "module_a.py").write_text(dedent("""\
        \"\"\"Sub-module A.\"\"\"

        from mypackage.utils import helper


        def feature_a() -> str:
            return helper() + " from A"
    """))

    (tmp_path / "README.md").write_text("# Test Project\n")

    return tmp_path


@pytest.fixture()
def default_settings() -> Settings:
    """Return a Settings instance with defaults."""
    return Settings()
