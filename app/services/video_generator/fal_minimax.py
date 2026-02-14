"""Minimax/Hailuo video provider via fal.ai API."""

import os
import time
from uuid import uuid4
from typing import Optional

import httpx
import fal_client

from app.config import get_settings
from app.services.video_generator.base import VideoProvider
from app.services.video_generator.mock import MockVideoProvider


class FalMinimaxProvider(VideoProvider):
    """Minimax/Hailuo video generation via fal.ai unified API gateway.

    Minimax video-01-live is a fast, budget-friendly video generation model.
    Pricing: ~$0.02-0.05/video, optimized for speed and cost efficiency.
    """

    def __init__(self, fal_key: str, output_dir: str):
        """Initialize Minimax provider.

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
        """Generate a video clip using Minimax via fal.ai.

        Falls back to mock provider if USE_MOCK_DATA is True or fal_key is empty.

        Args:
            prompt: Visual description of the scene
            duration_seconds: Length of clip in seconds (ignored - Minimax uses fixed duration)
            width: Video width in pixels (Minimax auto-determines from aspect ratio)
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

        # Submit job to fal.ai Minimax endpoint
        start_time = time.time()

        try:
            # Use subscribe for blocking wait until completion
            result = fal_client.subscribe(
                "fal-ai/minimax-video/video-01-live",
                arguments={
                    "prompt": prompt,
                    "prompt_optimizer": True  # Enable prompt optimization for better results
                }
            )

            # Extract video URL from result
            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise ValueError("No video URL in fal.ai response")

            # Download video to local file
            filename = f"minimax_{uuid4().hex[:8]}.mp4"
            output_path = os.path.join(self.clips_dir, filename)

            with httpx.Client(timeout=60.0) as client:
                response = client.get(video_url)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)

            elapsed = time.time() - start_time
            cost_estimate = 0.035  # Average cost per video

            print(f"Minimax generation completed in {elapsed:.1f}s "
                  f"(~${cost_estimate:.3f} per clip)")

            return output_path

        except Exception as e:
            print(f"Minimax generation failed: {e}, falling back to mock")
            return self.mock_provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration_seconds,
                width=width,
                height=height
            )

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if Minimax provider supports the given resolution.

        Minimax supports resolutions up to 1080p.

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            True if resolution is within supported range
        """
        # Support up to 1080p (full HD)
        max_dimension = max(width, height)
        return max_dimension <= 1920
