"""Application settings, sourced from the environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "herbaflow"
    database_url: str = ""

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
