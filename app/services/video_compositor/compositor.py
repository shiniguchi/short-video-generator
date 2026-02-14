"""
Video Compositor Orchestrator

Main class that coordinates video composition, combining video clips, audio, text overlays,
and background music into publish-ready MP4 files.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict
from uuid import uuid4

from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip

from app.schemas import TextOverlaySchema
from .text_overlay import render_text_overlays
from .audio_mixer import mix_audio
from .thumbnail import generate_thumbnail

logger = logging.getLogger(__name__)


class VideoCompositor:
    """
    Orchestrates video composition process.

    Combines base video, voiceover audio, text overlays, and optional background music
    into a publish-ready H.264/AAC MP4 file with thumbnail.
    """

    def __init__(self, output_dir: str = "output/final"):
        """
        Initialize VideoCompositor.

        Args:
            output_dir: Directory for output videos (default: output/final)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"VideoCompositor initialized with output_dir={self.output_dir}")

    def compose(
        self,
        video_path: str,
        audio_path: str,
        text_overlays: List[TextOverlaySchema],
        background_music_path: Optional[str] = None,
        music_volume: float = 0.3,
        output_filename: Optional[str] = None,
        thumbnail_timestamp: float = 2.0,
    ) -> Dict[str, any]:
        """
        Compose final video from components.

        Args:
            video_path: Path to base video file
            audio_path: Path to voiceover audio file
            text_overlays: List of TextOverlaySchema objects for text rendering
            background_music_path: Optional path to background music file
            music_volume: Volume multiplier for background music (0.0-1.0, default 0.3)
            output_filename: Optional output filename (default: auto-generated)
            thumbnail_timestamp: Time in seconds to extract thumbnail frame (default 2.0)

        Returns:
            Dict with keys: video_path (str), thumbnail_path (str), duration (float)
        """
        logger.info(f"Starting composition: video={video_path}, audio={audio_path}")

        # Use context managers for automatic resource cleanup
        with VideoFileClip(video_path) as base_video:
            with AudioFileClip(audio_path) as voiceover:
                # Step 1: Mix audio (voiceover + optional background music)
                final_audio = mix_audio(
                    voiceover=voiceover,
                    background_music_path=background_music_path,
                    music_volume=music_volume,
                    duration=base_video.duration,
                )
                logger.info(f"Audio mixed (background_music={'yes' if background_music_path else 'no'})")

                # Step 2: Render text overlays
                text_clips = render_text_overlays(
                    overlays=text_overlays,
                    video_size=(720, 1280),
                    duration=base_video.duration,
                )
                logger.info(f"Text overlays rendered: {len(text_clips)} overlays")

                # Step 3: Compose video with text overlays
                # Base video is first, then text clips are layered on top
                final_video = CompositeVideoClip(
                    [base_video] + text_clips,
                    size=(720, 1280),
                )

                # Step 4: Set audio on composite video (use v2.x API: with_audio)
                final_video = final_video.with_audio(final_audio)

                # Step 5: Verify audio was attached (catch CompositeVideoClip audio drop bug)
                assert final_video.audio is not None, "Audio was not attached to composite video"

                # Step 6: Generate output filename
                if output_filename is None:
                    output_filename = f"video_{uuid4().hex[:8]}.mp4"
                output_path = self.output_dir / output_filename

                # Step 7: Write final video with H.264/AAC encoding
                logger.info(f"Writing final video to {output_path}")
                final_video.write_videofile(
                    str(output_path),
                    codec="libx264",
                    audio_codec="aac",
                    fps=30,
                    preset="medium",
                    bitrate="5M",
                    audio_bitrate="128k",
                )

                # Step 8: Generate thumbnail
                thumbnail_dir = self.output_dir.parent / "thumbnails"
                thumbnail_path = generate_thumbnail(
                    video_path=str(output_path),
                    timestamp=thumbnail_timestamp,
                    output_dir=str(thumbnail_dir),
                )
                logger.info(f"Thumbnail generated: {thumbnail_path}")

                # Step 9: Get duration before cleanup
                duration = base_video.duration

                # Step 10: Explicit cleanup
                # Close composite audio
                if final_audio is not None:
                    final_audio.close()

                # Close all text clips
                for clip in text_clips:
                    clip.close()

                # Close final video
                final_video.close()

                logger.info(f"Composition complete: duration={duration:.2f}s")

                # Step 11: Return result
                return {
                    "video_path": str(output_path),
                    "thumbnail_path": thumbnail_path,
                    "duration": duration,
                }
