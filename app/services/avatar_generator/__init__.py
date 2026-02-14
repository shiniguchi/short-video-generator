"""Avatar generator subsystem - talking-head video generation."""

from app.services.avatar_generator.base import AvatarProvider
from app.services.avatar_generator.mock import MockAvatarProvider
from app.services.avatar_generator.heygen import HeyGenAvatarProvider
from app.services.avatar_generator.generator import AvatarGeneratorService, get_avatar_generator

__all__ = [
    "AvatarProvider",
    "MockAvatarProvider",
    "HeyGenAvatarProvider",
    "AvatarGeneratorService",
    "get_avatar_generator"
]
