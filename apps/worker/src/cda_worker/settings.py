from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://cda:change-me-local-only@localhost:5432/cda"
    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_topic_note_submitted: str = "note.submitted"
    kafka_group_id: str = "cda-worker"

    pii_encryption_key: str = ""

    llm_provider: str = "fake"  # fake | openrouter
    openrouter_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 60.0
    llm_max_input_tokens: int = 8000
    llm_max_retries: int = 3  # transport retries inside the provider
    llm_max_validation_retries: int = 2  # re-asks with the validation error fed back
    llm_price_in_per_mtok: Decimal = Decimal("0")
    llm_price_out_per_mtok: Decimal = Decimal("0")
    prompt_version: str = "v1"

    outbox_poll_seconds: float = 0.5
    stuck_after_minutes: int = 10
    log_level: str = "INFO"


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
