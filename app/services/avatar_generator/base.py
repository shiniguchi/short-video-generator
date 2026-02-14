"""Abstract base class for avatar providers."""

from abc import ABC, abstractmethod
from typing import List, Optional


class AvatarProvider(ABC):
    """Abstract interface for avatar video generation providers."""

    @abstractmethod
    def generate_avatar_video(
        self,
        script_text: str,
        avatar_id: str = "default",
        voice_id: str = "default"
    ) -> str:
        """Generate a talking-head avatar video from script text.

        Args:
            script_text: Script text for the avatar to speak
            avatar_id: Avatar identifier (provider-specific)
            voice_id: Voice identifier (provider-specific)

        Returns:
            Path to generated MP4 file with talking head and embedded audio
        """
        pass

    @abstractmethod
    def get_available_avatars(self) -> List[str]:
        """List available avatar identifiers.

        Returns:
            List of avatar identifiers
        """
        pass
