"""Abstract base class for TTS providers."""

from abc import ABC, abstractmethod
from typing import List, Optional


class TTSProvider(ABC):
    """Abstract interface for text-to-speech providers."""

    @abstractmethod
    def generate_speech(
        self,
        text: str,
        voice: str = "default",
        output_path: Optional[str] = None
    ) -> str:
        """Generate speech audio from text.

        Args:
            text: Text to convert to speech
            voice: Voice identifier (provider-specific)
            output_path: Optional path for output file

        Returns:
            Path to generated audio file
        """
        pass

    @abstractmethod
    def get_available_voices(self) -> List[str]:
        """List available voice options.

        Returns:
            List of voice identifiers supported by this provider
        """
        pass
