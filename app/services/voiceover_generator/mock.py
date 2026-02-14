"""Mock TTS provider for local development."""

import os
import numpy as np
from uuid import uuid4
from typing import List, Optional

from moviepy.audio.AudioClip import AudioClip

from app.services.voiceover_generator.base import TTSProvider


class MockTTSProvider(TTSProvider):
    """Generates silent audio files for testing."""

    def __init__(self, output_dir: str):
        """Initialize mock TTS provider.

        Args:
            output_dir: Base directory for output files
        """
        self.output_dir = output_dir
        self.audio_dir = os.path.join(output_dir, "audio")
        os.makedirs(self.audio_dir, exist_ok=True)

    def generate_speech(
        self,
        text: str,
        voice: str = "default",
        output_path: Optional[str] = None
    ) -> str:
        """Generate silent audio file with duration based on text length.

        Duration is calculated at ~15 characters per second.

        Args:
            text: Text to convert (determines duration)
            voice: Voice identifier (ignored for mock)
            output_path: Optional path for output file

        Returns:
            Path to generated audio file
        """
        # Calculate duration based on text length (~15 chars per second)
        duration = max(1.0, len(text) / 15.0)

        # Generate output path if not provided
        if output_path is None:
            filename = f"mock_{uuid4().hex[:8]}.mp3"
            output_path = os.path.join(self.audio_dir, filename)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Create silent audio clip
        def make_frame(t):
            # Return stereo silence
            return np.array([[0.0, 0.0]])

        audio = AudioClip(make_frame, duration=duration, fps=44100)

        # Write audio file
        audio.write_audiofile(output_path, logger=None)
        audio.close()

        return output_path

    def get_available_voices(self) -> List[str]:
        """List available voices for mock provider.

        Returns:
            List containing only "mock" voice
        """
        return ["mock"]
