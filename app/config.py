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

    # Content Generation (Phase 3)
    openai_api_key: str = ""  # For TTS provider (OpenAI)
    elevenlabs_api_key: str = ""  # For TTS provider (ElevenLabs)
    fish_audio_api_key: str = ""  # For TTS provider (Fish Audio)
    fal_key: str = ""  # For fal.ai video providers (Kling, Minimax)
    heygen_api_key: str = ""  # For HeyGen avatar provider
    video_provider_type: str = "mock"  # mock/svd/kling/minimax/veo
    tts_provider_type: str = "mock"  # mock/openai/elevenlabs/fish
    avatar_provider_type: str = "mock"  # mock/heygen
    heygen_avatar_id: str = ""  # Default avatar ID from HeyGen dashboard
    google_api_key: str = ""  # Google AI API key (Gemini, Imagen, Veo)
    llm_provider_type: str = "mock"  # mock/gemini
    image_provider_type: str = "mock"  # mock/imagen
    output_dir: str = "output"  # Base directory for generated files

    # Video Composition (Phase 4)
    background_music_path: str = ""  # Path to background music file (empty = no music)
    music_volume: float = 0.3  # Background music volume (0.0-1.0), default 30%
    thumbnail_timestamp: float = 2.0  # Seconds into video to extract thumbnail frame
    composition_output_dir: str = "output/review"  # Directory for composed videos (REVIEW-01)

    # Review & Output (Phase 5)
    approved_output_dir: str = "output/approved"  # Directory for approved videos
    rejected_output_dir: str = "output/rejected"  # Directory for rejected videos


@lru_cache()
def get_settings():
    return Settings()
