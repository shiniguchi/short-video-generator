"""Voiceover generation service with swappable TTS providers."""

from app.services.voiceover_generator.generator import (
    VoiceoverGeneratorService,
    get_voiceover_generator
)
from app.services.voiceover_generator.base import TTSProvider

__all__ = ["VoiceoverGeneratorService", "get_voiceover_generator", "TTSProvider"]
