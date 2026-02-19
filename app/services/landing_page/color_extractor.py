"""Color scheme extraction and management for landing pages."""

import colorgram
import json
from pathlib import Path
from typing import Optional, List
from app.schemas import ColorScheme


def extract_from_image(image_path: str, num_colors: int = 5) -> ColorScheme:
    """
    Extract color palette from product image using colorgram.

    Args:
        image_path: Path to the image file
        num_colors: Number of dominant colors to extract

    Returns:
        ColorScheme with extracted colors
    """
    colors = colorgram.extract(image_path, num_colors)

    # Sort by proportion (most dominant first)
    colors_sorted = sorted(colors, key=lambda c: c.proportion, reverse=True)

    # Convert RGB to hex
    def rgb_to_hex(rgb):
        return "#{:02x}{:02x}{:02x}".format(rgb.r, rgb.g, rgb.b)

    # Assign colors by dominance
    primary = rgb_to_hex(colors_sorted[0].rgb) if len(colors_sorted) > 0 else "#333333"
    secondary = rgb_to_hex(colors_sorted[1].rgb) if len(colors_sorted) > 1 else "#666666"
    accent = rgb_to_hex(colors_sorted[2].rgb) if len(colors_sorted) > 2 else "#0099FF"

    return ColorScheme(
        primary=primary,
        secondary=secondary,
        accent=accent,
        background="#FFFFFF",
        text="#1A1A1A",
        source="extracted"
    )


def get_research_colors(research_patterns: list) -> ColorScheme:
    """
    Analyze color schemes from researched landing pages and pick most common.

    Args:
        research_patterns: List of LPResearchPattern objects with color_scheme data

    Returns:
        ColorScheme based on research trends
    """
    # Collect all color schemes from patterns
    primary_colors = []
    secondary_colors = []
    accent_colors = []

    for pattern in research_patterns:
        if pattern.color_scheme:
            if "primary" in pattern.color_scheme:
                primary_colors.append(pattern.color_scheme["primary"])
            if "secondary" in pattern.color_scheme:
                secondary_colors.append(pattern.color_scheme["secondary"])
            if "accent" in pattern.color_scheme:
                accent_colors.append(pattern.color_scheme["accent"])

    # Pick most common or fallback to defaults
    def most_common(colors, default):
        if not colors:
            return default
        return max(set(colors), key=colors.count)

    primary = most_common(primary_colors, "#0066CC")
    secondary = most_common(secondary_colors, "#004C99")
    accent = most_common(accent_colors, "#00A3FF")

    return ColorScheme(
        primary=primary,
        secondary=secondary,
        accent=accent,
        background="#FFFFFF",
        text="#1A1A1A",
        source="research"
    )


def get_preset_palette(preset_name: str) -> ColorScheme:
    """
    Load a preset color palette from JSON.

    Args:
        preset_name: Name of the preset palette

    Returns:
        ColorScheme from preset

    Raises:
        ValueError: If preset name not found
    """
    palettes_path = Path(__file__).parent / "templates" / "presets" / "color_palettes.json"

    with open(palettes_path, "r") as f:
        data = json.load(f)

    # Find matching palette
    for palette in data["palettes"]:
        if palette["name"] == preset_name:
            return ColorScheme(
                primary=palette["primary"],
                secondary=palette["secondary"],
                accent=palette["accent"],
                background=palette["background"],
                text=palette["text"],
                source="preset"
            )

    raise ValueError(f"Preset palette '{preset_name}' not found")


def get_color_scheme(
    preference: str,
    image_path: Optional[str] = None,
    research_patterns: Optional[list] = None,
    preset_name: Optional[str] = None
) -> ColorScheme:
    """
    Main entry point for getting a color scheme based on preference.

    Args:
        preference: One of "extract", "research", "preset"
        image_path: Path to image (required for "extract")
        research_patterns: List of patterns (required for "research")
        preset_name: Name of preset (required for "preset")

    Returns:
        ColorScheme based on preference

    Raises:
        ValueError: If required parameters missing for preference
    """
    if preference == "extract":
        if not image_path:
            raise ValueError("image_path required for 'extract' preference")
        return extract_from_image(image_path)

    elif preference == "research":
        if not research_patterns:
            raise ValueError("research_patterns required for 'research' preference")
        return get_research_colors(research_patterns)

    elif preference == "preset":
        if not preset_name:
            raise ValueError("preset_name required for 'preset' preference")
        return get_preset_palette(preset_name)

    else:
        raise ValueError(f"Invalid preference: {preference}. Must be 'extract', 'research', or 'preset'")
