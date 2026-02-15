"""Mock video provider for local development."""

import os
import hashlib
from uuid import uuid4
from typing import Tuple

from moviepy.video.VideoClip import ColorClip

from app.services.video_generator.base import VideoProvider


class MockVideoProvider(VideoProvider):
    """Generates solid-color placeholder clips for testing."""

    # Color palette for variety (RGB tuples)
    COLORS = [
        (52, 152, 219),   # Blue
        (46, 204, 113),   # Green
        (155, 89, 182),   # Purple
        (241, 196, 15),   # Yellow
        (230, 126, 34),   # Orange
        (231, 76, 60),    # Red
        (26, 188, 156),   # Turquoise
        (149, 165, 166),  # Gray
    ]

    def __init__(self, output_dir: str):
        """Initialize mock provider.

        Args:
            output_dir: Base directory for output files
        """
        self.output_dir = output_dir
        self.clips_dir = os.path.join(output_dir, "clips")
        os.makedirs(self.clips_dir, exist_ok=True)

    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate a solid-color mock clip.

        Args:
            prompt: Visual description (used to pick color via hash)
            duration_seconds: Length of clip in seconds
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated MP4 file
        """
        # Pick color based on prompt hash for consistency
        color = self._pick_color(prompt)

        # Generate unique filename
        filename = f"mock_{uuid4().hex[:8]}.mp4"
        output_path = os.path.join(self.clips_dir, filename)

        # Create solid color clip
        clip = ColorClip(
            size=(width, height),
            color=color,
            duration=duration_seconds
        )

        # Write to file
        clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio=False,
            logger=None,  # Suppress moviepy logging
            preset="ultrafast"  # Fast encoding for mock data
        )
        clip.close()

        return output_path

    def generate_clip_from_image(
        self,
        prompt: str,
        image_path: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate a mock clip from image (delegates to generate_clip).

        In mock mode, the image_path is ignored and a solid-color clip
        is generated instead. This enables the UGC pipeline to run
        end-to-end without real Veo API access.

        Args:
            prompt: Visual description
            image_path: Source image (ignored in mock)
            duration_seconds: Length of clip in seconds
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated MP4 file
        """
        return self.generate_clip(
            prompt=prompt,
            duration_seconds=duration_seconds,
            width=width,
            height=height
        )

    def supports_resolution(self, width: int, height: int) -> bool:
        """Mock provider supports any resolution.

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Always True for mock provider
        """
        return True

    def _pick_color(self, prompt: str) -> Tuple[int, int, int]:
        """Pick a color from palette based on prompt hash.

        Args:
            prompt: Text to hash

        Returns:
            RGB color tuple
        """
        hash_value = int(hashlib.md5(prompt.encode()).hexdigest(), 16)
        color_index = hash_value % len(self.COLORS)
        return self.COLORS[color_index]
