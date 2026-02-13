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

    # Trend Intelligence
    use_mock_data: bool = True  # Default to mock for local dev
    apify_api_token: str = ""
    youtube_api_key: str = ""
    anthropic_api_key: str = ""

    # Schedule
    trend_scrape_interval_hours: int = 6
    trend_analysis_delay_minutes: int = 30


@lru_cache()
def get_settings():
    return Settings()
