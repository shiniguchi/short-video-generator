"""Google Veo 3.1 video provider via google-genai SDK."""

import os
import time
from uuid import uuid4
from typing import Optional

import httpx
from google import genai
from google.genai import types

from app.config import get_settings
from app.services.video_generator.base import VideoProvider
from app.services.video_generator.mock import MockVideoProvider


class GoogleVeoProvider(VideoProvider):
    """Veo 3.1 video generation via google-genai SDK.

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

        # Initialize client
        if google_api_key:
            self.client = genai.Client(api_key=google_api_key)
        else:
            self.client = None

        self.model_name = "veo-3.1-fast-generate-preview"

        # Fallback to mock provider when not configured
        self._mock_provider = None

    @property
    def mock_provider(self) -> MockVideoProvider:
        """Lazy initialization of mock provider for fallback."""
        if self._mock_provider is None:
            self._mock_provider = MockVideoProvider(output_dir=self.output_dir)
        return self._mock_provider

    def _save_video(self, video_obj, output_path: str):
        """Save generated video to file, handling both local bytes and remote URI.

        Args:
            video_obj: GeneratedVideo.video object from Veo response
            output_path: Path to save the MP4 file
        """
        if video_obj.video_bytes:
            # Video returned as bytes
            with open(output_path, "wb") as f:
                f.write(video_obj.video_bytes)
        elif video_obj.uri:
            # Video returned as download URI - download with API key auth
            download_url = video_obj.uri
            if "?" in download_url:
                download_url += f"&key={self.google_api_key}"
            else:
                download_url += f"?key={self.google_api_key}"

            with httpx.Client(timeout=120, follow_redirects=True) as http_client:
                response = http_client.get(download_url)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)
        else:
            raise ValueError("Veo response has neither video_bytes nor uri")

    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate a video clip using Veo 3.1.

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

        # CRITICAL: Veo only accepts even durations: 4, 6, or 8 seconds
        original_duration = duration_seconds
        valid_durations = [4, 6, 8]
        duration_seconds = min(valid_durations, key=lambda d: abs(d - int(original_duration)))
        if original_duration != duration_seconds:
            print(f"WARNING: Veo 3.1 requires 4/6/8s: adjusted {original_duration}s to {duration_seconds}s")

        # Determine aspect ratio
        aspect_ratio = "9:16" if height > width else "16:9"

        start_time = time.time()

        try:
            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                duration_seconds=duration_seconds,
            )

            operation = self.client.models.generate_videos(
                model=self.model_name,
                prompt=prompt,
                config=config,
            )

            # Poll until done
            print(f"Veo generation started, polling for completion...")
            while not operation.done:
                time.sleep(10)
                operation = self.client.operations.get(operation)

            # Save video
            video = operation.response.generated_videos[0]
            output_path = os.path.join(self.clips_dir, f"veo_{uuid4().hex[:8]}.mp4")
            self._save_video(video.video, output_path)

            elapsed = time.time() - start_time
            print(f"Veo generation completed in {elapsed:.1f}s "
                  f"({duration_seconds}s clip at {aspect_ratio})")

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

        # CRITICAL: Veo only accepts even durations: 4, 6, or 8 seconds
        original_duration = duration_seconds
        valid_durations = [4, 6, 8]
        duration_seconds = min(valid_durations, key=lambda d: abs(d - int(original_duration)))
        if original_duration != duration_seconds:
            print(f"WARNING: Veo 3.1 requires 4/6/8s: adjusted {original_duration}s to {duration_seconds}s")

        # Determine aspect ratio
        aspect_ratio = "9:16" if height > width else "16:9"

        start_time = time.time()

        try:
            # Load image as bytes with MIME type for Veo API
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            # Detect MIME type from extension
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
            mime_type = mime_map.get(ext, "image/png")

            image = types.Image(imageBytes=image_bytes, mimeType=mime_type)

            config = types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                duration_seconds=duration_seconds,
            )

            operation = self.client.models.generate_videos(
                model=self.model_name,
                prompt=prompt,
                image=image,
                config=config,
            )

            # Poll until done
            print(f"Veo image-to-video generation started, polling for completion...")
            while not operation.done:
                time.sleep(10)
                operation = self.client.operations.get(operation)

            # Save video
            video = operation.response.generated_videos[0]
            output_path = os.path.join(self.clips_dir, f"veo_{uuid4().hex[:8]}.mp4")
            self._save_video(video.video, output_path)

            elapsed = time.time() - start_time
            print(f"Veo image-to-video completed in {elapsed:.1f}s "
                  f"({duration_seconds}s clip at {aspect_ratio})")

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
        """Check if Veo provider supports the given resolution."""
        return (width, height) in self.SUPPORTED_RESOLUTIONS
