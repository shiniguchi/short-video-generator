"""Video generation service with swappable providers."""

from app.services.video_generator.generator import (
    VideoGeneratorService,
    get_video_generator
)
from app.services.video_generator.base import VideoProvider
from app.services.video_generator.mock import MockVideoProvider
from app.services.video_generator.fal_kling import FalKlingProvider
from app.services.video_generator.fal_minimax import FalMinimaxProvider

__all__ = [
    "VideoGeneratorService",
    "get_video_generator",
    "VideoProvider",
    "MockVideoProvider",
    "FalKlingProvider",
    "FalMinimaxProvider"
]
