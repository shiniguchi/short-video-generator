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

    # Google AI (Gemini + Imagen + Veo)
    google_api_key: str = ""
    llm_provider_type: str = "mock"  # mock/gemini
    image_provider_type: str = "mock"  # mock/imagen
    imagen_model: str = "imagen-4.0-fast-generate-001"
    imagen_edit_model: str = "imagen-3.0-capability-001"

    # Vertex AI (enables edit_image: subject refs, sketches, style transfer)
    vertex_ai_project: str = ""       # GCP project ID
    vertex_ai_location: str = "europe-west1"
    google_application_credentials: str = ""  # Path to service account JSON key

    # Output
    output_dir: str = "output"

    # Landing Page Generation
    lp_color_scheme: str = "research"  # Options: "extract", "research", "preset"
    lp_color_preset: str = ""  # Preset palette name when lp_color_scheme=preset

    # Cloudflare Analytics
    cf_worker_url: str = ""        # e.g. https://lp-analytics.yourname.workers.dev
    cf_worker_api_key: str = ""    # Bearer token for Worker /analytics endpoint

    # API Quota Limits (Google AI Paid Tier 1 defaults)
    veo_quota_rpm: int = 4
    veo_quota_rpd: int = 10
    imagen_quota_rpm: int = 20
    imagen_quota_rpd: int = 100

    # Cloudflare Pages Deployment
    cf_api_token: str = ""             # CLOUDFLARE_API_TOKEN for wrangler auth
    cf_account_id: str = ""            # Cloudflare Account ID
    cf_pages_project_name: str = ""    # Pages project name (must pre-exist in CF dashboard)


@lru_cache()
def get_settings():
    return Settings()
