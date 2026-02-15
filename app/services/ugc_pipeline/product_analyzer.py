"""Product analyzer service for UGC ad pipeline."""
import logging
from typing import Optional

from app.schemas import ProductAnalysis
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


def analyze_product(
    product_name: str,
    description: str,
    image_count: int,
    style_preference: Optional[str] = None,
    product_url: Optional[str] = None
) -> ProductAnalysis:
    """Analyze product for UGC ad creation using LLMProvider.

    Uses LLM to extract category, key features, target audience, recommended UGC style,
    emotional tone, and visual keywords for downstream image/video generation.

    Args:
        product_name: Product name
        description: Product description
        image_count: Number of images/videos to generate (affects visual keyword count)
        style_preference: Optional style preference (selfie-review, unboxing, tutorial, lifestyle)
        product_url: Optional product URL for additional brand/product context

    Returns:
        ProductAnalysis with category, features, audience, style, tone, and visual keywords
    """
    llm = get_llm_provider()

    # Build prompt
    prompt_parts = [
        f"Product Name: {product_name}",
        f"Description: {description}",
        f"Image/Video Count: {image_count}",
    ]

    if product_url:
        prompt_parts.append(f"Product URL: {product_url}")

    if style_preference:
        prompt_parts.append(f"Preferred Style: {style_preference}")

    prompt_parts.append("""
Analyze this product for a viral UGC ad campaign using the Hook-Problem-Proof-CTA framework.

For visual_keywords, provide specific descriptors that will be used in Veo video and Imagen image prompts:
- Include product appearance details (color, texture, size, packaging)
- Include setting/environment keywords (indoor, natural light, kitchen counter, desk setup)
- Include UGC aesthetic keywords (smartphone quality, raw, authentic, selfie-angle)
- Include action keywords (holding, applying, demonstrating, unboxing)
- Do NOT include abstract marketing terms — only visually concrete descriptors""")
    prompt = "\n".join(prompt_parts)

    system_prompt = (
        "You are a UGC marketing strategist specializing in viral short-form product ads. "
        "You analyze products to create scroll-stopping Hook-Problem-Proof-CTA ads. "
        "Your analysis directly feeds into Veo 3 video generation and Imagen image generation, "
        "so visual_keywords must be concrete and camera-ready, not abstract marketing jargon."
    )

    logger.info(f"Analyzing product '{product_name}' (style: {style_preference or 'auto'}, url: {product_url or 'none'})")

    # Generate structured analysis
    analysis = llm.generate_structured(
        prompt=prompt,
        schema=ProductAnalysis,
        system_prompt=system_prompt,
        temperature=0.7
    )

    logger.info(f"Product analysis complete: category='{analysis.category}', ugc_style='{analysis.ugc_style}'")

    return analysis
