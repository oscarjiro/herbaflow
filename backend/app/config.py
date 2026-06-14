"""Application settings, sourced from the environment."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root ``.env`` (config.py lives at ``backend/app/config.py``), resolved as an
# absolute path so the URL loads no matter the launch cwd (running from ``backend/``
# previously missed the cwd-relative ``.env`` → empty ``database_url`` → DB routes 500).
# Real environment variables still take precedence; a missing file is skipped silently.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")
    app_name: str = "herbaflow"
    database_url: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_url: str = "https://herbaflow.app"

    @property
    def cors_origins_list(self) -> list[str]:
        """Allowed browser origins for CORS (comma-separated in the environment)."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        """The configured URL normalized to the asyncpg driver."""
        url = self.database_url
        for prefix in ("postgresql+asyncpg://",):
            if url.startswith(prefix):
                return url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]
        return url


settings = Settings()
