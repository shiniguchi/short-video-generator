"""Avatar generator service with factory function."""

from typing import Optional

from app.config import get_settings
from app.services.avatar_generator.base import AvatarProvider
from app.services.avatar_generator.mock import MockAvatarProvider
from app.services.avatar_generator.heygen import HeyGenAvatarProvider


class AvatarGeneratorService:
    """Avatar generator service that wraps a provider."""

    def __init__(self, provider: AvatarProvider, output_dir: str):
        """Initialize avatar generator service.

        Args:
            provider: Avatar provider implementation
            output_dir: Base directory for output files
        """
        self.provider = provider
        self.output_dir = output_dir

    def generate_avatar_video(
        self,
        script_text: str,
        avatar_id: str = "default",
        voice_id: str = "default"
    ) -> str:
        """Generate avatar video from script text.

        Args:
            script_text: Script text for the avatar to speak
            avatar_id: Avatar identifier (provider-specific)
            voice_id: Voice identifier (provider-specific)

        Returns:
            Path to generated avatar video file
        """
        return self.provider.generate_avatar_video(script_text, avatar_id, voice_id)


def get_avatar_generator() -> AvatarGeneratorService:
    """Factory function to create avatar generator with appropriate provider.

    Reads avatar_provider_type from settings and instantiates the corresponding provider.
    Defaults to MockAvatarProvider if type is unrecognized or not configured.

    Returns:
        AvatarGeneratorService instance with selected provider
    """
    settings = get_settings()

    if settings.avatar_provider_type == "heygen":
        provider = HeyGenAvatarProvider(
            api_key=settings.heygen_api_key,
            output_dir=settings.output_dir,
            default_avatar_id=settings.heygen_avatar_id
        )
    else:
        # Default to mock provider
        provider = MockAvatarProvider(output_dir=settings.output_dir)

    return AvatarGeneratorService(provider=provider, output_dir=settings.output_dir)
