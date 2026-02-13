"""Video clip concatenation utilities."""

import os
from typing import List

from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips


def chain_clips_to_duration(
    clip_paths: List[str],
    target_duration: int,
    output_path: str
) -> str:
    """Concatenate clips and extend to target duration if needed.

    If the total duration of clips is less than target_duration,
    the clips will be repeated in sequence until reaching the target.

    Args:
        clip_paths: List of paths to video clips
        target_duration: Desired total duration in seconds
        output_path: Path for output video file

    Returns:
        Path to the output video file

    Raises:
        ValueError: If clip_paths is empty
    """
    if not clip_paths:
        raise ValueError("clip_paths cannot be empty")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Load all clips
    clips = [VideoFileClip(path) for path in clip_paths]

    try:
        # Calculate total duration
        total_duration = sum(clip.duration for clip in clips)

        # If we need to repeat clips to reach target duration
        if total_duration < target_duration:
            extended_clips = []
            current_duration = 0.0

            while current_duration < target_duration:
                for clip in clips:
                    extended_clips.append(clip)
                    current_duration += clip.duration
                    if current_duration >= target_duration:
                        break

            clips_to_concat = extended_clips
        else:
            clips_to_concat = clips

        # Concatenate clips
        final_clip = concatenate_videoclips(clips_to_concat, method="compose")

        # Trim to exact target duration if needed
        if final_clip.duration > target_duration:
            final_clip = final_clip.subclip(0, target_duration)

        # Write output file
        final_clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None,  # Suppress moviepy logging
            preset="medium"
        )

        # Clean up
        final_clip.close()

    finally:
        # Always close clips to free memory
        for clip in clips:
            clip.close()

    return output_path
