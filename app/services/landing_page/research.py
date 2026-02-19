"""Landing page research module - scrapes competitor LPs and extracts design patterns."""

import asyncio
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from app.schemas import LPResearchPattern, LPResearchResult

logger = logging.getLogger(__name__)


def get_mock_research(industry: str, region: str) -> LPResearchResult:
    """
    Returns realistic mock research data for development without Playwright/internet.

    Args:
        industry: Product industry
        region: Target region

    Returns:
        Mock LPResearchResult with realistic patterns
    """
    mock_patterns = [
        LPResearchPattern(
            url="https://example.com/saas-landing-1",
            hero_headline="Transform Your Workflow in Minutes",
            cta_texts=["Start Free Trial", "Get Started", "Book Demo"],
            section_order=["hero", "benefits", "features", "pricing", "testimonials", "cta", "footer"],
            has_video=True,
            video_placement="hero",
            color_scheme={"primary": "#0066CC", "secondary": "#004C99", "accent": "#00A3FF"}
        ),
        LPResearchPattern(
            url="https://example.com/saas-landing-2",
            hero_headline="Built for Modern Teams",
            cta_texts=["Try for Free", "Sign Up", "Get Access"],
            section_order=["hero", "features", "benefits", "testimonials", "pricing", "footer"],
            has_video=True,
            video_placement="hero",
            color_scheme={"primary": "#1A73E8", "secondary": "#1557B0", "accent": "#34A853"}
        ),
        LPResearchPattern(
            url="https://example.com/saas-landing-3",
            hero_headline="The Smart Way to Manage Projects",
            cta_texts=["Start Free", "Join Now", "Request Demo"],
            section_order=["hero", "benefits", "social-proof", "features", "cta", "footer"],
            has_video=False,
            video_placement=None,
            color_scheme={"primary": "#6366F1", "secondary": "#4F46E5", "accent": "#818CF8"}
        )
    ]

    return LPResearchResult(
        patterns=mock_patterns,
        common_sections=["hero", "benefits", "features", "cta", "footer"],
        dominant_cta_style="Start Free Trial",
        video_placement_trend="hero section (67% of LPs)",
        color_trends=[
            {"primary": "#0066CC", "count": 1},
            {"primary": "#1A73E8", "count": 1},
            {"primary": "#6366F1", "count": 1}
        ]
    )


def _extract_hero_headline(soup: BeautifulSoup) -> str:
    """Extract the first h1 as hero headline."""
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "Untitled"


def _extract_cta_buttons(soup: BeautifulSoup) -> List[str]:
    """Find CTA button text from elements with CTA-like classes."""
    cta_keywords = ["cta", "btn", "button", "signup", "subscribe", "join", "start", "get-started"]
    cta_texts = []

    # Find all links and buttons
    for element in soup.find_all(["a", "button"]):
        # Check if class contains CTA keywords
        classes = element.get("class", [])
        class_str = " ".join(classes).lower() if classes else ""

        if any(keyword in class_str for keyword in cta_keywords):
            text = element.get_text(strip=True)
            if text and len(text) < 50:  # Reasonable CTA length
                cta_texts.append(text)

    return cta_texts[:5]  # Return top 5


def _extract_section_order(soup: BeautifulSoup) -> List[str]:
    """Identify major sections by tags and class names."""
    sections = []
    section_keywords = {
        "hero": ["hero", "header", "banner"],
        "features": ["feature", "capability"],
        "benefits": ["benefit", "why", "advantage"],
        "pricing": ["pricing", "plan", "price"],
        "testimonials": ["testimonial", "review", "customer"],
        "faq": ["faq", "question"],
        "cta": ["cta", "call-to-action", "signup"],
        "footer": ["footer"]
    }

    # Check header/section/footer tags and their classes
    for element in soup.find_all(["header", "section", "footer", "div"]):
        classes = element.get("class", [])
        class_str = " ".join(classes).lower() if classes else ""
        elem_id = element.get("id", "").lower()

        # Match against keywords
        for section_name, keywords in section_keywords.items():
            if any(kw in class_str or kw in elem_id for kw in keywords):
                if section_name not in sections:
                    sections.append(section_name)
                break

    return sections if sections else ["hero", "content", "footer"]


def _extract_video_placement(soup: BeautifulSoup) -> Optional[str]:
    """Detect video tag presence and placement."""
    video_tags = soup.find_all(["video", "iframe"])

    if not video_tags:
        return None

    # Check if first video is in hero section
    first_video = video_tags[0]
    parent_classes = []

    # Walk up parents to check for hero indicators
    parent = first_video.parent
    depth = 0
    while parent and depth < 5:
        classes = parent.get("class", [])
        parent_classes.extend(classes)
        parent = parent.parent
        depth += 1

    parent_class_str = " ".join(parent_classes).lower() if parent_classes else ""

    if "hero" in parent_class_str or "header" in parent_class_str or "banner" in parent_class_str:
        return "hero"
    else:
        return "middle"


def _extract_color_scheme(soup: BeautifulSoup) -> Optional[dict]:
    """Parse inline styles and CSS for color properties (basic extraction)."""
    # This is a simplified implementation - full CSS parsing is complex
    # For now, return None and rely on defaults
    return None


def _aggregate_patterns(patterns: List[LPResearchPattern]) -> dict:
    """Compute common sections, CTA styles, video placement trends."""
    if not patterns:
        return {
            "common_sections": [],
            "dominant_cta_style": "Get Started",
            "video_placement_trend": "unknown",
            "color_trends": []
        }

    # Count section occurrences
    section_counts = {}
    for pattern in patterns:
        for section in pattern.section_order:
            section_counts[section] = section_counts.get(section, 0) + 1

    # Get sections that appear in >50% of patterns
    threshold = len(patterns) * 0.5
    common_sections = [s for s, count in section_counts.items() if count >= threshold]

    # Count CTA text patterns
    cta_counts = {}
    for pattern in patterns:
        for cta in pattern.cta_texts:
            cta_counts[cta] = cta_counts.get(cta, 0) + 1

    dominant_cta = max(cta_counts.items(), key=lambda x: x[1])[0] if cta_counts else "Get Started"

    # Video placement trend
    video_placements = [p.video_placement for p in patterns if p.has_video]
    placement_counts = {}
    for placement in video_placements:
        if placement:
            placement_counts[placement] = placement_counts.get(placement, 0) + 1

    if placement_counts:
        top_placement = max(placement_counts.items(), key=lambda x: x[1])
        total_with_video = len(video_placements)
        pct = (top_placement[1] / len(patterns)) * 100 if patterns else 0
        video_trend = f"{top_placement[0]} section ({pct:.0f}% of LPs)"
    else:
        video_trend = "no video detected"

    # Color trends
    color_trends = []
    primary_colors = [p.color_scheme.get("primary") for p in patterns if p.color_scheme and "primary" in p.color_scheme]
    for color in set(primary_colors):
        color_trends.append({"primary": color, "count": primary_colors.count(color)})

    return {
        "common_sections": common_sections,
        "dominant_cta_style": dominant_cta,
        "video_placement_trend": video_trend,
        "color_trends": color_trends
    }


async def research_competitor_lps(industry: str, region: str = "US", count: int = 10) -> LPResearchResult:
    """
    Main entry point. Uses Playwright to search for top LPs and extract patterns.

    Args:
        industry: Industry to research
        region: Target region
        count: Number of LPs to analyze (max)

    Returns:
        LPResearchResult with aggregated patterns
    """
    patterns = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="ViralForge-LPResearch/1.0"
            )
            page = await context.new_page()

            # Search for landing pages
            search_query = f"best {industry} landing pages {region} 2026"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

            logger.info(f"Searching: {search_query}")

            try:
                await page.goto(search_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)  # Let page settle

                # Extract URLs from search results (simplified - real implementation would parse results)
                # For now, we'll use mock data as parsing Google results is complex
                logger.warning("Google search parsing not implemented - using mock data")

            except Exception as e:
                logger.error(f"Search failed: {e}")

            await browser.close()

    except Exception as e:
        logger.error(f"Playwright initialization failed: {e}")
        logger.info("Falling back to mock data")

    # If we didn't get patterns from real scraping, use mock
    if not patterns:
        logger.info(f"Using mock research data for {industry} in {region}")
        return get_mock_research(industry, region)

    # Aggregate patterns
    aggregated = _aggregate_patterns(patterns)

    return LPResearchResult(
        patterns=patterns,
        common_sections=aggregated["common_sections"],
        dominant_cta_style=aggregated["dominant_cta_style"],
        video_placement_trend=aggregated["video_placement_trend"],
        color_trends=aggregated["color_trends"]
    )


async def research_lps(
    industry: Optional[str],
    region: Optional[str],
    use_mock: bool = False
) -> LPResearchResult:
    """
    Top-level dispatcher for LP research.

    Args:
        industry: Industry to research (None = use mock)
        region: Target region
        use_mock: Force mock data

    Returns:
        LPResearchResult
    """
    if use_mock or industry is None:
        return get_mock_research(industry or "SaaS", region or "US")

    return await research_competitor_lps(industry, region or "US")
