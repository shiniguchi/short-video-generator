"""Jinja2 template rendering engine for landing pages."""

import logging
from pathlib import Path
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.schemas import LandingPageCopy, ColorScheme

logger = logging.getLogger(__name__)

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


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


def build_landing_page(
    copy: LandingPageCopy,
    color_scheme: ColorScheme,
    video_url: Optional[str] = None,
    hero_image: Optional[str] = None,
    sections_order: Optional[List[str]] = None
) -> str:
    """
    Build complete landing page HTML from copy and design elements.

    Args:
        copy: LandingPageCopy with all content
        color_scheme: ColorScheme with colors
        video_url: Optional URL to hero video
        hero_image: Optional URL to hero image (fallback or poster)
        sections_order: Custom section order (default: ["hero", "benefits", "waitlist", "footer"])

    Returns:
        Complete HTML string ready to save as .html file
    """
    # Default section order (lean)
    if sections_order is None:
        sections_order = ["hero", "benefits", "waitlist", "footer"]

    logger.info(f"Building landing page with sections: {sections_order}")

    # Prepare section contexts
    section_contexts = {
        "hero": {
            "headline": copy.headline,
            "subheadline": copy.subheadline,
            "cta_text": copy.cta_text,
            "video_url": video_url,
            "hero_image": hero_image
        },
        "benefits": {
            "benefits": copy.benefits
        },
        "waitlist": {
            "cta_text": copy.cta_text,
            "social_proof_text": copy.social_proof_text
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
    # We just need to define the CSS custom properties
    inline_css = ""  # Section styles are already in templates

    # Render base template
    env = _create_jinja_env()
    base_template = env.get_template("base.html.j2")

    html = base_template.render(
        meta_title=copy.meta_title,
        meta_description=copy.meta_description,
        color_primary=color_scheme.primary,
        color_secondary=color_scheme.secondary,
        color_accent=color_scheme.accent,
        color_bg=color_scheme.background,
        color_text=color_scheme.text,
        inline_css=inline_css,
        sections=rendered_sections
    )

    logger.info(f"Generated landing page HTML: {len(html)} characters")
    return html
