from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Backend settings.

    Loads from environment variables and optional `.env` at repo root / confluence-mcp/.env
    to stay compatible with the existing MCP server setup.
    """

    model_config = SettingsConfigDict(
        # config.py -> core -> app -> backend -> python -> repo root
        env_file=str(Path(__file__).resolve().parents[4] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Atlassian (Jira + Confluence)
    confluence_url: str = Field(alias="CONFLUENCE_URL")
    confluence_email: str = Field(alias="CONFLUENCE_EMAIL")
    confluence_api_token: str = Field(alias="CONFLUENCE_API_TOKEN")

    # App
    app_name: str = "weekly-progress"
    api_prefix: str = "/api"
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Storage
    sqlite_path: str = Field(default="data/weekly_progress.db", alias="SQLITE_PATH")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

