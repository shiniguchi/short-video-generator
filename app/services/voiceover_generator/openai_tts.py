"""OpenAI TTS provider implementation."""

import os
from uuid import uuid4
from typing import List, Optional

from openai import OpenAI

from app.config import get_settings
from app.services.voiceover_generator.base import TTSProvider
from app.services.voiceover_generator.mock import MockTTSProvider


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS provider with fallback to mock when not configured."""

    AVAILABLE_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def __init__(self, api_key: str, output_dir: str):
        """Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key
            output_dir: Base directory for output files
        """
        self.api_key = api_key
        self.output_dir = output_dir
        self.audio_dir = os.path.join(output_dir, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)

        # Lazy initialization of client
        self._client = None

        # Fallback to mock provider when not configured
        self._mock_provider = None

    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenAI client.

        Returns:
            OpenAI client instance
        """
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def mock_provider(self) -> MockTTSProvider:
        """Lazy initialization of mock provider for fallback.

        Returns:
            MockTTSProvider instance
        """
        if self._mock_provider is None:
            self._mock_provider = MockTTSProvider(output_dir=self.output_dir)
        return self._mock_provider

    def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        output_path: Optional[str] = None
    ) -> str:
        """Generate speech using OpenAI TTS API.

        Falls back to mock provider if USE_MOCK_DATA is True or API key is empty.

        Args:
            text: Text to convert to speech
            voice: Voice identifier (alloy, echo, fable, onyx, nova, shimmer)
            output_path: Optional path for output file

        Returns:
            Path to generated audio file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.api_key:
            return self.mock_provider.generate_speech(text, voice, output_path)

        # Validate voice
        if voice not in self.AVAILABLE_VOICES:
            voice = "alloy"  # Default voice

        # Generate output path if not provided
        if output_path is None:
            filename = f"{uuid4().hex[:8]}.mp3"
            output_path = os.path.join(self.audio_dir, filename)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Call OpenAI TTS API
        response = self.client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=text,
            response_format="mp3"
        )

        # Stream to file
        response.stream_to_file(output_path)

        return output_path

    def get_available_voices(self) -> List[str]:
        """List available OpenAI TTS voices.

        Returns:
            List of voice identifiers
        """
        return self.AVAILABLE_VOICES.copy()
