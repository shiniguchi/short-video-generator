"""Abstract base class for video providers."""

from abc import ABC, abstractmethod
from typing import Optional


class VideoProvider(ABC):
    """Abstract interface for video generation providers."""

    @abstractmethod
    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate a video clip and return file path to MP4.

        Args:
            prompt: Visual description of the scene
            duration_seconds: Length of clip in seconds
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated MP4 file
        """
        pass

    @abstractmethod
    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if provider supports the given resolution.

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            True if resolution is supported
        """
        pass
