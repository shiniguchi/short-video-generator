"""Script engine service for UGC ad pipeline."""
import logging
from typing import Optional, List

from app.schemas import ProductAnalysis, AdBreakdown
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


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

    # Call 1: Generate master script text
    master_script_prompt = f"""Product: {product_name}
Description: {description}

Product Analysis:
- Category: {analysis.category}
- Key Features: {', '.join(analysis.key_features)}
- Target Audience: {analysis.target_audience}
- UGC Style: {analysis.ugc_style}
- Emotional Tone: {analysis.emotional_tone}

Write a viral UGC ad script for a {target_duration}-second vertical video (9:16). Follow this EXACT timing structure:

HOOK (0-3 seconds):
- One punchy sentence that stops the scroll. Use a bold claim, surprising question, or relatable frustration.
- Example patterns: "I was today years old when I found out...", "POV: you finally found...", "Stop scrolling if you..."
- Must create instant curiosity or emotional reaction.

PROBLEM (3-8 seconds):
- Describe the pain point the viewer relates to. Make it personal ("You know when you...").
- Be specific — generic problems don't convert. Name the exact frustration.

PROOF (8-22 seconds):
- Show the product solving the problem. This is the longest section.
- Include: what it does, how it feels/works, a specific result or social proof.
- Mention the product name naturally, not like reading an ad.
- Weave in 1-2 key features as benefits, not feature lists.

CTA (22-{target_duration} seconds):
- Direct and urgent. Tell them exactly what to do: "Link in bio", "Use code X for Y% off", "Comment LINK and I'll send it to you".
- Add scarcity or social proof: "This sold out twice", "Over 10K reviews".

CRITICAL RULES:
- Write ONLY the words the person speaks to camera. No stage directions, no [brackets], no (parentheses).
- Sound like a real person talking to a friend, not a voiceover artist reading copy.
- Use contractions, filler words sparingly ("honestly", "literally", "like"), and natural speech rhythms.
- The script must be speakable in {target_duration} seconds at natural pace (~3 words/second)."""

    system_prompt = (
        "You are a top-performing UGC ad creator who has generated millions in revenue "
        "for DTC brands. You write scripts that sound completely natural and unscripted, "
        "but are carefully engineered for conversion. Every word earns its place."
    )

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
Visual Keywords: {', '.join(analysis.visual_keywords)}

Master Script:
{master_script_text}

Break this script into a complete Ad Breakdown for Veo 3 video generation and Imagen image generation.

=== MASTER SCRIPT ===
Parse the script above into hook/problem/proof/cta sections. Include full_script as the complete text and total_duration as {target_duration}.

=== A-ROLL SCENES (creator talking to camera) ===
Create 4-6 scenes, each 6-8 seconds (Veo generates max 8s clips). Scenes must cover the ENTIRE script with no gaps.

For each scene provide:
- frame_number: Sequential (1, 2, 3...)
- duration_seconds: 6-8 (must fit within Veo's 8s limit)
- visual_prompt: Detailed Veo prompt describing the creator's appearance, gestures, product interaction, and setting. Example: "Young woman in casual white tee, holding [product] at chest height, gesturing with free hand, well-lit bedroom, natural window light, smartphone selfie angle"
- camera_angle: One of: "close-up" (face only), "medium close-up" (head+shoulders), "medium shot" (waist up), "POV" (first-person), "over-shoulder"
- voice_direction: How the person delivers the line — tone, pacing, energy. Example: "Excited and fast-paced, slight laugh at the end", "Slower, sincere, looking directly at camera"
- script_text: The EXACT words spoken in this scene (subset of the master script). Must be natural dialogue that Veo 3 will generate as speech audio.

Scene guidance:
- Scene 1 (HOOK): Medium close-up, high energy, eye contact with camera, no product yet or product reveal
- Scene 2 (PROBLEM): Close-up on face showing frustration/relatability, leaning toward camera
- Scenes 3-4 (PROOF): Medium shot showing product in use, demonstrating features, genuine reactions
- Scene 5-6 (CTA): Medium close-up, confident delivery, product visible, direct eye contact

=== B-ROLL SHOTS (product close-ups) ===
Create 3-5 product shots. These overlay on top of A-Roll during the PROOF section when the product is mentioned.

For each shot provide:
- shot_number: Sequential (1, 2, 3...)
- image_prompt: Imagen prompt for a product-focused photo. Include specific angles and styling. Examples: "Close-up of [product] on white marble surface, soft directional light, shallow depth of field", "Flat-lay of [product] with lifestyle props, overhead shot, clean aesthetic"
- animation_prompt: Veo image-to-video motion description. Keep it subtle: "Slow push-in revealing product details", "Gentle rotation with soft light shift", "Slow dolly across product surface"
- duration_seconds: 5 (standard B-Roll length)
- overlay_start: Timestamp in the timeline when this B-Roll appears (must be within 8-22s PROOF section)
- reference_image_index: Which uploaded product image to use as Imagen reference (0-indexed). Distribute across available images.

B-Roll angle variety:
- Shot 1: Close-up product detail (texture, label, key feature)
- Shot 2: Flat-lay or lifestyle context (product in natural setting)
- Shot 3: In-use / application shot (product being used)
- Shot 4-5 (optional): Packaging, ingredient list, or result/before-after

=== CRITICAL RULES ===
1. A-Roll scene script_text segments must concatenate to form the complete master script. No words missing, no words added.
2. A-Roll total duration must equal approximately {target_duration} seconds.
3. B-Roll overlay_start values must be within the timeline (0 to {target_duration}) and concentrated in the PROOF section (8-22s).
4. All prompts must be concrete visual descriptions — no abstract concepts, no marketing speak.
5. reference_image_index values should be distributed: if 3 images uploaded, use indices 0, 1, 2 across shots."""

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
