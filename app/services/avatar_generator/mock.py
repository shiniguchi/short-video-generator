"""Mock avatar provider for local development."""

import os
from uuid import uuid4
from typing import List, Optional

from moviepy import ColorClip

from app.services.avatar_generator.base import AvatarProvider


class MockAvatarProvider(AvatarProvider):
    """Mock avatar provider that generates placeholder videos."""

    def __init__(self, output_dir: str):
        """Initialize mock avatar provider.

        Args:
            output_dir: Base directory for output files
        """
        self.output_dir = output_dir
        self.avatar_dir = os.path.join(output_dir, "avatars")
        os.makedirs(self.avatar_dir, exist_ok=True)

    def generate_avatar_video(
        self,
        script_text: str,
        avatar_id: str = "default",
        voice_id: str = "default"
    ) -> str:
        """Generate a placeholder avatar video with solid color.

        Creates a simple colored placeholder MP4 with duration based on script length.
        Uses approximately 15 characters per second (same as MockTTSProvider).

        Args:
            script_text: Script text for the avatar to speak
            avatar_id: Avatar identifier (ignored for mock)
            voice_id: Voice identifier (ignored for mock)

        Returns:
            Path to generated placeholder MP4 file
        """
        # Calculate duration based on script text length (~15 chars/sec)
        chars_per_second = 15
        duration = max(1, len(script_text) / chars_per_second)

        # Generate unique filename
        filename = f"mock_avatar_{uuid4().hex[:8]}.mp4"
        output_path = os.path.join(self.avatar_dir, filename)

        # Create a solid color clip (purple for avatar videos)
        # 720x1280 is 9:16 vertical video format
        clip = ColorClip(
            size=(720, 1280),
            color=(128, 0, 128),  # Purple
            duration=duration
        )

        # Write to file
        clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None  # Suppress moviepy progress output
        )

        clip.close()

        return output_path

    def get_available_avatars(self) -> List[str]:
        """List available mock avatars.

        Returns:
            List containing single mock avatar identifier
        """
        return ["mock_avatar"]
