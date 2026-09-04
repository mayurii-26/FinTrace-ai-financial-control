"""
Application configuration for FinTrace.

All configuration is loaded from environment variables (and a local .env
file for development convenience). No secret or credential is ever
hardcoded in source code - see .env.example at the repository root.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the repository root.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
_BACKEND_ROOT = _THIS_FILE.parents[2]


class Settings(BaseSettings):
    """Central application settings, populated from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), str(_BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: str = "local"
    app_name: str = "FinTrace"
    api_prefix: str = "/api"
    log_level: str = "INFO"

    # Database
    database_url: str = ""

    # Synthetic data
    synthetic_record_count: int = 600
    synthetic_seed: int = 42

    # AI / LLM
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    agent_investigation_limit: int = 50

    # Razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_mode: str = "test"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalize the configured DATABASE_URL, falling back to a local
        SQLite file so the project runs out-of-the-box with zero setup."""
        url = (self.database_url or "").strip()
        if not url:
            db_path = _BACKEND_ROOT / "fintrace.db"
            return f"sqlite:///{db_path.as_posix()}"
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor - safe to call anywhere in the app."""
    return Settings()
