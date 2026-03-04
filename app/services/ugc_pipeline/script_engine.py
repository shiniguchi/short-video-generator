"""Script engine service for UGC ad pipeline."""
import logging
from typing import Optional, List

from app.schemas import ProductAnalysis, AdBreakdown

logger = logging.getLogger(__name__)


def generate_ugc_script(
    product_name: str,
    description: str,
    analysis: ProductAnalysis,
    target_duration: int = 30,
    use_mock: bool = False,
) -> AdBreakdown:
    """Generate UGC ad script and A-Roll/B-Roll breakdown using two-call pattern.

    Call 1: Generate master ad script using Hook-Problem-Proof-CTA structure
    Call 2: Break script into A-Roll scenes (4-8s each, Veo limit) and B-Roll shots (5s each)

    Args:
        product_name: Product name
        description: Product description
        analysis: ProductAnalysis from analyze_product()
        target_duration: Target duration in seconds (25-30s typical)
        use_mock: Use mock LLM provider instead of real API

    Returns:
        AdBreakdown with master_script, aroll_scenes, broll_shots, and total_duration
    """
    # Instantiate provider directly based on use_mock flag
    if use_mock:
        from app.services.llm_provider.mock import MockLLMProvider
        llm = MockLLMProvider()
    else:
        from app.services.llm_provider.gemini import GeminiLLMProvider
        from app.config import get_settings
        settings = get_settings()
        llm = GeminiLLMProvider(api_key=settings.google_api_key)

    # Call 1: Generate master script text
    master_script_prompt = f"""Product: {product_name}
Description: {description}

Product Analysis:
- Category: {analysis.category}
- Key Features: {', '.join(analysis.key_features)}
- Target Audience: {analysis.target_audience}
- Video Style: {analysis.ugc_style}
- Emotional Tone: {analysis.emotional_tone}

Write a viral ad script for a {target_duration}-second vertical video (9:16). This should sound like something a Gen-Z or millennial creator would actually post — not an ad agency script read by a voiceover artist.

HOOK (0-3 seconds):
- One line that makes someone stop mid-scroll. It should feel like overhearing something juicy.
- Use patterns trending NOW: "okay but why is nobody talking about this", "no because this actually changed my life", "the way I gatekept this for too long", "bestie you NEED this", "tell me why this random [product] is going viral rn"
- Avoid: anything that sounds like a TV commercial or a clickbait headline from 2018.

PROBLEM (3-8 seconds):
- Call out a specific, relatable struggle. Make the viewer think "omg literally me".
- Talk TO them, not AT them. Use "you" and "we", not "people" or "consumers".
- Be hyper-specific — vague problems = boring. Name the exact frustration they feel.
- Example energy: "because I was SO tired of [specific thing] and nothing was working"

PROOF (8-22 seconds):
- Show the product as a genuine discovery, not a sales pitch.
- Talk about it like you're texting your group chat: what it does, how it feels, why you're obsessed.
- Drop the product name casually — not as an announcement.
- Share a real-feeling result or reaction ("I literally used this for a week and...")
- Weave in 1-2 features as things you noticed, not a spec sheet.

CTA (22-{target_duration} seconds):
- Keep it casual but clear. Tell them what to do next like you're helping a friend out.
- Example energy: "I'll leave the link", "trust me just try it", "run don't walk", "you can thank me later"
- Optional: scarcity that feels real ("they keep selling out", "idk how long this deal lasts")

VOICE & TONE RULES:
- Write ONLY the words spoken to camera. No stage directions, no [brackets], no (parentheses).
- This should sound like a real person filming on their phone — raw, unpolished, authentic.
- Use the way people ACTUALLY talk: contractions, mid-sentence pivots, emphasis words ("literally", "actually", "honestly", "lowkey", "ngl").
- Short punchy sentences. Break thoughts up. Let pauses happen naturally.
- Match the energy of trending TikTok and Reels creators — not a brand's social media manager.
- The script must be speakable in {target_duration} seconds at natural pace (~3 words/second).
- NEVER use corporate phrases like "game-changer", "revolutionary", "innovative solution", "take your X to the next level", "look no further"."""

    system_prompt = (
        "You are a 22-year-old creator who blew up on TikTok and Reels. "
        "You talk to camera like you're FaceTiming your best friend. "
        "Your scripts feel raw and off-the-cuff but every word is intentional. "
        "You never sound like an ad — you sound like a friend sharing a secret."
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
Video Style: {analysis.ugc_style}
Target Duration: {target_duration} seconds
Visual Keywords: {', '.join(analysis.visual_keywords)}

Master Script:
{master_script_text}

Break this script into a complete Ad Breakdown for Veo 3 video generation.

=== MASTER SCRIPT ===
Parse the script above into hook/problem/proof/cta sections. Include full_script as the complete text and total_duration as {target_duration}.

IMPORTANT — creator_persona: Write ONE detailed physical description of the creator that stays the SAME across every scene. Include: gender, age range, ethnicity, hair, clothing, and setting. Make them look like an actual Gen-Z/millennial creator — trendy but effortless. Example: "Early 20s woman with long dark hair in a claw clip, oversized vintage band tee and gold hoops, sitting cross-legged on a bed with fairy lights in background, golden hour lighting from window"

IMPORTANT — voice_direction: Write ONE overall voice style for the entire video. Should match how popular creators actually talk — expressive, natural pauses, genuine reactions. Example: "Excited best-friend energy, talking fast when hyped then slowing down for emphasis, little laughs between thoughts, direct eye contact, hand gestures while talking"

=== A-ROLL SCENES (creator talking to camera) ===
Create 4-6 scenes, each exactly 8 seconds (Veo maximum clip length). Scenes must cover the ENTIRE script with no gaps.

IMPORTANT: All video clips are generated from a SINGLE reference image of the creator. The visual_prompt describes ONLY motion, gestures, expressions, and camera movement — NOT the person's appearance (that comes from the reference image automatically).

For each scene provide:
- frame_number: Sequential (1, 2, 3...)
- duration_seconds: Always 8 (Veo maximum clip length)
- visual_prompt: Describe ONLY motion, gestures, expressions, and camera movement for Veo video generation. Do NOT describe the person's appearance. Example: "Leaning toward camera with excited expression, holding product at chest height, gesturing with free hand, slow push-in camera movement"
- camera_angle: One of: "close-up" (face only), "medium close-up" (head+shoulders), "medium shot" (waist up), "POV" (first-person), "over-shoulder"
- script_text: The EXACT words spoken in this scene (subset of the master script). Must be natural dialogue that Veo 3 will generate as speech audio.

Scene guidance:
- Scene 1 (HOOK): "Wait let me tell you" energy — leaning in, eyes wide, grabbing camera's attention like they just remembered something important
- Scene 2 (PROBLEM): Eye-roll moment, head shake, "ugh you know what I mean" expression, relatable frustration
- Scenes 3-4 (PROOF): Glow-up moment — holding product up to camera, genuine smile, showing it off like sharing a find with a friend, natural movements
- Scene 5-6 (CTA): Confident nod, pointing at camera or tapping link area, "trust me on this" energy, warm smile

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
5. reference_image_index values should be distributed: if 3 images uploaded, use indices 0, 1, 2 across shots.

=== VIDEO SAFETY — MANDATORY ===
Visual prompts (visual_prompt, image_prompt, animation_prompt) are sent directly to Google Veo and Imagen APIs which have strict safety filters. Prompts WILL BE REJECTED if they contain:
- People in bathrobes, towels, swimwear, underwear, or any state of undress
- Bathtub, shower, or bathroom scenes with people present
- Suggestive poses, "inviting" expressions, or intimate framing
- Medical/health before-after imagery
- Children or minors in any context
- Violence, weapons, or dangerous activities
- Specific real celebrities or public figures

INSTEAD: Keep people fully clothed (sweater, casual shirt, etc). Use neutral settings (living room, kitchen counter, desk, outdoor patio). Describe friendly/confident expressions, never "inviting" or "seductive". Focus on the product, not the person's body."""

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


def resplit_script_to_scenes(full_script: str, num_scenes: int, use_mock: bool = False) -> list[str]:
    """Re-split full_script into scene speaking segments using LLM.

    Used when section fields (hook/problem/proof/cta) change and scene
    script_text values need to realign with the updated full_script.

    Args:
        full_script: Complete script text (hook + problem + proof + cta)
        num_scenes: Number of scene segments to produce
        use_mock: Use mock provider instead of real LLM

    Returns:
        List of script_text strings, one per scene
    """
    if not full_script or num_scenes <= 0:
        return []

    if use_mock:
        # Split by paragraph breaks (sections are joined by \n\n)
        parts = [p.strip() for p in full_script.split("\n\n") if p.strip()]
        while len(parts) < num_scenes:
            parts.append("")
        return parts[:num_scenes]

    from pydantic import BaseModel

    from app.config import get_settings
    from app.services.llm_provider.gemini import GeminiLLMProvider

    settings = get_settings()
    llm = GeminiLLMProvider(api_key=settings.google_api_key)

    class ScriptSegments(BaseModel):
        segments: list[str]

    prompt = f"""Split this UGC ad script into exactly {num_scenes} speaking segments for video scenes.

Rules:
1. Each segment = one natural speaking take (complete thought, 1-3 sentences)
2. Segments must concatenate to form the EXACT original text. No words added or removed.
3. Return exactly {num_scenes} segments.

Script:
{full_script}"""

    result = llm.generate_structured(
        prompt=prompt,
        schema=ScriptSegments,
        system_prompt="Split scripts into speaking segments. Preserve every word exactly.",
        temperature=0.2,
    )

    segments = result.segments[:num_scenes]
    while len(segments) < num_scenes:
        segments.append("")
    return segments
