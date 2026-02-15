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
    style_preference: Optional[str] = None
) -> ProductAnalysis:
    """Analyze product for UGC ad creation using LLMProvider.
    
    Uses LLM to extract category, key features, target audience, recommended UGC style,
    emotional tone, and visual keywords for downstream image/video generation.
    
    Args:
        product_name: Product name
        description: Product description
        image_count: Number of images/videos to generate (affects visual keyword count)
        style_preference: Optional style preference (selfie-review, unboxing, tutorial, lifestyle)
    
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
    
    if style_preference:
        prompt_parts.append(f"Preferred Style: {style_preference}")
    
    prompt_parts.append("\nAnalyze this product for UGC ad creation.")
    prompt = "\n".join(prompt_parts)
    
    system_prompt = "You are a UGC marketing strategist analyzing products for viral ad campaigns."
    
    logger.info(f"Analyzing product '{product_name}' (style: {style_preference or 'auto'})")
    
    # Generate structured analysis
    analysis = llm.generate_structured(
        prompt=prompt,
        schema=ProductAnalysis,
        system_prompt=system_prompt,
        temperature=0.7
    )
    
    logger.info(f"Product analysis complete: category='{analysis.category}', ugc_style='{analysis.ugc_style}'")
    
    return analysis
