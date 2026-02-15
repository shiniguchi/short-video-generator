"""Asset generation for UGC product ad pipeline.

Generates hero images, A-Roll scenes, and B-Roll product shots using Imagen + Veo.
"""

import logging
import os
from typing import List, Optional, Dict, Any

from app.config import get_settings
from app.services.image_provider import get_image_provider
from app.services.video_generator.google_veo import GoogleVeoProvider
from app.services.video_generator.mock import MockVideoProvider

logger = logging.getLogger(__name__)


def _get_veo_or_mock() -> GoogleVeoProvider:
    """Get Veo provider or mock fallback based on settings.

    Returns:
        GoogleVeoProvider instance (which may internally fallback to mock)
    """
    settings = get_settings()
    google_api_key = getattr(settings, "google_api_key", "")
    output_dir = getattr(settings, "output_dir", "output")

    # Check if we should use mock
    if settings.use_mock_data or not google_api_key:
        logger.info("Using MockVideoProvider for Veo operations (USE_MOCK_DATA=True or no API key)")
        return MockVideoProvider(output_dir=output_dir)

    # Return actual Veo provider (which has its own mock fallback)
    return GoogleVeoProvider(google_api_key=google_api_key, output_dir=output_dir)


def generate_hero_image(
    product_image_path: str,
    ugc_style: str,
    emotional_tone: str,
    visual_keywords: List[str]
) -> str:
    """Generate hero image combining UGC character and product.

    Creates a photo-realistic image of a UGC creator holding/showcasing the product,
    using the product photo as a reference for consistent product appearance.

    Args:
        product_image_path: Path to product photo reference
        ugc_style: UGC character description (e.g., "young woman in casual outfit")
        emotional_tone: Emotional tone for the scene (e.g., "excited", "enthusiastic")
        visual_keywords: Style guidance keywords (e.g., ["natural lighting", "authentic"])

    Returns:
        Path to generated hero image (720x1280 vertical)
    """
    settings = get_settings()

    # Build prompt combining UGC character + product integration
    visual_style = ", ".join(visual_keywords) if visual_keywords else "natural, authentic"
    prompt = (
        f"Selfie-style photo of a {ugc_style} UGC creator, medium close-up, "
        f"phone camera angle slightly below eye level. "
        f"Creator holds the product at chest height facing camera with one hand. "
        f"Expression: {emotional_tone}, natural and unposed. "
        f"Well-lit indoor setting, soft natural window light. "
        f"Raw smartphone aesthetic, not studio-lit. "
        f"Style: {visual_style}. "
        f"Product clearly visible and matching reference image. "
        f"Vertical 9:16 composition."
    )

    logger.info(f"Generating hero image with UGC style: {ugc_style}, tone: {emotional_tone}")
    logger.debug(f"Hero image prompt: {prompt}")

    # Get image provider
    image_provider = get_image_provider()

    # Generate hero image (9:16 vertical format)
    image_paths = image_provider.generate_image(
        prompt=prompt,
        width=720,
        height=1280,
        num_images=1,
        reference_images=[product_image_path]
    )

    hero_image_path = image_paths[0]
    logger.info(f"Hero image generated: {hero_image_path}")

    return hero_image_path


def generate_aroll_assets(
    aroll_scenes: List[Dict[str, Any]],
    hero_image_path: str
) -> List[str]:
    """Generate A-Roll video clips from hero image using Veo image-to-video.

    Each scene is animated from the hero image with voice direction and visual prompts.

    Args:
        aroll_scenes: List of A-Roll scene dicts with keys:
            - visual_prompt: Scene description
            - duration_seconds: Clip duration
            - voice_direction: Voice/audio direction
            - script_text: Script text (for reference)
        hero_image_path: Path to hero image for image-to-video generation

    Returns:
        List of paths to A-Roll video clips in scene order
    """
    logger.info(f"Generating {len(aroll_scenes)} A-Roll clips from hero image")

    # Get Veo provider (or mock fallback)
    veo = _get_veo_or_mock()

    clip_paths = []
    for idx, scene in enumerate(aroll_scenes, 1):
        visual_prompt = scene.get("visual_prompt", "")
        voice_direction = scene.get("voice_direction", "")
        camera_angle = scene.get("camera_angle", "medium close-up")
        script_text = scene.get("script_text", "")
        duration_seconds = scene.get("duration_seconds", 6)

        # Build Veo prompt with camera angle, dialogue, and voice delivery
        full_prompt = (
            f"{visual_prompt} Camera: {camera_angle}. "
            f"The person speaks to camera: \"{script_text}\" "
            f"Voice delivery: {voice_direction}"
        )

        logger.info(f"Generating A-Roll scene {idx}/{len(aroll_scenes)} "
                   f"(duration: {duration_seconds}s)")
        logger.debug(f"A-Roll scene {idx} prompt: {full_prompt}")

        # Generate clip from hero image (image-to-video mode)
        clip_path = veo.generate_clip_from_image(
            prompt=full_prompt,
            image_path=hero_image_path,
            duration_seconds=duration_seconds,
            width=720,
            height=1280
        )

        clip_paths.append(clip_path)
        logger.info(f"A-Roll scene {idx} generated: {clip_path}")

    logger.info(f"All {len(clip_paths)} A-Roll clips generated successfully")
    return clip_paths


def generate_broll_assets(
    broll_shots: List[Dict[str, Any]],
    product_images: List[str]
) -> List[str]:
    """Generate B-Roll product shots via Imagen + Veo pipeline.

    Two-step process for each shot:
    1. Generate product image via Imagen (using product photo as reference)
    2. Animate the image via Veo image-to-video

    Each shot specifies a reference_image_index to select which uploaded product
    image to use as the Imagen reference, enabling varied angles across shots.

    Args:
        broll_shots: List of B-Roll shot dicts with keys:
            - image_prompt: Static product image description
            - animation_prompt: Motion/animation description
            - duration_seconds: Clip duration
            - reference_image_index: Index into product_images list
        product_images: List of paths to uploaded product photos

    Returns:
        List of paths to B-Roll video clips in shot order
    """
    logger.info(f"Generating {len(broll_shots)} B-Roll clips via Imagen → Veo pipeline "
                f"(using {len(product_images)} reference images)")

    # Get providers
    image_provider = get_image_provider()
    veo = _get_veo_or_mock()

    clip_paths = []
    for idx, shot in enumerate(broll_shots, 1):
        image_prompt = shot.get("image_prompt", "")
        animation_prompt = shot.get("animation_prompt", "")
        duration_seconds = shot.get("duration_seconds", 5)
        ref_index = shot.get("reference_image_index", 0)

        # Clamp reference_image_index to valid range
        ref_index = max(0, min(ref_index, len(product_images) - 1))
        reference_image = product_images[ref_index]

        logger.info(f"Generating B-Roll shot {idx}/{len(broll_shots)} "
                   f"(ref image {ref_index}, Step 1: Imagen, Step 2: Veo)")
        logger.debug(f"B-Roll shot {idx} image prompt: {image_prompt}")
        logger.debug(f"B-Roll shot {idx} animation prompt: {animation_prompt}")

        # Step 1: Generate product image via Imagen
        product_shot_paths = image_provider.generate_image(
            prompt=image_prompt,
            width=720,
            height=1280,
            num_images=1,
            reference_images=[reference_image]
        )
        product_shot_path = product_shot_paths[0]
        logger.info(f"B-Roll shot {idx} product image generated: {product_shot_path}")

        # Step 2: Animate via Veo image-to-video
        clip_path = veo.generate_clip_from_image(
            prompt=animation_prompt,
            image_path=product_shot_path,
            duration_seconds=duration_seconds,
            width=720,
            height=1280
        )

        clip_paths.append(clip_path)
        logger.info(f"B-Roll shot {idx} animated clip generated: {clip_path}")

    logger.info(f"All {len(clip_paths)} B-Roll clips generated successfully")
    return clip_paths
