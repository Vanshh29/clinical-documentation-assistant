from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://cda:change-me-local-only@localhost:5432/cda"

    auth_jwt_secret: str = Field(default="dev-only-change-me-at-least-32-characters", min_length=32)
    auth_jwt_issuer: str = "http://localhost:8000"
    auth_jwt_audience: str = "cda-web"
    auth_access_token_ttl_minutes: int = 30

    max_note_chars: int = 50_000
    retention_days: int = 30
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
