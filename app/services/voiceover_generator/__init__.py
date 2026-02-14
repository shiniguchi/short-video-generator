"""Voiceover generation service with swappable TTS providers."""

from app.services.voiceover_generator.generator import (
    VoiceoverGeneratorService,
    get_voiceover_generator
)
from app.services.voiceover_generator.base import TTSProvider
from app.services.voiceover_generator.mock import MockTTSProvider
from app.services.voiceover_generator.openai_tts import OpenAITTSProvider
from app.services.voiceover_generator.elevenlabs_tts import ElevenLabsTTSProvider
from app.services.voiceover_generator.fish_audio_tts import FishAudioTTSProvider

__all__ = [
    "VoiceoverGeneratorService",
    "get_voiceover_generator",
    "TTSProvider",
    "MockTTSProvider",
    "OpenAITTSProvider",
    "ElevenLabsTTSProvider",
    "FishAudioTTSProvider",
]
