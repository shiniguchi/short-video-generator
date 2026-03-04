"""WCAG contrast ratio utilities for landing page color validation."""

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# WCAG AA minimum contrast ratio for normal text
WCAG_AA_RATIO = 4.5


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Parse hex color (#RGB, #RRGGBB, or RRGGBB) to (r, g, b) tuple."""
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6 or not re.match(r"^[0-9a-fA-F]{6}$", h):
        raise ValueError(f"Invalid hex color: {hex_color}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (r, g, b) to #RRGGBB hex string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.1 relative luminance formula."""
    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two RGB colors. Returns value between 1 and 21."""
    l1 = relative_luminance(*color1)
    l2 = relative_luminance(*color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def darken_to_contrast(hex_color: str, target_ratio: float = WCAG_AA_RATIO) -> str:
    """Darken a hex color until it meets target contrast ratio against white.

    Uses binary search to find the lightest shade that still passes.
    Returns original color if it already passes.
    """
    WHITE = (255, 255, 255)
    rgb = hex_to_rgb(hex_color)

    # Already meets contrast
    if contrast_ratio(rgb, WHITE) >= target_ratio:
        return hex_color

    r, g, b = rgb
    # Binary search: factor 0.0 = black, 1.0 = original color
    lo, hi = 0.0, 1.0
    for _ in range(20):
        mid = (lo + hi) / 2
        test = (int(r * mid), int(g * mid), int(b * mid))
        if contrast_ratio(test, WHITE) >= target_ratio:
            lo = mid  # can go lighter
        else:
            hi = mid  # need darker
    factor = lo
    result = (int(r * factor), int(g * factor), int(b * factor))
    return rgb_to_hex(*result)


def ensure_contrast(hex_color: str, label: str = "color") -> str:
    """Validate color has WCAG AA contrast against white. Darken if needed.

    Logs a warning when auto-correction happens.
    """
    try:
        rgb = hex_to_rgb(hex_color)
    except ValueError:
        logger.warning(f"Invalid {label}: {hex_color}, using fallback #1a1a2e")
        return "#1a1a2e"

    ratio = contrast_ratio(rgb, (255, 255, 255))
    if ratio >= WCAG_AA_RATIO:
        return hex_color

    corrected = darken_to_contrast(hex_color, WCAG_AA_RATIO)
    corrected_rgb = hex_to_rgb(corrected)
    new_ratio = contrast_ratio(corrected_rgb, (255, 255, 255))
    logger.info(
        f"Contrast fix ({label}): {hex_color} ratio {ratio:.1f}:1 → "
        f"{corrected} ratio {new_ratio:.1f}:1"
    )
    return corrected
