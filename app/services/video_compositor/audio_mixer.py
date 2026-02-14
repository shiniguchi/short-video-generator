"""
Audio Mixing

Combines voiceover audio with optional background music at configurable volumes.
"""

from typing import Optional
from moviepy import AudioFileClip, CompositeAudioClip


def mix_audio(
    voiceover: AudioFileClip,
    background_music_path: Optional[str] = None,
    music_volume: float = 0.3,
    duration: Optional[float] = None,
) -> AudioFileClip:
    """
    Mix voiceover with optional background music.

    Args:
        voiceover: Primary voiceover audio clip (already loaded)
        background_music_path: Optional path to background music file
        music_volume: Volume multiplier for background music (0.0-1.0, default 0.3)
        duration: Target duration - music will be looped or cropped to match

    Returns:
        AudioFileClip - either the original voiceover or a CompositeAudioClip with music
    """
    # If no background music, return voiceover unchanged
    if background_music_path is None:
        return voiceover

    # Use voiceover duration if not specified
    if duration is None:
        duration = voiceover.duration

    # Load background music
    music = AudioFileClip(background_music_path)

    # Adjust music duration to match target
    if music.duration < duration:
        # Loop music if shorter than target
        music = music.audio_loop(duration=duration)
    elif music.duration > duration:
        # Crop music if longer than target
        music = music.subclipped(0, duration)

    # Reduce music volume (voiceover should be dominant)
    # Use with_multiply_volume (v2.x API) instead of deprecated volumex
    music = music.with_multiply_volume(music_volume)

    # Create composite with voiceover + background music
    # Voiceover is listed first so it's dominant
    composite = CompositeAudioClip([voiceover, music])

    return composite
