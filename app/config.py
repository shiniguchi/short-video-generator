from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra env vars like POSTGRES_* used by docker-compose
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # API
    api_secret_key: str

    # Local config fallback
    local_config_path: str = "config/sample-data.yml"


@lru_cache()
def get_settings():
    return Settings()
