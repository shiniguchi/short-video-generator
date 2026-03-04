"""UGC ad compositor for A-Roll + B-Roll composition.

Concatenates A-Roll clips into base layer, then intercuts full-screen B-Roll
at specified timestamps with crossfade transitions. A-Roll voiceover audio
plays continuously over the entire video.

Auto-detects and removes black bars (letterboxing) from clips, then scales
to fill the 9:16 frame.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any

import imageio_ffmpeg
import numpy as np
from moviepy import VideoFileClip, CompositeVideoClip, concatenate_videoclips, vfx

logger = logging.getLogger(__name__)

# Target frame size (9:16 vertical)
FRAME_W, FRAME_H = 720, 1280

# Crossfade duration for B-Roll transitions (seconds)
CROSSFADE_DURATION = 0.4

# Overall video fade in/out (seconds)
VIDEO_FADE_IN = 0.5
VIDEO_FADE_OUT = 0.8

# PiP (Picture-in-Picture) overlay settings
PIP_SIZE_RATIO = 0.30  # creator overlay = 30% of frame width
PIP_MARGIN = 20        # pixels from edge
PIP_CORNER_RADIUS = 999  # large value = circle mask

# Minimum black bar size to trigger removal (pixels)
MIN_BAR_THRESHOLD = 20


def normalize_video(path: str) -> str:
    """Re-encode video to h264/aac/30fps CFR mp4 if needed.

    iPhone .MOV files use VFR and QuickTime edit lists that cause moviepy
    to misread duration (losing the last 1-2s). This probes the file first
    and skips re-encoding if already mp4 + CFR 30fps.

    Returns path to normalized file (.normalized.mp4) or original if already OK.
    """
    p = Path(path)

    # Already normalized — skip
    if p.suffixes and ".normalized" in p.stem:
        logger.info(f"Already normalized, skipping: {p.name}")
        return path

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")

    # Probe codec, fps, and whether edit list / VFR is present
    try:
        probe_cmd = [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(p),
        ]
        probe_out = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(probe_out.stdout)
    except Exception as e:
        logger.warning(f"ffprobe failed for {p.name}, will re-encode: {e}")
        info = {}

    # Check if re-encoding is needed
    needs_reencode = True
    video_stream = None
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            video_stream = s
            break

    if video_stream and p.suffix.lower() == ".mp4":
        codec = video_stream.get("codec_name", "")
        # Check for CFR 30fps: r_frame_rate = "30/1" or "30000/1001"
        r_fps = video_stream.get("r_frame_rate", "")
        try:
            num, den = map(int, r_fps.split("/"))
            fps = num / den if den else 0
        except (ValueError, ZeroDivisionError):
            fps = 0
        if codec == "h264" and 29.9 <= fps <= 30.1:
            needs_reencode = False

    if not needs_reencode:
        logger.info(f"Already normalized (h264/30fps mp4), skipping: {p.name}")
        return path

    # Re-encode to CFR h264/aac mp4
    out_path = p.with_suffix("").with_suffix(".normalized.mp4")
    cmd = [
        ffmpeg, "-y", "-i", str(p),
        "-c:v", "libx264", "-preset", "slow", "-crf", "15",
        "-r", "30",  # force CFR 30fps
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    logger.info(f"Normalizing video: {p.name} -> {out_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"ffmpeg normalize failed: {result.stderr[-500:]}")
        raise RuntimeError(f"Failed to normalize video {p.name}")

    logger.info(f"Normalized video: {out_path.name}")
    return str(out_path)


def _fill_frame(clip: VideoFileClip) -> VideoFileClip:
    """Remove black bars and scale clip to fill the target 9:16 frame.

    Samples a frame, detects top/bottom black bars, crops them out,
    then scales to cover the full frame (center-cropping any overflow).
    """
    # Sample frame at 1s (or mid-point for very short clips)
    sample_t = min(1.0, clip.duration / 2)
    frame = clip.get_frame(sample_t)
    h, w, _ = frame.shape

    # Detect black bar rows (brightness < 10)
    row_brightness = frame.mean(axis=(1, 2))
    content_rows = np.where(row_brightness > 10)[0]

    if len(content_rows) == 0:
        return clip  # all black, nothing to do

    top_bar = content_rows[0]
    bottom_bar = h - content_rows[-1] - 1

    # Only crop if bars are significant
    if top_bar >= MIN_BAR_THRESHOLD or bottom_bar >= MIN_BAR_THRESHOLD:
        content_top = top_bar
        content_bottom = h - bottom_bar
        clip = clip.cropped(y1=content_top, y2=content_bottom)
        logger.info(f"Cropped black bars: top={top_bar}px, bottom={bottom_bar}px")

    # Scale to fill the target frame (cover, then center-crop)
    cw, ch = clip.size
    scale = max(FRAME_W / cw, FRAME_H / ch)

    if abs(scale - 1.0) > 0.01:  # only resize if needed
        clip = clip.resized(scale)
        nw, nh = clip.size
        # Center-crop to exact target size
        x_off = int((nw - FRAME_W) / 2)
        y_off = int((nh - FRAME_H) / 2)
        if x_off > 0 or y_off > 0:
            clip = clip.cropped(
                x1=x_off, y1=y_off,
                x2=x_off + FRAME_W, y2=y_off + FRAME_H
            )
            logger.info(f"Scaled {scale:.2f}x, cropped to {FRAME_W}x{FRAME_H}")

    return clip


def _make_pip_clip(aroll_clip, start: float, duration: float) -> CompositeVideoClip:
    """Create a circular PiP overlay from A-Roll clip for given time range.

    Crops center of A-Roll to square, scales to PIP_SIZE_RATIO of frame,
    applies circular mask, positions bottom-left with margin.
    """
    pip_w = int(FRAME_W * PIP_SIZE_RATIO)

    # Crop A-Roll to center square (face region)
    aw, ah = aroll_clip.size
    square = min(aw, ah)
    x_off = (aw - square) // 2
    y_off = int(ah * 0.05)  # slight top bias to capture face
    y_end = min(y_off + square, ah)
    cropped = aroll_clip.cropped(x1=x_off, y1=y_off, x2=x_off + square, y2=y_end)
    cropped = cropped.resized((pip_w, pip_w))

    # Circular mask
    center = pip_w // 2
    Y, X = np.ogrid[:pip_w, :pip_w]
    dist = np.sqrt((X - center) ** 2 + (Y - center) ** 2)
    circle_mask = (dist <= center).astype(np.float64)

    from moviepy import ImageClip
    mask_clip = ImageClip(circle_mask, is_mask=True).with_duration(duration)
    cropped = cropped.subclipped(start, min(start + duration, aroll_clip.duration))
    cropped = cropped.with_mask(mask_clip)

    # Position: bottom-left with margin
    pip_x = PIP_MARGIN
    pip_y = FRAME_H - pip_w - PIP_MARGIN
    cropped = cropped.with_position((pip_x, pip_y))

    return cropped


def compose_ugc_ad(
    aroll_paths: List[str],
    broll_metadata: List[Dict[str, Any]],
    output_path: str,
    pip_mode: bool = False,
) -> str:
    """Compose final UGC ad from A-Roll + full-screen B-Roll intercuts.

    A-Roll clips are concatenated as the base video with voiceover audio.
    B-Roll clips appear full-screen at their timestamps, replacing the A-Roll
    visually while the voiceover continues underneath. Crossfade transitions
    smooth the cuts. Overall video has fade-in and fade-out.
    """
    logger.info(f"Starting UGC ad composition: {len(aroll_paths)} A-Roll clips, "
               f"{len(broll_metadata)} B-Roll overlays")

    if not aroll_paths:
        raise ValueError("aroll_paths cannot be empty - at least one A-Roll clip required")

    aroll_clips = [VideoFileClip(path) for path in aroll_paths]
    logger.info(f"Loaded {len(aroll_clips)} A-Roll clips")

    try:
        # Build A-Roll base video (carries voiceover audio)
        if len(aroll_clips) == 1:
            base_video = aroll_clips[0]
        else:
            base_video = concatenate_videoclips(aroll_clips, method="compose")
        logger.info(f"A-Roll base: {base_video.duration:.2f}s")

        total_duration = base_video.duration

        # Preserve A-Roll voiceover audio
        base_audio = base_video.audio

        if not broll_metadata:
            # No B-Roll — write A-Roll with fade in/out
            final_video = base_video.with_effects([
                vfx.FadeIn(VIDEO_FADE_IN),
                vfx.FadeOut(VIDEO_FADE_OUT),
            ])
            final_video.write_videofile(
                output_path,
                codec="libx264", audio_codec="aac",
                fps=30, preset="slow",
                ffmpeg_params=["-crf", "15"],
                audio_bitrate="192k"
            )
            return output_path

        # Build full-screen B-Roll intercuts with crossfade
        broll_overlays = []
        for idx, broll in enumerate(broll_metadata, 1):
            clip = VideoFileClip(broll["path"])
            overlay_start = broll["overlay_start"]

            # Warn if B-Roll extends past A-Roll end
            if overlay_start + clip.duration > total_duration:
                logger.warning(f"B-Roll {idx} extends beyond A-Roll "
                              f"({overlay_start + clip.duration:.1f}s > {total_duration:.1f}s)")

            # Remove black bars and scale to fill frame
            clip = _fill_frame(clip)

            # Full-screen B-Roll: no audio, crossfade transitions
            overlay = (clip
                      .without_audio()
                      .with_start(overlay_start)
                      .with_position(("center", "center"))
                      .with_effects([
                          vfx.CrossFadeIn(CROSSFADE_DURATION),
                          vfx.CrossFadeOut(CROSSFADE_DURATION),
                      ]))

            broll_overlays.append(overlay)

            # PiP mode: add creator talking-head overlay on top of B-Roll
            if pip_mode:
                pip_clip = _make_pip_clip(base_video, overlay_start, clip.duration)
                pip_clip = pip_clip.with_start(overlay_start)
                broll_overlays.append(pip_clip)

            logger.info(f"B-Roll {idx}: {overlay_start:.1f}s-{overlay_start + clip.duration:.1f}s "
                       f"(full-screen{'+ PiP' if pip_mode else ''}, crossfade)")

        # Calculate total duration including B-Roll that extends past A-Roll
        max_broll_end = 0.0
        for broll in broll_metadata:
            clip = VideoFileClip(broll["path"])
            end = broll["overlay_start"] + clip.duration
            clip.close()
            if end > max_broll_end:
                max_broll_end = end
        final_duration = max(total_duration, max_broll_end)
        if final_duration > total_duration:
            logger.info(f"Extending timeline {total_duration:.1f}s -> {final_duration:.1f}s to fit B-Roll")

        # Composite: A-Roll base + full-screen B-Roll layers
        composite = CompositeVideoClip(
            [base_video] + broll_overlays,
            size=(FRAME_W, FRAME_H),
        ).with_duration(final_duration)

        # Override audio with A-Roll voiceover (continuous under B-Roll)
        composite = composite.with_audio(base_audio)

        # Overall fade in/out
        final_video = composite.with_effects([
            vfx.FadeIn(VIDEO_FADE_IN),
            vfx.FadeOut(VIDEO_FADE_OUT),
        ])

        # Write A-Roll only version (reuses already-built base_video)
        aroll_only_path = output_path.replace(".mp4", "_aroll.mp4")
        aroll_only = base_video.with_effects([vfx.FadeIn(VIDEO_FADE_IN), vfx.FadeOut(VIDEO_FADE_OUT)])
        logger.info(f"Writing A-Roll only: {aroll_only.duration:.2f}s -> {aroll_only_path}")
        aroll_only.write_videofile(
            aroll_only_path, codec="libx264", audio_codec="aac",
            fps=30, preset="slow", ffmpeg_params=["-crf", "15"], audio_bitrate="192k"
        )

        logger.info(f"Writing final UGC ad: {final_video.duration:.2f}s")
        final_video.write_videofile(
            output_path,
            codec="libx264", audio_codec="aac",
            fps=30, preset="slow",
            ffmpeg_params=["-crf", "15"],
            audio_bitrate="192k"
        )
        logger.info("UGC ad composition complete")

    finally:
        # Cleanup all loaded clips
        for clip in aroll_clips:
            clip.close()
        if broll_metadata:
            for overlay in broll_overlays:
                overlay.close()
        if 'final_video' in locals():
            final_video.close()
        if 'composite' in locals():
            composite.close()
        if len(aroll_clips) > 1 and 'base_video' in locals():
            base_video.close()

    return output_path
