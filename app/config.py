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

    # Redis (optional for local dev without Redis)
    redis_url: str = ""

    # Celery
    celery_broker_url: str = "sqla+sqlite:///celery_broker.db"
    celery_result_backend: str = "db+sqlite:///celery_results.db"

    # API
    api_secret_key: str

    # Local config fallback
    local_config_path: str = "config/sample-data.yml"


@lru_cache()
def get_settings():
    return Settings()
