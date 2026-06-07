"""Application settings, sourced from the environment."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. DATABASE_URL/CORS wired in later phases."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "herbaflow"


settings = Settings()
