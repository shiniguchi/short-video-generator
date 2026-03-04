"""Jinja2 template rendering engine for landing pages."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.schemas import LandingPageCopy, ColorScheme
from app.services.landing_page.contrast import ensure_contrast

logger = logging.getLogger(__name__)

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
THEMES_DIR = TEMPLATES_DIR / "themes"
PRESETS_PATH = TEMPLATES_DIR / "presets" / "templates.json"


def _create_jinja_env() -> Environment:
    """Create and configure Jinja2 environment."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(['html', 'xml', 'j2'])
    )


def render_section(section_name: str, context: dict) -> str:
    """
    Render a single section template.

    Args:
        section_name: Name of the section (e.g., "hero", "benefits")
        context: Template variables

    Returns:
        Rendered HTML string for the section

    Raises:
        TemplateNotFound: If section template doesn't exist
    """
    env = _create_jinja_env()
    template_path = f"sections/{section_name}.html.j2"
    template = env.get_template(template_path)

    logger.debug(f"Rendering section: {section_name}")
    return template.render(**context)


def get_section_list() -> List[str]:
    """
    Get list of available section names.

    Returns:
        List of section names (without .html.j2 extension)
    """
    sections_dir = TEMPLATES_DIR / "sections"
    if not sections_dir.exists():
        return []

    sections = []
    for template_file in sections_dir.glob("*.html.j2"):
        section_name = template_file.stem
        sections.append(section_name)

    return sorted(sections)


def get_available_templates() -> List[Dict[str, Any]]:
    """Return list of template presets for the UI picker."""
    if not PRESETS_PATH.exists():
        return []
    with open(PRESETS_PATH, "r") as f:
        return json.load(f)


def _load_template_config(template_key: str) -> Optional[Dict[str, Any]]:
    """Load a single template config by key from presets JSON."""
    templates = get_available_templates()
    for t in templates:
        if t["key"] == template_key:
            return t
    return None


def _load_theme_css(template_key: str) -> str:
    """Read theme CSS file for the given template key."""
    css_path = THEMES_DIR / f"{template_key}.css"
    if not css_path.exists():
        logger.warning(f"Theme CSS not found: {css_path}")
        return ""
    return css_path.read_text(encoding="utf-8")


def build_landing_page(
    copy: LandingPageCopy,
    color_scheme: ColorScheme,
    video_url: Optional[str] = None,
    hero_image: Optional[str] = None,
    product_images: Optional[List[str]] = None,
    sections_order: Optional[List[str]] = None,
    lp_source: Optional[str] = None,
    template_key: Optional[str] = None,
    section_images: Optional[Dict[str, List[str]]] = None,
) -> str:
    """
    Build complete landing page HTML from copy and design elements.

    Args:
        copy: LandingPageCopy with all content
        color_scheme: ColorScheme with colors
        video_url: Optional URL to hero video
        hero_image: Optional URL to hero image (fallback or poster)
        product_images: Optional list of product image paths for visual sections
        sections_order: Custom section order

    Returns:
        Complete HTML string ready to save as .html file
    """
    # Default section order — high-converting LP structure
    if sections_order is None:
        sections_order = ["hero", "benefits", "gallery", "features", "how_it_works", "cta_repeat", "faq", "footer"]

    logger.info(f"Building landing page with sections: {sections_order}")

    # Contrast guardrails — darken primary/secondary if white text unreadable
    safe_primary = ensure_contrast(color_scheme.primary, "primary")
    safe_secondary = ensure_contrast(color_scheme.secondary, "secondary")

    # Extract product name for sections that need it
    product_name = copy.meta_title.split("—")[0].split("-")[0].strip() if copy.meta_title else "this product"

    # Distribute images — prefer AI-generated section images over pool
    imgs = product_images or []
    benefits_count = len(copy.benefits) if copy.benefits else 0
    steps_count = len(copy.how_it_works) if copy.how_it_works else 0

    if section_images and "benefits" in section_images:
        benefits_imgs = section_images["benefits"]
    else:
        benefits_imgs = imgs[:benefits_count]

    if section_images and "how_it_works" in section_images:
        hiw_imgs = section_images["how_it_works"]
    else:
        hiw_imgs = imgs[benefits_count:benefits_count + steps_count]

    # Gallery: deduplicated union of section images + pool (up to 6)
    all_unique = list(dict.fromkeys(
        (section_images.get("benefits", []) if section_images else [])
        + (section_images.get("how_it_works", []) if section_images else [])
        + imgs
    ))
    gallery_imgs = all_unique[:6]

    # Inject images into benefits
    benefits_with_images = []
    for i, benefit in enumerate(copy.benefits or []):
        b = dict(benefit)
        if i < len(benefits_imgs):
            b["image"] = benefits_imgs[i]
        benefits_with_images.append(b)

    # Inject images into how_it_works steps
    steps_with_images = []
    for i, step in enumerate(copy.how_it_works or []):
        s = dict(step)
        if i < len(hiw_imgs):
            s["image"] = hiw_imgs[i]
        steps_with_images.append(s)

    # Skip gallery section if no gallery images
    if not gallery_imgs and "gallery" in sections_order:
        sections_order = [s for s in sections_order if s != "gallery"]

    # Prepare section contexts
    section_contexts = {
        "hero": {
            "headline": copy.headline,
            "subheadline": copy.subheadline,
            "cta_text": copy.cta_text,
            "trust_text": copy.trust_text,
            "video_url": video_url,
            "hero_image": hero_image
        },
        "benefits": {
            "heading": f"Why {product_name}?",
            "benefits": benefits_with_images
        },
        "gallery": {
            "images": gallery_imgs,
            "product_name": product_name,
            "heading": f"See {product_name} in Action"
        },
        "features": {
            "features": copy.features or [],
            "product_name": product_name
        },
        "how_it_works": {
            "steps": steps_with_images
        },
        "cta_repeat": {
            "headline": "Ready to Get Started?",
            "subtext": copy.subheadline,
            "cta_text": copy.cta_text,
            "urgency_text": copy.urgency_text
        },
        "faq": {
            "faq_items": copy.faq or []
        },
        "waitlist": {
            "cta_text": copy.cta_text,
            "social_proof_text": copy.social_proof_text,
            "trust_text": copy.trust_text
        },
        "footer": {
            "footer_text": copy.footer_text
        }
    }

    # Render each section
    rendered_sections = []
    for section_name in sections_order:
        if section_name in section_contexts:
            context = section_contexts[section_name]
            rendered_html = render_section(section_name, context)
            rendered_sections.append(rendered_html)
        else:
            logger.warning(f"Section '{section_name}' not found in contexts, skipping")

    # Build CSS with color variables
    # Note: Individual section CSS is already embedded in each section template
    inline_css = ""  # Section styles are already in templates

    env = _create_jinja_env()

    # Choose themed or plain base template
    tmpl_config = _load_template_config(template_key) if template_key else None
    if tmpl_config:
        theme_css = _load_theme_css(template_key)
        base_template = env.get_template("base_themed.html.j2")
        html = base_template.render(
            meta_title=copy.meta_title,
            meta_description=copy.meta_description,
            color_primary=safe_primary,
            color_secondary=safe_secondary,
            color_accent=color_scheme.accent,
            color_bg=color_scheme.background,
            color_text=color_scheme.text,
            inline_css=inline_css,
            sections=rendered_sections,
            lp_source=lp_source or "",
            fonts_url=tmpl_config["fonts_url"],
            heading_font=tmpl_config["heading_font"],
            body_font=tmpl_config["body_font"],
            theme_css=theme_css,
            cta_text=copy.cta_text,
        )
    else:
        base_template = env.get_template("base.html.j2")
        html = base_template.render(
            meta_title=copy.meta_title,
            meta_description=copy.meta_description,
            color_primary=safe_primary,
            color_secondary=safe_secondary,
            color_accent=color_scheme.accent,
            color_bg=color_scheme.background,
            color_text=color_scheme.text,
            inline_css=inline_css,
            sections=rendered_sections,
            lp_source=lp_source or "",
            cta_text=copy.cta_text,
        )

    logger.info(f"Generated landing page HTML: {len(html)} characters")
    return html
