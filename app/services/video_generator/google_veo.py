"""Google Veo 3.1 video provider via Google Generative AI API."""

import os
import time
from uuid import uuid4
from typing import Optional

import google.generativeai as genai
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.services.video_generator.base import VideoProvider
from app.services.video_generator.mock import MockVideoProvider


class GoogleVeoProvider(VideoProvider):
    """Veo 3.1 video generation via Google Generative AI.

    Veo 3.1 generates video with built-in voice/audio support.
    Critical limitation: Maximum 8 seconds per clip.
    Supports both text-to-video and image-to-video modes.
    """

    SUPPORTED_RESOLUTIONS = [
        (720, 1280),   # 9:16 HD
        (1080, 1920),  # 9:16 Full HD
        (1280, 720),   # 16:9 HD
        (1920, 1080),  # 16:9 Full HD
    ]

    def __init__(self, google_api_key: str, output_dir: str):
        """Initialize Veo provider.

        Args:
            google_api_key: Google API key for authentication
            output_dir: Base directory for output files
        """
        self.google_api_key = google_api_key
        self.output_dir = output_dir
        self.clips_dir = os.path.join(output_dir, "clips")
        os.makedirs(self.clips_dir, exist_ok=True)

        # Configure Google Generative AI if API key is available
        if google_api_key:
            genai.configure(api_key=google_api_key)

        # Fallback to mock provider when not configured
        self._mock_provider = None

    @property
    def mock_provider(self) -> MockVideoProvider:
        """Lazy initialization of mock provider for fallback.

        Returns:
            MockVideoProvider instance
        """
        if self._mock_provider is None:
            self._mock_provider = MockVideoProvider(output_dir=self.output_dir)
        return self._mock_provider

    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate a video clip using Veo 3.1.

        Falls back to mock provider if USE_MOCK_DATA is True or google_api_key is empty.

        Args:
            prompt: Visual description of the scene
            duration_seconds: Length of clip in seconds (max 8)
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated MP4 file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.google_api_key:
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

        # CRITICAL: Clamp duration to 8 seconds max
        original_duration = duration_seconds
        duration_seconds = min(duration_seconds, 8)
        if original_duration > 8:
            print(f"WARNING: Veo 3.1 max 8s/clip: clamped {original_duration}s to {duration_seconds}s")

        # Determine aspect ratio and resolution
        aspect_ratio = "9:16" if height > width else "16:9"
        resolution = "1080p" if width >= 1080 else "720p"

        start_time = time.time()

        try:
            # Create model
            model = genai.GenerativeModel("veo-3.1-fast-generate-preview")

            # Call API
            operation = model.generate_videos(
                prompt=prompt,
                config={
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "duration_seconds": str(duration_seconds)
                }
            )

            # Poll until done
            print(f"Veo generation started, polling for completion...")
            while not operation.done:
                time.sleep(10)
                operation = operation.refresh()

            # Save video
            video = operation.response.generated_videos[0]
            output_path = os.path.join(self.clips_dir, f"veo_{uuid4().hex[:8]}.mp4")
            video.video.save(output_path)

            elapsed = time.time() - start_time
            print(f"Veo generation completed in {elapsed:.1f}s "
                  f"({duration_seconds}s clip at {resolution} {aspect_ratio})")

            return output_path

        except Exception as e:
            print(f"Veo generation failed: {e}, falling back to mock")
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

    def generate_clip_from_image(
        self,
        prompt: str,
        image_path: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate a video clip from an image using Veo 3.1 (image-to-video mode).

        This is a Veo-specific extension method, not part of VideoProvider ABC.
        Useful for Phase 13 UGC Product Ad Pipeline where Imagen images are animated.

        Falls back to mock provider if USE_MOCK_DATA is True or google_api_key is empty.

        Args:
            prompt: Visual description of the scene/motion
            image_path: Path to input image file
            duration_seconds: Length of clip in seconds (max 8)
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated MP4 file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.google_api_key:
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

        # CRITICAL: Clamp duration to 8 seconds max
        original_duration = duration_seconds
        duration_seconds = min(duration_seconds, 8)
        if original_duration > 8:
            print(f"WARNING: Veo 3.1 max 8s/clip: clamped {original_duration}s to {duration_seconds}s")

        # Determine aspect ratio and resolution
        aspect_ratio = "9:16" if height > width else "16:9"
        resolution = "1080p" if width >= 1080 else "720p"

        start_time = time.time()

        try:
            # Load image
            image = Image.open(image_path)

            # Create model
            model = genai.GenerativeModel("veo-3.1-fast-generate-preview")

            # Call API with image
            operation = model.generate_videos(
                prompt=prompt,
                image=image,
                config={
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "duration_seconds": str(duration_seconds)
                }
            )

            # Poll until done
            print(f"Veo image-to-video generation started, polling for completion...")
            while not operation.done:
                time.sleep(10)
                operation = operation.refresh()

            # Save video
            video = operation.response.generated_videos[0]
            output_path = os.path.join(self.clips_dir, f"veo_{uuid4().hex[:8]}.mp4")
            video.video.save(output_path)

            elapsed = time.time() - start_time
            print(f"Veo image-to-video completed in {elapsed:.1f}s "
                  f"({duration_seconds}s clip at {resolution} {aspect_ratio})")

            return output_path

        except Exception as e:
            print(f"Veo image-to-video generation failed: {e}, falling back to mock")
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if Veo provider supports the given resolution.

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            True if resolution is in supported list
        """
        return (width, height) in self.SUPPORTED_RESOLUTIONS
