"""Application configuration backed by pydantic-settings and .env files."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration for codebase-mcp, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    codebase_root: str | None = Field(
        default=None,
        description="Path to the codebase to analyze. Can be set per-request via MCP tools.",
    )
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console", description="'console' or 'json'")
    max_file_size: int = Field(
        default=1_048_576,
        description="Skip files larger than this (bytes)",
    )
    transport: str = Field(default="stdio", description="'stdio' or 'http'")
    http_host: str = Field(default="127.0.0.1")
    http_port: int = Field(default=8000)

    excluded_patterns: list[str] = Field(
        default_factory=lambda: ["*.pyc", "*.pyo", "*.so", "*.dylib"],
        description="Glob patterns for files to exclude from analysis",
    )


def get_settings() -> Settings:
    """Create a Settings instance (reads from env / .env on each call)."""
    return Settings()
