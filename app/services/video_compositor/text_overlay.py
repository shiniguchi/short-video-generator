"""
Text Overlay Rendering

Converts TextOverlaySchema objects into positioned, styled MoviePy TextClip objects.
"""

import os
from typing import List, Tuple, Optional
from moviepy import TextClip
from app.schemas import TextOverlaySchema


# Position mapping for 9:16 vertical video (720x1280)
POSITION_MAP = {
    "top": ("center", 100),
    "center": ("center", "center"),
    "bottom": ("center", 1100),
}

# Font style mapping to Montserrat variants (full paths to bundled fonts)
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "fonts")
FONT_MAP = {
    "bold": os.path.abspath(os.path.join(_FONTS_DIR, "Montserrat-Bold.ttf")),
    "normal": os.path.abspath(os.path.join(_FONTS_DIR, "Montserrat-Regular.ttf")),
    "highlight": os.path.abspath(os.path.join(_FONTS_DIR, "Montserrat-ExtraBold.ttf")),
}


def render_text_overlays(
    overlays: List[TextOverlaySchema],
    video_size: Tuple[int, int] = (720, 1280),
    duration: Optional[float] = None,
) -> List[TextClip]:
    """
    Render text overlays as positioned TextClip objects with timing and animations.

    Args:
        overlays: List of TextOverlaySchema objects with text, timing, position, style
        video_size: Video dimensions (width, height) - default 720x1280 (9:16)
        duration: Optional max duration to clip overlays to

    Returns:
        List of TextClip objects with timing, positioning, and fade-in animations applied
    """
    text_clips = []

    for overlay in overlays:
        # Map position to coordinates
        pos = POSITION_MAP.get(overlay.position, POSITION_MAP["center"])

        # Map style to font
        font = FONT_MAP.get(overlay.style, FONT_MAP["bold"])

        # Calculate duration
        overlay_duration = overlay.timestamp_end - overlay.timestamp_start
        if duration is not None:
            overlay_duration = min(overlay_duration, duration - overlay.timestamp_start)

        # Create TextClip with styling
        # Use method="caption" with size for word wrapping
        # Add margin=(10, 10) to prevent stroke clipping (MoviePy bug workaround)
        text_clip = TextClip(
            text=overlay.text,
            font=font,
            font_size=48,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(video_size[0] - 80, None),  # 40px margin each side
            margin=(10, 10),  # Prevent stroke clipping
        )

        # Apply timing using MoviePy v2.x API (with_* methods)
        text_clip = text_clip.with_start(overlay.timestamp_start)
        text_clip = text_clip.with_duration(overlay_duration)

        # Apply position
        text_clip = text_clip.with_position(pos)

        # Apply fade-in animation (0.3 second fade) — MoviePy v2.x API
        from moviepy import vfx
        text_clip = text_clip.with_effects([vfx.CrossFadeIn(0.3)])

        text_clips.append(text_clip)

    return text_clips
