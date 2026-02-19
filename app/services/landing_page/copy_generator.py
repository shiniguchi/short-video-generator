"""AI copy generator for landing pages using proven copywriting formulas."""

import logging
from typing import Optional, List
from app.schemas import LandingPageCopy, LPResearchResult
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


_COPY_PROMPT = """
Generate high-converting landing page copy for a product waitlist page.

Product: {product_idea}
Target Audience: {target_audience}
Formula: {formula}

Research Context (patterns from top-performing LPs):
{research_context}

CRITICAL RULES — follow these exactly:
- HEADLINE: 5-8 words ONLY. Benefit-driven. Specific to THIS product. Second-person "you".
  BAD: "Your Product Awaits" or "Transform Your Workflow"
  GOOD: "Never Drink Warm Water Again" or "Clean Water, Zero Effort"
- SUBHEADLINE: 15-25 words. Expands the headline with a specific, quantified claim.
- BENEFITS: 3 items. Each MUST be specific to this product's actual features.
  Each has: title (3-5 words), description (15-20 words with a number/stat), icon_emoji
  BAD: "Save Time" / "Zero Hassle" / "Join Early" (generic, applies to anything)
  GOOD: "24-Hour Cold Retention" / "Self-Cleans Every 2 Hours" / "30-Day Battery Life"
- FEATURES: 3-4 items. Product specs turned into benefits.
  Each has: title, description, stat (a number like "24hrs", "2min", "99.9%")
- HOW IT WORKS: Exactly 3 steps. Simple, visual, numbered.
  Each has: step_number (1/2/3), title (2-4 words), description (10-15 words)
- FAQ: 3-5 items. Answer real objections the target audience would have.
  Each has: question, answer (2-3 sentences max)
- CTA TEXT: 2-4 words. Action verb + benefit. NOT "Submit" or "Click Here".
  GOOD: "Get Early Access", "Reserve Yours", "Join Free"
- URGENCY TEXT: One line creating scarcity. "Limited early access" or "First 500 get priority".
- SOCIAL PROOF: Include a specific number. "Join 2,000+ early adopters" not "Join others".
- TRUST TEXT: Privacy reassurance. "We'll never spam you. Unsubscribe anytime."
- META TITLE: Under 60 characters. Product name + value prop.
- META DESCRIPTION: ~160 characters. Compelling reason to click.

TONE: Conversational, friendly, direct. Second-person "you". NO corporate jargon. NO hype.
FORMULA: If PAS — headline = problem hook, subheadline = agitate, benefits = solution.
         If AIDA — headline = attention, subheadline = interest, benefits = desire.

Generate ALL fields. Every benefit, feature, and FAQ must be specific to this exact product.
"""


def _format_research_context(research_result: LPResearchResult) -> str:
    """
    Format research patterns into a readable string for the LLM prompt.

    Args:
        research_result: Research patterns from competitor LPs

    Returns:
        Formatted research context string
    """
    context_parts = []

    # Top headline examples
    if research_result.patterns:
        top_headlines = [p.hero_headline for p in research_result.patterns[:3]]
        context_parts.append("Top Headline Patterns:")
        for i, headline in enumerate(top_headlines, 1):
            context_parts.append(f"  {i}. {headline}")

    # CTA styles
    if research_result.dominant_cta_style:
        context_parts.append(f"\nMost Common CTA Style: {research_result.dominant_cta_style}")

    # Section order trends
    if research_result.common_sections:
        context_parts.append(f"\nCommon Sections: {', '.join(research_result.common_sections)}")

    # Video placement trend
    if research_result.video_placement_trend:
        context_parts.append(f"\nVideo Placement Trend: {research_result.video_placement_trend}")

    return "\n".join(context_parts) if context_parts else "No specific research patterns available."


def generate_lp_copy(
    product_idea: str,
    target_audience: str,
    research_result: LPResearchResult,
    formula: str = "PAS"
) -> LandingPageCopy:
    """
    Main entry point for AI copy generation using LLM provider.

    Args:
        product_idea: The product or service being marketed
        target_audience: Who this product is for
        research_result: Research patterns from competitor LPs
        formula: Copywriting formula to use ("PAS" or "AIDA")

    Returns:
        LandingPageCopy with all fields populated

    Raises:
        ValueError: If invalid formula specified
    """
    if formula not in ["PAS", "AIDA"]:
        raise ValueError(f"Invalid formula: {formula}. Must be 'PAS' or 'AIDA'")

    # Format research context
    research_context = _format_research_context(research_result)

    # Build prompt
    prompt = _COPY_PROMPT.format(
        product_idea=product_idea,
        target_audience=target_audience,
        research_context=research_context,
        formula=formula
    )

    # System prompt
    system_prompt = (
        "You are an expert landing page copywriter specializing in conversion-focused copy. "
        "You understand proven copywriting formulas and create compelling, authentic copy "
        "that connects with audiences without hype or manipulation. "
        "You always follow research-backed patterns and write in a conversational, friendly tone."
    )

    # Generate structured copy
    llm = get_llm_provider()
    logger.info(f"Generating LP copy using {formula} formula for: {product_idea}")

    copy = llm.generate_structured(
        prompt=prompt,
        schema=LandingPageCopy,
        system_prompt=system_prompt,
        temperature=0.9  # Slightly creative but consistent
    )

    logger.info(f"Generated copy with headline: {copy.headline}")
    return copy


def get_mock_copy(product_idea: str) -> LandingPageCopy:
    """
    Returns realistic mock copy for development without LLM API calls.
    Follows LP_DESIGN_CHECKLIST.md rules for high-converting copy.

    Args:
        product_idea: The product being marketed (used in headline for realism)

    Returns:
        LandingPageCopy with mock data
    """
    # Extract a short product name from a potentially long description
    product_name = product_idea.split(" - ")[0].split(". ")[0].split(", ")[0]
    if len(product_name.split()) > 6:
        product_name = " ".join(product_name.split()[:5])

    return LandingPageCopy(
        headline=f"Never Settle for Less Than {product_name}",
        subheadline=f"The smarter way to get exactly what you need — designed for people who demand more from their everyday gear.",
        benefits=[
            {
                "title": "Built Around You",
                "description": f"Every detail of {product_name} is engineered for how you actually live and move.",
                "icon_emoji": "🎯"
            },
            {
                "title": "Works Instantly",
                "description": "Zero setup, zero learning curve. Unbox it and start using it in under 2 minutes.",
                "icon_emoji": "⚡"
            },
            {
                "title": "Lasts and Lasts",
                "description": "Premium materials built to handle your daily routine for years, not months.",
                "icon_emoji": "🛡️"
            }
        ],
        features=[
            {
                "title": "Smart Design",
                "description": f"Intelligent engineering that adapts to your needs throughout the day.",
                "stat": "24/7"
            },
            {
                "title": "Premium Build",
                "description": "Medical-grade materials that are safe, durable, and eco-friendly.",
                "stat": "100%"
            },
            {
                "title": "Long-Lasting Power",
                "description": "One charge lasts weeks, not days. USB-C fast charging included.",
                "stat": "30 days"
            }
        ],
        how_it_works=[
            {
                "step_number": 1,
                "title": "Unbox & Charge",
                "description": "Plug in via USB-C. Full charge in under an hour."
            },
            {
                "step_number": 2,
                "title": "Fill & Go",
                "description": "Add your favorite drink. The smart system handles the rest."
            },
            {
                "step_number": 3,
                "title": "Enjoy All Day",
                "description": "Perfect temperature, pure taste, zero maintenance required."
            }
        ],
        faq=[
            {
                "question": "When does it ship?",
                "answer": "We're targeting Q2 2026 for first shipments. Waitlist members get priority access and early-bird pricing."
            },
            {
                "question": "Is the waitlist free?",
                "answer": "Yes, completely free. No credit card required. You'll just be first to know when we launch."
            },
            {
                "question": "What makes this different?",
                "answer": f"{product_name} combines smart technology with premium materials. It's not just another product — it's designed for people who want the best."
            },
            {
                "question": "Can I cancel anytime?",
                "answer": "The waitlist has zero obligations. You can unsubscribe with one click anytime."
            }
        ],
        cta_text="Get Early Access",
        urgency_text="Limited to first 500 signups",
        social_proof_text="Join 2,000+ early adopters",
        trust_text="No spam, ever. Unsubscribe anytime.",
        footer_text=f"\u00a9 2026 {product_name}. All rights reserved.",
        meta_title=f"{product_name} — Get Early Access",
        meta_description=f"Join the waitlist for {product_name}. Be first to experience the next generation. Limited early access — sign up free."
    )


def generate_copy(
    product_idea: str,
    target_audience: str,
    research_result: LPResearchResult,
    use_mock: bool = False,
    formula: str = "PAS"
) -> LandingPageCopy:
    """
    Top-level dispatcher for copy generation.

    Args:
        product_idea: The product being marketed
        target_audience: Who this product is for
        research_result: Research patterns from competitor LPs
        use_mock: If True, return mock data instead of calling LLM
        formula: Copywriting formula ("PAS" or "AIDA")

    Returns:
        LandingPageCopy (mock or AI-generated)
    """
    if use_mock:
        logger.info(f"Using mock copy for: {product_idea}")
        return get_mock_copy(product_idea)

    return generate_lp_copy(product_idea, target_audience, research_result, formula)
