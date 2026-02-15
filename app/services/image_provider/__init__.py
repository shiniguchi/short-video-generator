"""Image provider factory and exports."""

import os

from app.config import get_settings
from app.services.image_provider.base import ImageProvider
from app.services.image_provider.mock import MockImageProvider
from app.services.image_provider.google_imagen import GoogleImagenProvider


def get_image_provider() -> ImageProvider:
    """Factory function to create image provider with configured provider.

    Provider is selected based on IMAGE_PROVIDER_TYPE setting:
    - "mock": MockImageProvider (default for local dev)
    - "imagen": GoogleImagenProvider (requires GOOGLE_API_KEY)

    Returns:
        Configured ImageProvider instance
    """
    settings = get_settings()

    # Get provider type from settings (default to mock)
    provider_type = getattr(settings, "image_provider_type", "mock")
    output_dir = getattr(settings, "output_dir", "output")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Create provider based on type
    if provider_type == "imagen":
        google_api_key = getattr(settings, "google_api_key", "")
        # Fall back to mock if no API key or USE_MOCK_DATA is True
        if not google_api_key or settings.use_mock_data:
            print("Warning: IMAGE_PROVIDER_TYPE is 'imagen' but GOOGLE_API_KEY "
                  "is empty or USE_MOCK_DATA is True. Using mock provider.")
            return MockImageProvider(output_dir=output_dir)
        return GoogleImagenProvider(api_key=google_api_key, output_dir=output_dir)
    else:
        # Default to mock for local development
        return MockImageProvider(output_dir=output_dir)


__all__ = [
    "ImageProvider",
    "MockImageProvider",
    "GoogleImagenProvider",
    "get_image_provider"
]
