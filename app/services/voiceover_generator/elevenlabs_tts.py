"""ElevenLabs TTS provider implementation."""

import os
from uuid import uuid4
from typing import List, Optional

from elevenlabs.client import ElevenLabs

from app.config import get_settings
from app.services.voiceover_generator.base import TTSProvider
from app.services.voiceover_generator.mock import MockTTSProvider


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS provider with fallback to mock when not configured."""

    # Voice name to ID mappings for common marketing voices
    VOICE_MAPPINGS = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",
        "drew": "29vD33N1CtxCmqQRPOHJ",
        "clyde": "2EiwWnXFnvU5JabPnv8n",
        "paul": "5Q0t7uMcjvnagumLfvZi",
        "domi": "AZnzlk1XvdvUeBnXmlld",
        "bella": "EXAVITQu4vr4xnSDxMaL",
        "antoni": "ErXwobaYiN019PkySvjV",
        "elli": "MF3mGyEYCl7XYWbV9V6O",
        "josh": "TxGEqnHWrfWFTfGW9XjX",
        "arnold": "VR6AewLTigWG4xSOukaG",
        "adam": "pNInz6obpgDQGcFmaJgB",
        "sam": "yoZ06aMxZJJ28mfd3POQ",
    }

    def __init__(self, api_key: str, output_dir: str):
        """Initialize ElevenLabs TTS provider.

        Args:
            api_key: ElevenLabs API key
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
    def client(self) -> ElevenLabs:
        """Lazy initialization of ElevenLabs client.

        Returns:
            ElevenLabs client instance
        """
        if self._client is None:
            self._client = ElevenLabs(api_key=self.api_key)
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
        voice: str = "rachel",
        output_path: Optional[str] = None
    ) -> str:
        """Generate speech using ElevenLabs TTS API.

        Falls back to mock provider if USE_MOCK_DATA is True or API key is empty.

        Args:
            text: Text to convert to speech
            voice: Voice identifier (rachel, drew, clyde, etc.)
            output_path: Optional path for output file

        Returns:
            Path to generated audio file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.api_key:
            return self.mock_provider.generate_speech(text, voice, output_path)

        # Map voice name to ID
        voice_lower = voice.lower()
        voice_id = self.VOICE_MAPPINGS.get(voice_lower, self.VOICE_MAPPINGS["rachel"])

        # Generate output path if not provided
        if output_path is None:
            filename = f"{uuid4().hex[:8]}.mp3"
            output_path = os.path.join(self.audio_dir, filename)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Call ElevenLabs TTS API
        audio_generator = self.client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128"
        )

        # Stream audio bytes to file
        with open(output_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)

        return output_path

    def get_available_voices(self) -> List[str]:
        """List available ElevenLabs voices.

        Returns:
            List of voice identifiers
        """
        return list(self.VOICE_MAPPINGS.keys())
