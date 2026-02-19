"""End-to-end landing page generation orchestrator."""

import asyncio
import logging
import os
from pathlib import Path
from uuid import uuid4
from typing import Optional

from app.schemas import LandingPageRequest, LandingPageResult, ColorScheme
from app.config import get_settings
from app.services.landing_page.research import research_lps
from app.services.landing_page.copy_generator import generate_copy
from app.services.landing_page.template_builder import build_landing_page
from app.services.landing_page.color_extractor import get_color_scheme
from app.services.landing_page.optimizer import optimize_html, validate_html, get_html_size_kb

logger = logging.getLogger(__name__)


async def generate_landing_page(request: LandingPageRequest, use_mock: bool = False) -> LandingPageResult:
    """
    Generate a complete landing page through the full pipeline.

    Pipeline Steps:
    1. Research: Scrape competitor LPs for design patterns
    2. Color: Extract/derive color scheme
    3. Copy: Generate AI-written copy using PAS formula
    4. Build: Render HTML from templates
    5. Optimize: Minify CSS and validate
    6. Save: Write to output directory

    Args:
        request: LandingPageRequest with product idea, audience, preferences
        use_mock: If True, use mock data for all AI/scraping steps

    Returns:
        LandingPageResult with path to generated HTML and metadata
    """
    import time
    pipeline_start = time.time()

    settings = get_settings()

    # Generate run ID
    run_id = uuid4().hex[:8]
    logger.info(f"Starting LP generation (run_id={run_id}) for: {request.product_idea}")

    # STEP 1: Research
    step_start = time.time()
    logger.info("STEP 1/6: Research competitor landing pages")
    research_result = await research_lps(
        industry=request.industry,
        region=request.region or "US",
        use_mock=use_mock
    )
    logger.info(f"Research complete: {len(research_result.patterns)} patterns analyzed ({time.time() - step_start:.1f}s)")

    # STEP 2: Color Scheme
    step_start = time.time()
    logger.info("STEP 2/6: Generate color scheme")
    color_preference = request.color_preference or "research"
    color_scheme = get_color_scheme(
        preference=color_preference,
        image_path=request.hero_image_path,
        research_patterns=research_result.patterns,
        preset_name=request.color_preset
    )
    logger.info(f"Color scheme: {color_scheme.source} (primary={color_scheme.primary}) ({time.time() - step_start:.1f}s)")

    # STEP 3: Copy Generation
    step_start = time.time()
    logger.info("STEP 3/6: Generate landing page copy")
    copy = generate_copy(
        product_idea=request.product_idea,
        target_audience=request.target_audience,
        research_result=research_result,
        use_mock=use_mock
    )
    logger.info(f"Copy generated: '{copy.headline}' ({time.time() - step_start:.1f}s)")

    # STEP 4: Build HTML
    step_start = time.time()
    logger.info("STEP 4/6: Build landing page HTML")

    # Resolve asset paths relative to the output HTML location
    output_dir = Path(settings.output_dir) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "landing-page.html"

    video_url_for_template = None
    hero_image_for_template = None
    product_images_for_template = []

    html_parent = html_path.parent.resolve()

    if request.video_path:
        abs_video = Path(request.video_path).resolve()
        video_url_for_template = os.path.relpath(abs_video, html_parent)
    if request.hero_image_path:
        abs_image = Path(request.hero_image_path).resolve()
        hero_image_for_template = os.path.relpath(abs_image, html_parent)
    if request.product_images:
        for img_path in request.product_images:
            abs_img = Path(img_path).resolve()
            product_images_for_template.append(os.path.relpath(abs_img, html_parent))
        logger.info(f"Resolved {len(product_images_for_template)} product images for LP")

    raw_html = build_landing_page(
        copy=copy,
        color_scheme=color_scheme,
        video_url=video_url_for_template,
        hero_image=hero_image_for_template,
        product_images=product_images_for_template,
        lp_source=run_id
    )
    logger.info(f"HTML built: {len(raw_html)} chars ({time.time() - step_start:.1f}s)")

    # STEP 5: Optimize
    step_start = time.time()
    logger.info("STEP 5/6: Optimize and validate HTML")
    optimized_html = optimize_html(raw_html)
    validation = validate_html(optimized_html)
    html_size = get_html_size_kb(optimized_html)

    if not validation["valid"]:
        logger.warning(f"HTML validation warnings: {validation['warnings']}")

    logger.info(f"Optimization complete: {html_size:.1f} KB ({time.time() - step_start:.1f}s)")

    # STEP 6: Save
    step_start = time.time()
    logger.info("STEP 6/6: Save to output directory")
    html_path.write_text(optimized_html, encoding='utf-8')
    logger.info(f"Saved to: {html_path} ({time.time() - step_start:.1f}s)")

    # Extract actual section names from generated HTML
    import re
    actual_sections = re.findall(r'data-section="([^"]+)"', optimized_html)

    result = LandingPageResult(
        html_path=str(html_path),
        product_idea=request.product_idea,
        color_scheme=color_scheme,
        sections=actual_sections
    )

    total_time = time.time() - pipeline_start
    logger.info(f"LP generation complete! Total time: {total_time:.1f}s")

    return result


def generate_landing_page_sync(request: LandingPageRequest, use_mock: bool = False) -> LandingPageResult:
    """
    Synchronous wrapper for generate_landing_page.

    Args:
        request: LandingPageRequest
        use_mock: If True, use mock data

    Returns:
        LandingPageResult
    """
    return asyncio.run(generate_landing_page(request, use_mock))
