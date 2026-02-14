"""HeyGen avatar provider implementation."""

import os
import time
from uuid import uuid4
from typing import List, Optional

import httpx

from app.config import get_settings
from app.services.avatar_generator.base import AvatarProvider
from app.services.avatar_generator.mock import MockAvatarProvider


class HeyGenAvatarProvider(AvatarProvider):
    """HeyGen avatar provider with fallback to mock when not configured."""

    # Common HeyGen avatar IDs (examples - users should use their own from HeyGen dashboard)
    COMMON_AVATARS = [
        "default",
        "josh_lite",
        "anna_costume1",
        "wayne_20220808"
    ]

    def __init__(self, api_key: str, output_dir: str, default_avatar_id: str = ""):
        """Initialize HeyGen avatar provider.

        Args:
            api_key: HeyGen API key
            output_dir: Base directory for output files
            default_avatar_id: Default avatar ID from HeyGen dashboard
        """
        self.api_key = api_key
        self.output_dir = output_dir
        self.default_avatar_id = default_avatar_id or "default"
        self.avatar_dir = os.path.join(output_dir, "avatars")
        os.makedirs(self.avatar_dir, exist_ok=True)

        # Fallback to mock provider when not configured
        self._mock_provider = None

    @property
    def mock_provider(self) -> MockAvatarProvider:
        """Lazy initialization of mock provider for fallback.

        Returns:
            MockAvatarProvider instance
        """
        if self._mock_provider is None:
            self._mock_provider = MockAvatarProvider(output_dir=self.output_dir)
        return self._mock_provider

    def generate_avatar_video(
        self,
        script_text: str,
        avatar_id: str = "default",
        voice_id: str = "default"
    ) -> str:
        """Generate avatar video using HeyGen API.

        Falls back to mock provider if USE_MOCK_DATA is True or API key is empty.

        Args:
            script_text: Script text for the avatar to speak
            avatar_id: Avatar identifier from HeyGen dashboard
            voice_id: Voice identifier from HeyGen dashboard

        Returns:
            Path to generated avatar video file
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.api_key:
            return self.mock_provider.generate_avatar_video(script_text, avatar_id, voice_id)

        # Use default avatar if not specified
        if avatar_id == "default":
            avatar_id = self.default_avatar_id

        # Create video via HeyGen API v2
        video_id = self._create_video(script_text, avatar_id, voice_id)

        # Poll for completion
        video_url = self._wait_for_completion(video_id, timeout_seconds=600)

        # Download video
        output_path = self._download_video(video_url)

        return output_path

    def _create_video(self, script_text: str, avatar_id: str, voice_id: str) -> str:
        """Create avatar video via HeyGen API.

        Args:
            script_text: Script text for the avatar to speak
            avatar_id: Avatar identifier
            voice_id: Voice identifier

        Returns:
            Video ID for polling
        """
        url = "https://api.heygen.com/v2/video/generate"
        headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": script_text,
                    "voice_id": voice_id
                }
            }],
            "dimension": {
                "width": 720,
                "height": 1280
            }
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

        video_id = result.get("data", {}).get("video_id")
        if not video_id:
            raise ValueError(f"HeyGen API did not return video_id: {result}")

        return video_id

    def _wait_for_completion(self, video_id: str, timeout_seconds: int = 600) -> str:
        """Poll HeyGen API until video generation is complete.

        Args:
            video_id: Video ID to poll
            timeout_seconds: Maximum time to wait (default 10 minutes)

        Returns:
            URL to completed video

        Raises:
            TimeoutError: If video not completed within timeout
            ValueError: If video generation failed
        """
        url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
        headers = {
            "X-Api-Key": self.api_key
        }

        start_time = time.time()
        poll_interval = 10  # Poll every 10 seconds

        with httpx.Client(timeout=30.0) as client:
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    raise TimeoutError(f"HeyGen video generation timed out after {timeout_seconds}s")

                response = client.get(url, headers=headers)
                response.raise_for_status()
                result = response.json()

                status = result.get("data", {}).get("status")

                if status == "completed":
                    video_url = result.get("data", {}).get("video_url")
                    if not video_url:
                        raise ValueError(f"HeyGen API completed but no video_url: {result}")
                    return video_url

                elif status == "failed":
                    error = result.get("data", {}).get("error", "Unknown error")
                    raise ValueError(f"HeyGen video generation failed: {error}")

                # Status is pending or processing, wait and retry
                time.sleep(poll_interval)

    def _download_video(self, video_url: str) -> str:
        """Download video from HeyGen URL to local file.

        Args:
            video_url: URL to download video from

        Returns:
            Path to downloaded video file
        """
        filename = f"heygen_{uuid4().hex[:8]}.mp4"
        output_path = os.path.join(self.avatar_dir, filename)

        with httpx.Client(timeout=60.0) as client:
            response = client.get(video_url)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        return output_path

    def get_available_avatars(self) -> List[str]:
        """List available HeyGen avatars.

        Returns common avatar IDs. For production, users should use their own
        avatar IDs from HeyGen dashboard.

        Returns:
            List of avatar identifiers
        """
        return self.COMMON_AVATARS.copy()
