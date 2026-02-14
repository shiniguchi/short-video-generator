"""Kling 3.0 video provider via fal.ai API."""

import os
import time
from uuid import uuid4
from typing import Optional

import httpx
import fal_client

from app.config import get_settings
from app.services.video_generator.base import VideoProvider
from app.services.video_generator.mock import MockVideoProvider


class FalKlingProvider(VideoProvider):
    """Kling 3.0 video generation via fal.ai unified API gateway.

    Kling 3.0 is a premium video generation model from Kuaishou.
    Pricing: ~$0.029/second, supports 4K resolution, high quality output.
    """

    SUPPORTED_RESOLUTIONS = [
        (720, 1280),   # 9:16 standard HD
        (1080, 1920),  # 9:16 full HD
    ]

    def __init__(self, fal_key: str, output_dir: str):
        """Initialize Kling provider.

        Args:
            fal_key: fal.ai API key for authentication
            output_dir: Base directory for output files
        """
        self.fal_key = fal_key
        self.output_dir = output_dir
        self.clips_dir = os.path.join(output_dir, "clips")
        os.makedirs(self.clips_dir, exist_ok=True)

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
        """Generate a video clip using Kling 3.0 via fal.ai.

        Falls back to mock provider if USE_MOCK_DATA is True or fal_key is empty.

        Args:
            prompt: Visual description of the scene
            duration_seconds: Length of clip in seconds (5 or 10)
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated MP4 file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.fal_key:
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

        # Set FAL_KEY environment variable for fal_client
        os.environ["FAL_KEY"] = self.fal_key

        # Map duration to Kling supported values (5 or 10 seconds)
        kling_duration = "10" if duration_seconds >= 7 else "5"

        # Submit job to fal.ai Kling endpoint
        start_time = time.time()

        try:
            # Use subscribe for blocking wait until completion
            result = fal_client.subscribe(
                "fal-ai/kling-video/v2/master",
                arguments={
                    "prompt": prompt,
                    "duration": kling_duration,
                    "aspect_ratio": "9:16"
                }
            )

            # Extract video URL from result
            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise ValueError("No video URL in fal.ai response")

            # Download video to local file
            filename = f"kling_{uuid4().hex[:8]}.mp4"
            output_path = os.path.join(self.clips_dir, filename)

            with httpx.Client(timeout=60.0) as client:
                response = client.get(video_url)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)

            elapsed = time.time() - start_time
            cost_estimate = float(kling_duration) * 0.029

            print(f"Kling generation completed in {elapsed:.1f}s "
                  f"(~${cost_estimate:.3f} for {kling_duration}s clip)")

            return output_path

        except Exception as e:
            print(f"Kling generation failed: {e}, falling back to mock")
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if Kling provider supports the given resolution.

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            True if resolution is in supported list
        """
        return (width, height) in self.SUPPORTED_RESOLUTIONS
