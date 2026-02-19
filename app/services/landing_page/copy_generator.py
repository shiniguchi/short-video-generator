"""AI copy generator for landing pages using proven copywriting formulas."""

import logging
from typing import Optional, List
from app.schemas import LandingPageCopy, LPResearchResult
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


# PAS (Problem-Agitate-Solution) formula template
_PAS_PROMPT = """
Generate landing page copy using the Problem-Agitate-Solution (PAS) formula.

Product Idea: {product_idea}
Target Audience: {target_audience}

Research Context (patterns from top-performing LPs):
{research_context}

PAS Formula Structure:
1. HEADLINE: State the problem as a compelling hook
   - Make it relatable and immediate
   - Second-person ("you") address
   - 8-12 words max

2. SUBHEADLINE: Agitate the emotional cost of the problem
   - What pain/frustration does this problem cause?
   - Build urgency without fear-mongering
   - 15-25 words

3. BENEFITS: Present the solution in 3 specific benefits
   - Each benefit: title (3-5 words), description (10-15 words), icon emoji
   - Focus on transformation/outcome, not features
   - Be concrete and specific

4. CTA: Clear, direct action
   - 2-4 words max
   - Action-oriented ("Get Started", "Join Waitlist", "Start Free")

5. SOCIAL PROOF: Use implied proof only
   - Soft signals like "Join 1,000+ early users" or "Built by the team behind..."
   - NO fake testimonials or fabricated stats
   - Keep it authentic and modest

TONE: Conversational, friendly, direct, second-person ("you"). NOT corporate or salesy.

Generate all required fields following the research patterns above.
"""

# AIDA (Attention-Interest-Desire-Action) formula template
_AIDA_PROMPT = """
Generate landing page copy using the AIDA (Attention-Interest-Desire-Action) formula.

Product Idea: {product_idea}
Target Audience: {target_audience}

Research Context (patterns from top-performing LPs):
{research_context}

AIDA Formula Structure:
1. HEADLINE: Grab attention with a bold statement
   - Surprising, provocative, or intriguing
   - Second-person ("you") address
   - 8-12 words max

2. SUBHEADLINE: Build interest with specificity
   - What makes this unique or different?
   - Hint at the value proposition
   - 15-25 words

3. BENEFITS: Create desire through 3 specific outcomes
   - Each benefit: title (3-5 words), description (10-15 words), icon emoji
   - Paint the picture of life after using the product
   - Be aspirational yet believable

4. CTA: Direct call to action
   - 2-4 words max
   - Action-oriented ("Get Started", "Join Waitlist", "Start Free")

5. SOCIAL PROOF: Use implied proof only
   - Soft signals like "Join 1,000+ early users" or "Built by the team behind..."
   - NO fake testimonials or fabricated stats
   - Keep it authentic and modest

TONE: Conversational, friendly, direct, second-person ("you"). NOT corporate or salesy.

Generate all required fields following the research patterns above.
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

    # Select formula template
    prompt_template = _PAS_PROMPT if formula == "PAS" else _AIDA_PROMPT

    # Build prompt
    prompt = prompt_template.format(
        product_idea=product_idea,
        target_audience=target_audience,
        research_context=research_context
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

    Args:
        product_idea: The product being marketed (used in headline for realism)

    Returns:
        LandingPageCopy with mock data
    """
    return LandingPageCopy(
        headline=f"Transform Your Workflow with {product_idea}",
        subheadline="Stop wasting hours on manual tasks. Get back to what matters most with our AI-powered solution.",
        benefits=[
            {
                "title": "Save Time Daily",
                "description": "Automate repetitive work and reclaim hours every week for strategic thinking.",
                "icon_emoji": "⚡"
            },
            {
                "title": "Boost Productivity",
                "description": "Get more done with less effort using intelligent automation and smart workflows.",
                "icon_emoji": "🚀"
            },
            {
                "title": "Scale Effortlessly",
                "description": "Grow your output without growing your team or your stress levels.",
                "icon_emoji": "📈"
            }
        ],
        cta_text="Join the Waitlist",
        social_proof_text="Join 1,000+ early users already transforming their workflow",
        footer_text="© 2026 ViralForge. Built for modern teams.",
        meta_title=f"{product_idea} - Transform Your Workflow",
        meta_description=f"Stop wasting time on manual tasks. {product_idea} helps you automate, scale, and focus on what matters most."
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
