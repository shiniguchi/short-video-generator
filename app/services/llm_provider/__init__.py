"""LLM provider service with swappable providers."""

import logging
from app.config import get_settings
from app.services.llm_provider.base import LLMProvider
from app.services.llm_provider.mock import MockLLMProvider
from app.services.llm_provider.gemini import GeminiLLMProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    """Factory function to create LLM provider based on configuration.

    Provider is selected based on LLM_PROVIDER_TYPE setting:
    - "mock": MockLLMProvider (default for local dev)
    - "gemini": GeminiLLMProvider (requires GOOGLE_API_KEY)

    Falls back to mock if:
    - API key is missing for the selected provider
    - USE_MOCK_DATA is True

    Returns:
        Configured LLMProvider instance
    """
    settings = get_settings()

    # Get provider type from settings (default to mock)
    provider_type = getattr(settings, "llm_provider_type", "mock")
    use_mock_data = getattr(settings, "use_mock_data", True)

    # Create provider based on type
    if provider_type == "gemini":
        google_api_key = getattr(settings, "google_api_key", "")

        # Fall back to mock if no API key or mock mode enabled
        if not google_api_key or use_mock_data:
            if not google_api_key:
                logger.warning("GOOGLE_API_KEY not set, falling back to MockLLMProvider")
            else:
                logger.info("USE_MOCK_DATA=True, using MockLLMProvider")
            return MockLLMProvider()

        return GeminiLLMProvider(api_key=google_api_key)
    else:
        # Default to mock for local development
        return MockLLMProvider()


__all__ = [
    "LLMProvider",
    "MockLLMProvider",
    "GeminiLLMProvider",
    "get_llm_provider"
]
