"""Asset generation for UGC product ad pipeline.

Generates hero images, A-Roll scenes, and B-Roll product shots using Imagen + Veo.
"""

import logging
import os
import re
from typing import List, Optional, Dict, Any

from app.config import get_settings
from app.services.video_generator.google_veo import GoogleVeoProvider
from app.services.video_generator.mock import MockVideoProvider

logger = logging.getLogger(__name__)

# Veo safety filter: blocked terms → safe replacements
_VEO_SAFETY_REPLACEMENTS = [
    # Clothing
    (r"\bbathrobe\b", "cozy knit sweater"),
    (r"\brobe\b", "casual sweater"),
    (r"\btowel\b", "casual top"),
    (r"\bswimwear\b", "casual clothing"),
    (r"\bswimsuit\b", "casual clothing"),
    (r"\bbikini\b", "casual clothing"),
    (r"\bunderwear\b", "casual clothing"),
    (r"\blingerie\b", "casual clothing"),
    (r"\bundress(?:ed|ing)?\b", "casually dressed"),
    # Settings
    (r"\bbathtub\b", "comfortable chair"),
    (r"\bbath\s*room\b", "living room"),
    (r"\bshower\b", "kitchen"),
    (r"\bjacuzzi\b", "comfortable seating area"),
    (r"\bhot\s*tub\b", "comfortable seating area"),
    # Poses / framing
    (r"\bsuggestive\b", "confident"),
    (r"\bseductive\b", "friendly"),
    (r"\binviting\b", "welcoming"),
    (r"\bintimate\b", "warm"),
    (r"\bsensual\b", "natural"),
    # Violence / danger
    (r"\bweapon\b", "object"),
    (r"\bgun\b", "device"),
    (r"\bknife\b", "utensil"),
]


def _sanitize_veo_prompt(prompt: str, preserve_terms: Optional[List[str]] = None) -> str:
    """Replace Veo-blocked terms with safe alternatives.

    Veo checks both text prompt AND source image. This catches
    common terms that the LLM guardrails sometimes miss.

    preserve_terms: Strings to protect from sanitization (e.g. product name).
        These are temporarily replaced with placeholders, then restored.
    """
    # Temporarily replace preserved terms with placeholders
    placeholders = {}
    for i, term in enumerate(preserve_terms or []):
        if term:
            ph = f"__PRESERVE_{i}__"
            placeholders[ph] = term
            prompt = prompt.replace(term, ph)

    original = prompt
    for pattern, replacement in _VEO_SAFETY_REPLACEMENTS:
        prompt = re.sub(pattern, replacement, prompt, flags=re.IGNORECASE)
    if prompt != original:
        logger.warning(f"Sanitized Veo prompt: blocked terms replaced")

    # Restore preserved terms
    for ph, term in placeholders.items():
        prompt = prompt.replace(ph, term)

    return prompt


def _get_veo_or_mock(use_mock: bool = False) -> GoogleVeoProvider:
    """Get Veo provider or mock fallback based on use_mock flag.

    Args:
        use_mock: Use mock provider instead of real Veo API

    Returns:
        GoogleVeoProvider or MockVideoProvider instance
    """
    settings = get_settings()
    google_api_key = getattr(settings, "google_api_key", "")
    output_dir = getattr(settings, "output_dir", "output")

    # Use mock when explicitly requested or no API key available
    if use_mock or not google_api_key:
        logger.info("Using MockVideoProvider for Veo operations (use_mock=True or no API key)")
        return MockVideoProvider(output_dir=output_dir)

    # Return actual Veo provider (which has its own mock fallback)
    return GoogleVeoProvider(google_api_key=google_api_key, output_dir=output_dir)


def generate_hero_image(
    product_image_path: str,
    ugc_style: str,
    emotional_tone: str,
    visual_keywords: List[str],
    product_name: str = "",
    use_mock: bool = False,
    sketch_path: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
) -> str:
    """Generate hero image for the product.

    Generation strategy (in priority order):
    1. Reference images provided → subject-referenced generation (keeps product appearance)
    2. Sketch provided → sketch-guided generation (scribble control)
    3. Neither → text-to-image generation

    Args:
        product_image_path: Path to product photo reference
        ugc_style: Style description (e.g., "lifestyle", "minimalist")
        emotional_tone: Emotional tone (e.g., "aspirational", "authentic")
        visual_keywords: Style guidance keywords
        product_name: Product name for subject description
        use_mock: Use mock image provider instead of real API
        sketch_path: Optional hand-drawn sketch to guide generation
        reference_images: Optional list of product photo paths for subject reference

    Returns:
        Path to generated hero image (720x1280 vertical)
    """
    settings = get_settings()
    output_dir = getattr(settings, "output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    # Filter reference_images to only existing files
    valid_refs = [p for p in (reference_images or []) if os.path.exists(p)]
    # Append product_image_path as fallback (user-uploaded refs take priority)
    if product_image_path and os.path.exists(product_image_path) and product_image_path not in valid_refs:
        valid_refs.append(product_image_path)

    visual_style = ", ".join(visual_keywords) if visual_keywords else "natural, authentic"

    has_refs = bool(valid_refs)
    has_sketch = sketch_path and os.path.exists(sketch_path)
    subject_desc = product_name or "the product"

    if use_mock:
        from app.services.image_provider.mock import MockImageProvider
        prompt = (
            f"Professional product photography, {ugc_style} style. "
            f"Mood: {emotional_tone}. Style: {visual_style}. Vertical 9:16 format."
        )
        image_provider = MockImageProvider(output_dir=output_dir)
        image_paths = image_provider.generate_image(
            prompt=prompt, width=720, height=1280, reference_images=valid_refs or None
        )
    else:
        from app.services.image_provider.google_imagen import GoogleImagenProvider
        google_api_key = getattr(settings, "google_api_key", "")
        image_provider = GoogleImagenProvider(api_key=google_api_key, output_dir=output_dir)

        if has_refs and has_sketch:
            # Both: subject refs + sketch composition control
            prompt = (
                f"Professional product hero photography of [1] in the composition shown by [2], "
                f"{ugc_style} style. Soft natural window light, shallow depth of field. "
                f"Mood: {emotional_tone}. Style: {visual_style}. "
                f"Clean composition, product as hero, vertical 9:16 format."
            )
            logger.info(f"Using subject refs ({len(valid_refs)}) + sketch control")
            image_paths = image_provider.generate_with_refs_and_sketch(
                prompt=prompt, reference_images=valid_refs,
                sketch_path=sketch_path, subject_description=subject_desc,
                width=720, height=1280
            )
        elif has_refs:
            # Subject-referenced only: preserves product appearance
            prompt = (
                f"Professional product hero photography of [1], {ugc_style} style. "
                f"Product displayed in a beautiful lifestyle setting, "
                f"soft natural window light, shallow depth of field. "
                f"Mood: {emotional_tone}. Style: {visual_style}. "
                f"Clean composition, product as hero, vertical 9:16 format."
            )
            logger.info(f"Using subject-referenced generation with {len(valid_refs)} reference(s)")
            image_paths = image_provider.generate_with_references(
                prompt=prompt, reference_images=valid_refs,
                subject_description=subject_desc, width=720, height=1280
            )
        elif has_sketch:
            # Sketch-guided only: composition from hand-drawn sketch
            prompt = (
                f"Professional product photography, {ugc_style} style. "
                f"Product displayed in a beautiful lifestyle setting, "
                f"soft natural window light, shallow depth of field. "
                f"Mood: {emotional_tone}. Style: {visual_style}. "
                f"Clean composition, product as hero, vertical 9:16 format."
            )
            logger.info(f"Using sketch-guided generation: {sketch_path}")
            image_paths = image_provider.generate_from_sketch(
                prompt=prompt, sketch_path=sketch_path, width=720, height=1280
            )
        else:
            # Text-to-image only
            prompt = (
                f"Professional product photography, {ugc_style} style. "
                f"Product displayed in a beautiful lifestyle setting, "
                f"soft natural window light, shallow depth of field. "
                f"Mood: {emotional_tone}. Style: {visual_style}. "
                f"Clean composition, product as hero, vertical 9:16 format."
            )
            logger.info("Using text-to-image generation (no references)")
            image_paths = image_provider.generate_image(
                prompt=prompt, width=720, height=1280, num_images=1
            )

    hero_image_path = image_paths[0]
    logger.info(f"Hero image generated: {hero_image_path}")

    return hero_image_path


def _get_image_provider(use_mock: bool = False):
    """Get Imagen provider or mock fallback."""
    settings = get_settings()
    output_dir = getattr(settings, "output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    if use_mock:
        from app.services.image_provider.mock import MockImageProvider
        return MockImageProvider(output_dir=output_dir)

    from app.services.image_provider.google_imagen import GoogleImagenProvider
    google_api_key = getattr(settings, "google_api_key", "")
    return GoogleImagenProvider(api_key=google_api_key, output_dir=output_dir)


def generate_aroll_images(
    aroll_scenes: List[Dict[str, Any]],
    hero_image_path: str,
    use_mock: bool = False,
    creator_persona: str = "",
    product_image_paths: Optional[List[str]] = None,
    product_name: str = "",
) -> List[str]:
    """Generate a single A-Roll creator image used for all video clips.

    Uses Imagen 4 text-to-image (no subject refs) for best quality.
    Subject refs force Imagen 3 edit model which produces worse results.
    The product is described textually in the prompt instead.

    Returns:
        List with 1 image path (single creator image for all scenes)
    """
    logger.info("Generating 1 A-Roll creator image (text-to-image, Imagen 4)")

    image_provider = _get_image_provider(use_mock=use_mock)
    product_desc = product_name or "the product"

    # Build a rich prompt — no image refs, pure text-to-image for Imagen 4 quality
    persona_prefix = f"{creator_persona}. " if creator_persona else ""
    safe_visual = _sanitize_veo_prompt(
        f"{persona_prefix}Looking directly at camera with a natural, confident smile. "
        f"Holding {product_desc} casually in one hand at chest height.",
        preserve_terms=[product_desc],
    )
    prompt = (
        f"{safe_visual} "
        f"Photorealistic portrait, vertical 9:16, shot on iPhone, "
        f"soft golden hour window light, shallow depth of field, "
        f"cozy indoor setting, warm tones. "
        f"The person is the main subject, product visible but secondary."
    )

    logger.info(f"A-Roll prompt (text-to-image): {prompt}")

    # No reference_images → uses text-to-image path → Imagen 4
    paths = image_provider.generate_image(
        prompt=prompt, width=720, height=1280, num_images=1,
    )

    logger.info(f"A-Roll creator image generated: {paths[0]}")
    return [paths[0]]


def generate_aroll_assets(
    aroll_scenes: List[Dict[str, Any]],
    aroll_image_paths: List[str],
    use_mock: bool = False,
    creator_persona: str = "",
    existing_paths: Optional[List] = None,
) -> List[str]:
    """Generate A-Roll video clips from per-scene images using Veo image-to-video.

    Args:
        aroll_scenes: Scene dicts with visual_prompt, duration_seconds, etc.
        aroll_image_paths: Per-scene image paths (from generate_aroll_images)
        use_mock: Use mock provider instead of real Veo API
        existing_paths: Pre-filled paths list. Non-None slots are kept as-is (skipped).

    Returns:
        List of paths to A-Roll video clips in scene order
    """
    logger.info(f"Generating {len(aroll_scenes)} A-Roll clips from per-scene images")

    veo = _get_veo_or_mock(use_mock=use_mock)

    clip_paths = list(existing_paths) if existing_paths else [None] * len(aroll_scenes)
    for idx, scene in enumerate(aroll_scenes, 1):
        # Skip slots that already have a path or are marked as skipped
        slot = clip_paths[idx - 1] if idx - 1 < len(clip_paths) else None
        if slot == "__skipped__":
            clip_paths[idx - 1] = None  # Replace sentinel with None
            logger.info(f"A-Roll scene {idx}: skipped by user")
            continue
        if slot is not None:
            logger.info(f"A-Roll scene {idx}: slot pre-filled, skipping generation")
            continue
        visual_prompt = scene.get("visual_prompt", "")
        camera_angle = scene.get("camera_angle", "medium close-up")
        script_text = scene.get("script_text", "")
        duration_seconds = 8  # Always max — Veo snaps to [4,6,8], shorter clips truncate voiceover

        # Prepend creator persona so Veo keeps the same person across clips
        persona_prefix = f"{creator_persona}. " if creator_persona else ""
        # Sanitize visual prompt only — dialogue must stay as-is for accurate speech
        visual_part = f"{persona_prefix}{visual_prompt} Camera: {camera_angle}."
        visual_part = _sanitize_veo_prompt(visual_part)
        dialogue = f' The person says: "{script_text}"' if script_text else ""
        full_prompt = f"{visual_part}{dialogue}"

        # All clips use the single creator image
        image_path = aroll_image_paths[0]

        logger.info(f"Generating A-Roll scene {idx}/{len(aroll_scenes)} "
                   f"(duration: {duration_seconds}s)")

        # Image-to-video with retry on celebrity false-positive
        try:
            try:
                clip_path = veo.generate_clip_from_image(
                    prompt=full_prompt,
                    image_path=image_path,
                    duration_seconds=duration_seconds,
                    width=720,
                    height=1280
                )
            except RuntimeError as e:
                if "celebrity" in str(e).lower():
                    logger.warning(f"A-Roll scene {idx}: celebrity filter hit, retrying with modified prompt")
                    retry_prompt = (
                        f"Original fictional character (not a real person). {full_prompt}"
                    )
                    clip_path = veo.generate_clip_from_image(
                        prompt=retry_prompt,
                        image_path=image_path,
                        duration_seconds=duration_seconds,
                        width=720,
                        height=1280
                    )
                else:
                    raise
        except Exception as e:
            raise RuntimeError(f"[aroll_scene:{idx - 1}] {e}") from e

        clip_paths[idx - 1] = clip_path
        logger.info(f"A-Roll scene {idx} generated: {clip_path}")

    generated = sum(1 for p in clip_paths if p is not None)
    logger.info(f"A-Roll complete: {generated}/{len(clip_paths)} clips (rest skipped)")
    return clip_paths


def generate_broll_images(
    broll_shots: List[Dict[str, Any]],
    product_images: List[str],
    use_mock: bool = False,
) -> List[str]:
    """Generate per-shot B-Roll product images via Imagen.

    Each shot uses a product photo as reference to generate a styled product image.

    Returns:
        List of image paths, one per shot
    """
    logger.info(f"Generating {len(broll_shots)} B-Roll images "
                f"(using {len(product_images)} reference images)")

    image_provider = _get_image_provider(use_mock=use_mock)

    image_paths = []
    for idx, shot in enumerate(broll_shots, 1):
        image_prompt = shot.get("image_prompt", "")
        ref_index = shot.get("reference_image_index", 0)
        ref_index = max(0, min(ref_index, len(product_images) - 1))
        reference_image = product_images[ref_index]

        logger.info(f"Generating B-Roll image {idx}/{len(broll_shots)} (ref image {ref_index})")

        paths = image_provider.generate_image(
            prompt=image_prompt, width=720, height=1280, num_images=1,
            reference_images=[reference_image],
        )
        image_paths.append(paths[0])
        logger.info(f"B-Roll image {idx} generated: {paths[0]}")

    return image_paths


def generate_broll_assets(
    broll_shots: List[Dict[str, Any]],
    broll_image_paths: List[str],
    use_mock: bool = False,
    existing_paths: Optional[List] = None,
) -> List[str]:
    """Generate B-Roll video clips from pre-generated images via Veo.

    Args:
        broll_shots: Shot dicts with animation_prompt, duration_seconds, etc.
        broll_image_paths: Per-shot image paths (from generate_broll_images)
        use_mock: Use mock providers instead of real APIs
        existing_paths: Pre-filled paths list. Non-None slots are kept as-is (skipped).

    Returns:
        List of paths to B-Roll video clips in shot order
    """
    logger.info(f"Generating {len(broll_shots)} B-Roll clips from pre-generated images")

    veo = _get_veo_or_mock(use_mock=use_mock)

    clip_paths = list(existing_paths) if existing_paths else [None] * len(broll_shots)
    for idx, shot in enumerate(broll_shots, 1):
        # Skip slots that already have a path or are marked as skipped
        slot = clip_paths[idx - 1] if idx - 1 < len(clip_paths) else None
        if slot == "__skipped__":
            clip_paths[idx - 1] = None  # Replace sentinel with None
            logger.info(f"B-Roll shot {idx}: skipped by user")
            continue
        if slot is not None:
            logger.info(f"B-Roll shot {idx}: slot pre-filled, skipping generation")
            continue
        animation_prompt = _sanitize_veo_prompt(shot.get("animation_prompt", ""))
        duration_seconds = shot.get("duration_seconds", 5)

        # Use per-shot image
        image_idx = idx - 1
        image_path = broll_image_paths[image_idx] if image_idx < len(broll_image_paths) else broll_image_paths[0]

        logger.info(f"Generating B-Roll shot {idx}/{len(broll_shots)} via Veo")

        try:
            try:
                clip_path = veo.generate_clip_from_image(
                    prompt=animation_prompt,
                    image_path=image_path,
                    duration_seconds=duration_seconds,
                    width=720,
                    height=1280
                )
            except RuntimeError as e:
                if "safety filter" in str(e).lower():
                    logger.warning(f"B-Roll shot {idx}: image blocked by safety filter, "
                                  f"retrying as text-to-video")
                    clip_path = veo.generate_clip(
                        prompt=animation_prompt,
                        duration_seconds=duration_seconds,
                        width=720,
                        height=1280
                    )
                else:
                    raise
        except Exception as e:
            raise RuntimeError(f"[broll_shot:{image_idx}] {e}") from e

        clip_paths[idx - 1] = clip_path
        logger.info(f"B-Roll shot {idx} animated clip generated: {clip_path}")

    generated = sum(1 for p in clip_paths if p is not None)
    logger.info(f"B-Roll complete: {generated}/{len(clip_paths)} clips (rest skipped)")
    return clip_paths
