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
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,https://herbaflow-oscarjiro.vercel.app"
    )
    frontend_url: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 10
    db_pool_recycle: int = 1800
    db_connect_timeout: int = 5
    # Security controls. Budgets are env-configurable; rate limits use slowapi's
    # "<count>/<period>" syntax. rate_limit_enabled is toggled off in tests (conftest).
    max_request_bytes: int = 1_048_576  # 1 MB request-body cap
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_create: str = "5/minute"
    rate_limit_validate: str = "20/minute"

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
