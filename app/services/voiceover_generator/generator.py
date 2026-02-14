"""Voiceover generator service orchestrating provider selection."""

import os
from typing import Optional

from moviepy.audio.io.AudioFileClip import AudioFileClip

from app.config import get_settings
from app.services.voiceover_generator.base import TTSProvider
from app.services.voiceover_generator.mock import MockTTSProvider
from app.services.voiceover_generator.openai_tts import OpenAITTSProvider


class VoiceoverGeneratorService:
    """Orchestrates voiceover generation using configured TTS provider."""

    def __init__(self, provider: TTSProvider, output_dir: str):
        """Initialize voiceover generator service.

        Args:
            provider: TTS provider implementation
            output_dir: Base directory for output files
        """
        self.provider = provider
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_voiceover(
        self,
        script: str,
        voice: str = "default",
        target_duration: Optional[float] = None
    ) -> str:
        """Generate voiceover audio from script text.

        Args:
            script: Text to convert to speech
            voice: Voice identifier (provider-specific)
            target_duration: Optional target duration in seconds
                           (will trim if too long, pad if too short)

        Returns:
            Path to generated audio file
        """
        # Generate speech audio
        audio_path = self.provider.generate_speech(
            text=script,
            voice=voice
        )

        # If target duration specified, adjust audio length
        if target_duration is not None:
            audio_path = self._adjust_duration(audio_path, target_duration)

        return audio_path

    def _adjust_duration(
        self,
        audio_path: str,
        target_duration: float
    ) -> str:
        """Adjust audio to match target duration.

        Args:
            audio_path: Path to audio file
            target_duration: Target duration in seconds

        Returns:
            Path to adjusted audio file (same as input if already correct)
        """
        clip = None
        try:
            clip = AudioFileClip(audio_path)
            current_duration = clip.duration

            # If duration matches (within 0.1s tolerance), return as-is
            if abs(current_duration - target_duration) < 0.1:
                return audio_path

            # If too long, trim
            if current_duration > target_duration:
                trimmed_clip = clip.subclip(0, target_duration)
                trimmed_path = audio_path.replace(".mp3", "_trimmed.mp3")
                trimmed_clip.write_audiofile(trimmed_path, logger=None)
                trimmed_clip.close()
                clip.close()
                return trimmed_path

            # If too short, return as-is (rare for TTS, padding is complex)
            # In production, we'd pad with silence or adjust speech rate
            return audio_path

        finally:
            if clip is not None:
                clip.close()


def get_voiceover_generator() -> VoiceoverGeneratorService:
    """Factory function to create voiceover generator with configured provider.

    Provider is selected based on TTS_PROVIDER_TYPE setting:
    - "mock": MockTTSProvider (default for local dev)
    - "openai": OpenAITTSProvider (requires API key)

    Returns:
        Configured VoiceoverGeneratorService instance
    """
    settings = get_settings()

    # Get provider type from settings (default to mock)
    provider_type = getattr(settings, "tts_provider_type", "mock")
    output_dir = getattr(settings, "output_dir", "output")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "audio"), exist_ok=True)

    # Create provider based on type
    if provider_type == "openai":
        api_key = getattr(settings, "openai_api_key", "")
        provider = OpenAITTSProvider(api_key=api_key, output_dir=output_dir)
    else:
        # Default to mock for local development
        provider = MockTTSProvider(output_dir=output_dir)

    return VoiceoverGeneratorService(provider=provider, output_dir=output_dir)
