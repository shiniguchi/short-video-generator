"""Fish Audio TTS provider implementation."""

import os
from uuid import uuid4
from typing import List, Optional

import httpx

from app.config import get_settings
from app.services.voiceover_generator.base import TTSProvider
from app.services.voiceover_generator.mock import MockTTSProvider


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio TTS provider with fallback to mock when not configured."""

    # Fish Audio API endpoint
    API_URL = "https://api.fish.audio/v1/tts"

    # Voice reference aliases (Fish Audio uses reference_id system)
    # These are convenience aliases - in production, users can provide actual reference IDs
    VOICE_ALIASES = {
        "default": None,  # Use Fish Audio's default voice
        "english_female": None,
        "english_male": None,
    }

    def __init__(self, api_key: str, output_dir: str):
        """Initialize Fish Audio TTS provider.

        Args:
            api_key: Fish Audio API key
            output_dir: Base directory for output files
        """
        self.api_key = api_key
        self.output_dir = output_dir
        self.audio_dir = os.path.join(output_dir, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)

        # Fallback to mock provider when not configured
        self._mock_provider = None

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
        voice: str = "default",
        output_path: Optional[str] = None
    ) -> str:
        """Generate speech using Fish Audio TTS API.

        Falls back to mock provider if USE_MOCK_DATA is True or API key is empty.

        Args:
            text: Text to convert to speech
            voice: Voice identifier (default, english_female, english_male)
            output_path: Optional path for output file

        Returns:
            Path to generated audio file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.api_key:
            return self.mock_provider.generate_speech(text, voice, output_path)

        # Map voice to reference_id
        voice_lower = voice.lower()
        reference_id = self.VOICE_ALIASES.get(voice_lower)

        # Generate output path if not provided
        if output_path is None:
            filename = f"{uuid4().hex[:8]}.mp3"
            output_path = os.path.join(self.audio_dir, filename)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Prepare request payload
        payload = {
            "text": text,
            "format": "mp3"
        }

        # Add reference_id if specified
        if reference_id is not None:
            payload["reference_id"] = reference_id

        # Call Fish Audio TTS API
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()

            # Write audio bytes to file
            with open(output_path, "wb") as f:
                f.write(response.content)

        return output_path

    def get_available_voices(self) -> List[str]:
        """List available Fish Audio voice aliases.

        Returns:
            List of voice identifiers
        """
        return list(self.VOICE_ALIASES.keys())
