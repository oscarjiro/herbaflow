# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    database_url: str

    # --- Security / hardening (Wave 4) ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_create: str = "10/minute"
    rate_limit_export: str = "30/minute"
    max_request_bytes: int = 2_097_152  # 2 MB

    model_config = {
        "env_file": str(Path(__file__).parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        if "supabase" in url and "ssl" not in url:
            url += "?ssl=require"
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
