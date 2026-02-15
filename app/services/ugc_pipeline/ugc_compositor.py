"""UGC ad compositor for A-Roll + B-Roll composition.

Concatenates A-Roll clips into base layer and overlays B-Roll product shots
at specified timestamps to create final 9:16 UGC product ad.
"""

import logging
from typing import List, Dict, Any, Optional

from moviepy import VideoFileClip, CompositeVideoClip, concatenate_videoclips

logger = logging.getLogger(__name__)


def compose_ugc_ad(
    aroll_paths: List[str],
    broll_metadata: List[Dict[str, Any]],
    output_path: str
) -> str:
    """Compose final UGC ad from A-Roll base layer and B-Roll overlays.

    Concatenates A-Roll clips into continuous base video with built-in voice/audio.
    Overlays B-Roll product shots at specified timestamps as picture-in-picture (80% scale).

    Args:
        aroll_paths: List of paths to A-Roll video clips (in scene order)
        broll_metadata: List of B-Roll overlay dicts with keys:
            - path: str - Path to B-Roll video clip
            - overlay_start: float - Timestamp to start overlay (in seconds)
        output_path: Path where final MP4 will be written

    Returns:
        Path to final composed video (same as output_path)
    """
    logger.info(f"Starting UGC ad composition: {len(aroll_paths)} A-Roll clips, "
               f"{len(broll_metadata)} B-Roll overlays")

    # Edge case: Empty A-Roll list
    if not aroll_paths:
        raise ValueError("aroll_paths cannot be empty - at least one A-Roll clip required")

    # Load all A-Roll clips
    aroll_clips = [VideoFileClip(path) for path in aroll_paths]
    logger.info(f"Loaded {len(aroll_clips)} A-Roll clips")

    try:
        # Create base video from A-Roll clips
        if len(aroll_clips) == 1:
            # Edge case: Single A-Roll clip - no concatenation needed
            base_video = aroll_clips[0]
            logger.info(f"Single A-Roll clip used as base (duration: {base_video.duration:.2f}s)")
        else:
            # Concatenate multiple A-Roll clips
            base_video = concatenate_videoclips(aroll_clips, method="compose")
            logger.info(f"A-Roll clips concatenated into base video "
                       f"(duration: {base_video.duration:.2f}s)")

        # Calculate total A-Roll duration for overlay validation
        total_aroll_duration = base_video.duration

        # Edge case: No B-Roll overlays - just write A-Roll concatenation
        if not broll_metadata:
            logger.info("No B-Roll overlays - writing A-Roll base only")
            base_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                fps=30,
                preset="medium",
                bitrate="5M",
                audio_bitrate="128k"
            )
            return output_path

        # Load and position B-Roll overlays
        broll_overlays = []
        for idx, broll in enumerate(broll_metadata, 1):
            broll_path = broll["path"]
            overlay_start = broll["overlay_start"]

            # Load B-Roll clip
            clip = VideoFileClip(broll_path)

            # Validate overlay timing
            overlay_end = overlay_start + clip.duration
            if overlay_end > total_aroll_duration:
                logger.warning(f"B-Roll overlay {idx} extends beyond A-Roll duration "
                              f"({overlay_end:.2f}s > {total_aroll_duration:.2f}s) - "
                              f"overlay will be truncated by MoviePy")

            # Strip audio from B-Roll to prevent conflicts with A-Roll voice
            # Position at center and scale to 80% for picture-in-picture effect
            overlay = (clip
                      .without_audio()
                      .with_start(overlay_start)
                      .with_position(("center", "center"))
                      .resized(0.8))

            broll_overlays.append(overlay)
            logger.info(f"B-Roll overlay {idx} positioned at {overlay_start:.2f}s "
                       f"(duration: {clip.duration:.2f}s, 80% scale)")

        # Composite: base video + B-Roll overlays
        final_video = CompositeVideoClip(
            [base_video] + broll_overlays,
            size=(720, 1280)
        )
        logger.info(f"Composite created with {len(broll_overlays)} B-Roll overlays")

        # Write final video with H.264/AAC encoding
        logger.info(f"Writing final UGC ad to {output_path}")
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            bitrate="5M",
            audio_bitrate="128k"
        )

        # Get total duration before cleanup
        total_duration = final_video.duration
        logger.info(f"UGC ad composition complete: {total_duration:.2f}s total duration")

    finally:
        # Explicit resource cleanup
        logger.debug("Cleaning up video resources")

        # Close A-Roll clips
        for clip in aroll_clips:
            clip.close()

        # Close B-Roll overlays
        if broll_metadata:
            for overlay in broll_overlays:
                overlay.close()

        # Close composite (if created)
        if 'final_video' in locals():
            final_video.close()

        # Close base video (if different from single A-Roll clip)
        if len(aroll_clips) > 1 and 'base_video' in locals():
            base_video.close()

        logger.debug("Resource cleanup complete")

    return output_path
