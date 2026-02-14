"""Video generator service orchestrating provider selection and clip generation."""

import os
from typing import List, Tuple
from uuid import uuid4

from app.config import get_settings
from app.services.video_generator.base import VideoProvider
from app.services.video_generator.mock import MockVideoProvider
from app.services.video_generator.svd import StableVideoDiffusionProvider
from app.services.video_generator.fal_kling import FalKlingProvider
from app.services.video_generator.fal_minimax import FalMinimaxProvider
from app.services.video_generator.chaining import chain_clips_to_duration


class VideoGeneratorService:
    """Orchestrates video generation using configured provider."""

    def __init__(self, provider: VideoProvider, output_dir: str):
        """Initialize video generator service.

        Args:
            provider: Video generation provider implementation
            output_dir: Base directory for output files
        """
        self.provider = provider
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_video(
        self,
        scenes: List[dict],
        target_duration: int,
        resolution: Tuple[int, int] = (720, 1280)
    ) -> str:
        """Generate a complete video from scene descriptions.

        Args:
            scenes: List of scene dicts with 'visual_prompt' and 'duration_seconds'
            target_duration: Total desired video duration in seconds
            resolution: (width, height) tuple

        Returns:
            Path to final generated video file

        Raises:
            ValueError: If scenes is empty or resolution not supported
        """
        if not scenes:
            raise ValueError("scenes cannot be empty")

        width, height = resolution

        if not self.provider.supports_resolution(width, height):
            raise ValueError(
                f"Provider does not support resolution {width}x{height}"
            )

        # Generate individual clips for each scene
        clip_paths = []
        for scene in scenes:
            prompt = scene.get("visual_prompt", "")
            duration = scene.get("duration_seconds", 3)

            clip_path = self.provider.generate_clip(
                prompt=prompt,
                duration_seconds=duration,
                width=width,
                height=height
            )
            clip_paths.append(clip_path)

        # Generate final output path
        final_output = os.path.join(
            self.output_dir,
            f"video_{uuid4().hex[:8]}.mp4"
        )

        # Chain clips to target duration
        result_path = chain_clips_to_duration(
            clip_paths=clip_paths,
            target_duration=target_duration,
            output_path=final_output
        )

        return result_path


def get_video_generator() -> VideoGeneratorService:
    """Factory function to create video generator with configured provider.

    Provider is selected based on VIDEO_PROVIDER_TYPE setting:
    - "mock": MockVideoProvider (default for local dev)
    - "svd": StableVideoDiffusionProvider (requires GPU)
    - "kling": FalKlingProvider (Kling 3.0 via fal.ai, requires FAL_KEY)
    - "minimax": FalMinimaxProvider (Minimax/Hailuo via fal.ai, requires FAL_KEY)

    Returns:
        Configured VideoGeneratorService instance
    """
    settings = get_settings()

    # Get provider type from settings (default to mock)
    provider_type = getattr(settings, "video_provider_type", "mock")
    output_dir = getattr(settings, "output_dir", "output")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Create provider based on type
    if provider_type == "kling":
        fal_key = getattr(settings, "fal_key", "")
        provider = FalKlingProvider(fal_key=fal_key, output_dir=output_dir)
    elif provider_type == "minimax":
        fal_key = getattr(settings, "fal_key", "")
        provider = FalMinimaxProvider(fal_key=fal_key, output_dir=output_dir)
    elif provider_type == "svd":
        provider = StableVideoDiffusionProvider()
    else:
        # Default to mock for local development
        provider = MockVideoProvider(output_dir=output_dir)

    return VideoGeneratorService(provider=provider, output_dir=output_dir)
