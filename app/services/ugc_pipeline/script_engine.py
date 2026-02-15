"""Script engine service for UGC ad pipeline."""
import logging
from typing import Optional, List

from app.schemas import ProductAnalysis, AdBreakdown
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


# Category-specific prompt templates for Hook-Problem-Proof-CTA structure
CATEGORY_PROMPTS = {
    "cosmetics": (
        "Create a UGC ad script for a cosmetics product. Focus on: "
        "1) Hook: Relatable beauty struggle or transformation tease "
        "2) Problem: Common skin/beauty issues the product solves "
        "3) Proof: Before/after results, texture/application demo, glowing skin "
        "4) CTA: Where to buy, discount code, or follow for more beauty tips. "
        "Use emotional tone that's authentic and excited."
    ),
    "tech": (
        "Create a UGC ad script for a tech product. Focus on: "
        "1) Hook: Problem scenario or 'what if you could...' question "
        "2) Problem: Daily frustrations or inefficiencies "
        "3) Proof: Feature demo, speed comparison, user testimonials "
        "4) CTA: Link in bio, early bird discount, or tech specs. "
        "Use educational and aspirational tone."
    ),
    "food": (
        "Create a UGC ad script for a food product. Focus on: "
        "1) Hook: Taste reaction, cooking shortcut reveal "
        "2) Problem: Lack of time, boring meals, or dietary restrictions "
        "3) Proof: Cooking process, taste test, nutritional benefits "
        "4) CTA: Order link, recipe download, or meal plan. "
        "Use authentic and enthusiastic tone."
    ),
    "fashion": (
        "Create a UGC ad script for a fashion product. Focus on: "
        "1) Hook: Style transformation or 'get ready with me' opening "
        "2) Problem: Wardrobe gaps, uncomfortable clothing, or style struggles "
        "3) Proof: Try-on haul, outfit styling, comfort demo "
        "4) CTA: Shop link, discount code, or outfit inspo page. "
        "Use aspirational and authentic tone."
    ),
    "saas": (
        "Create a UGC ad script for a SaaS product. Focus on: "
        "1) Hook: Productivity pain point or time-saving claim "
        "2) Problem: Manual workflows, expensive tools, or team collaboration issues "
        "3) Proof: Screen recording demo, ROI stats, customer success stories "
        "4) CTA: Free trial link, demo booking, or pricing page. "
        "Use educational and professional tone."
    ),
    "default": (
        "Create a UGC ad script following Hook-Problem-Proof-CTA structure. "
        "1) Hook: Capture attention in first 3 seconds with relatable scenario or bold claim "
        "2) Problem: Identify pain point the product solves (3-8 seconds) "
        "3) Proof: Show product in action with social proof or results (8-20 seconds) "
        "4) CTA: Clear call-to-action for next step (final 5-10 seconds). "
        "Use authentic and engaging tone."
    )
}


def generate_ugc_script(
    product_name: str,
    description: str,
    analysis: ProductAnalysis,
    target_duration: int = 30
) -> AdBreakdown:
    """Generate UGC ad script and A-Roll/B-Roll breakdown using two-call pattern.
    
    Call 1: Generate master ad script using Hook-Problem-Proof-CTA structure
    Call 2: Break script into A-Roll scenes (4-8s each, Veo limit) and B-Roll shots (5s each)
    
    Args:
        product_name: Product name
        description: Product description
        analysis: ProductAnalysis from analyze_product()
        target_duration: Target duration in seconds (25-30s typical)
    
    Returns:
        AdBreakdown with master_script, aroll_scenes, broll_shots, and total_duration
    """
    llm = get_llm_provider()
    
    # Get category-specific guidance
    category_guidance = CATEGORY_PROMPTS.get(
        analysis.category.lower(),
        CATEGORY_PROMPTS["default"]
    )
    
    # Call 1: Generate master script text
    master_script_prompt = f"""Product: {product_name}
Description: {description}

Product Analysis:
- Category: {analysis.category}
- Key Features: {', '.join(analysis.key_features)}
- Target Audience: {analysis.target_audience}
- UGC Style: {analysis.ugc_style}
- Emotional Tone: {analysis.emotional_tone}

{category_guidance}

Target Duration: {target_duration} seconds

Write a complete UGC ad script following the Hook-Problem-Proof-CTA framework. Make it conversational and authentic, like a real person talking directly to camera."""
    
    system_prompt = "You are a viral UGC ad script writer specializing in short-form video content."
    
    logger.info(f"LLM Call 1/2: Generating master script for '{product_name}' ({analysis.category})")
    
    master_script_text = llm.generate_text(
        prompt=master_script_prompt,
        system_prompt=system_prompt,
        temperature=0.8,
        max_tokens=2048
    )
    
    logger.info(f"Call 1 complete: {len(master_script_text)} chars of master script")
    
    # Call 2: Generate structured breakdown with A-Roll/B-Roll
    breakdown_prompt = f"""Product: {product_name}
Category: {analysis.category}
UGC Style: {analysis.ugc_style}
Target Duration: {target_duration} seconds

Master Script:
{master_script_text}

Product Analysis:
- Key Features: {', '.join(analysis.key_features)}
- Emotional Tone: {analysis.emotional_tone}
- Visual Keywords: {', '.join(analysis.visual_keywords)}

Break this master script into a complete Ad Breakdown:

1. MasterScript: Parse the script into Hook/Problem/Proof/CTA sections with durations
2. A-Roll Scenes: UGC creator talking to camera, 4-8 seconds each (Veo limit)
   - Each scene needs: frame_number, duration_seconds, visual_prompt (creator appearance + action), voice_direction (tone/delivery), script_text (words spoken)
3. B-Roll Shots: Product close-ups or lifestyle shots, 5 seconds each
   - Each shot needs: shot_number, image_prompt (for Imagen), animation_prompt (for Veo image-to-video), duration_seconds (5s), overlay_start (when to overlay in timeline)

Ensure total duration is approximately {target_duration} seconds. A-Roll scenes should cover the full script. B-Roll shots overlay during key moments (product mentions, features, proof)."""
    
    logger.info(f"LLM Call 2/2: Generating A-Roll/B-Roll breakdown")
    
    breakdown = llm.generate_structured(
        prompt=breakdown_prompt,
        schema=AdBreakdown,
        system_prompt=system_prompt,
        temperature=0.7
    )
    
    logger.info(
        f"Ad breakdown complete: {len(breakdown.aroll_scenes)} A-Roll scenes, "
        f"{len(breakdown.broll_shots)} B-Roll shots, {breakdown.total_duration}s total"
    )
    
    return breakdown
