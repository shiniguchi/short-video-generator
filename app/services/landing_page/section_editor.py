"""AI-powered section editor for landing pages (Phase 15)."""

import re
import logging
from pathlib import Path
from typing import Optional, List, Type, Dict
from pydantic import BaseModel

from app.services.landing_page.template_builder import render_section
from app.services.landing_page.optimizer import optimize_html, validate_html
from app.services.llm_provider import get_llm_provider
from app.schemas import (
    HeroEditCopy, BenefitsEditCopy, FeaturesEditCopy, HowItWorksEditCopy,
    CtaRepeatEditCopy, FaqEditCopy, WaitlistEditCopy, FooterEditCopy
)

logger = logging.getLogger(__name__)


# Maps section name -> (schema, template context builder function)
# gallery excluded: it contains image paths, not copy
EDITABLE_SECTIONS: Dict[str, Type[BaseModel]] = {
    "hero": HeroEditCopy,
    "benefits": BenefitsEditCopy,
    "features": FeaturesEditCopy,
    "how_it_works": HowItWorksEditCopy,
    "cta_repeat": CtaRepeatEditCopy,
    "faq": FaqEditCopy,
    "waitlist": WaitlistEditCopy,
    "footer": FooterEditCopy,
}


def get_editable_sections() -> List[str]:
    """Return list of AI-editable section names (gallery excluded)."""
    return list(EDITABLE_SECTIONS.keys())


def list_sections(html: str) -> List[str]:
    """
    Extract all data-section values from HTML.
    Used for --list discovery in CLI.
    """
    pattern = re.compile(r'data-section=["\']([^"\']+)["\']')
    return pattern.findall(html)


def edit_section(
    html_path: str,
    section_name: str,
    user_prompt: str,
    product_idea: str,
    use_mock: bool = False
) -> dict:
    """
    Main entry point: AI-edit a single section in a saved LP HTML file.

    Args:
        html_path: Path to the HTML file to edit
        section_name: Section to edit (e.g., "hero", "benefits")
        user_prompt: Natural language edit instruction
        product_idea: Product context for AI (e.g., "Smart Water Bottle")
        use_mock: If True, skip LLM and return placeholder copy

    Returns:
        {"success": True, "html_path": str, "section": str, "warnings": list}
        or {"success": False, "error": str}
    """
    try:
        path = Path(html_path)
        html = path.read_text(encoding="utf-8")

        # Validate: section exists in HTML
        if f'data-section="{section_name}"' not in html:
            return {
                "success": False,
                "error": (
                    f"Section '{section_name}' not found in this LP. "
                    "Check that the HTML was generated with Phase 14 or later."
                )
            }

        # Validate: section is editable (not gallery)
        if section_name not in EDITABLE_SECTIONS:
            return {
                "success": False,
                "error": (
                    f"Section '{section_name}' is not AI-editable. "
                    "Gallery shows product images — re-run generation with different --images files."
                )
            }

        # Extract current section HTML for AI context
        current_context = _extract_section_context(html, section_name)

        # Generate new section copy via AI
        new_copy = _generate_section_copy(
            section_name, user_prompt, product_idea, current_context, use_mock
        )

        # Build template context from generated copy
        template_context = _build_template_context(section_name, new_copy)

        # Re-render section via Jinja2
        new_section_html = render_section(section_name, template_context)

        # Replace section block in HTML
        updated_html = _replace_section(html, section_name, new_section_html)

        # Re-optimize: consolidates CSS back into <head>
        final_html = optimize_html(updated_html)
        validation = validate_html(final_html)

        # Write back to file
        path.write_text(final_html, encoding="utf-8")

        logger.info(f"Edited section '{section_name}' in {html_path}")
        return {
            "success": True,
            "html_path": str(path),
            "section": section_name,
            "warnings": validation.get("warnings", [])
        }

    except Exception as e:
        logger.error(f"edit_section failed: {e}")
        return {"success": False, "error": str(e)}


def _extract_section_context(html: str, section_name: str) -> str:
    """Extract inner HTML of the target section for AI context."""
    pattern = re.compile(
        r'<section[^>]*data-section=["\']' + re.escape(section_name) + r'["\'][^>]*>(.*?)</section>',
        re.DOTALL
    )
    match = pattern.search(html)
    return match.group(1).strip() if match else ""


def _replace_section(html: str, section_name: str, new_html: str) -> str:
    """Replace entire <section data-section="NAME">...</section> block."""
    pattern = re.compile(
        r'<section[^>]*data-section=["\']' + re.escape(section_name) + r'["\'][^>]*>.*?</section>',
        re.DOTALL
    )
    return pattern.sub(new_html, html)


def _generate_section_copy(
    section_name: str,
    user_prompt: str,
    product_idea: str,
    current_context: str,
    use_mock: bool
) -> BaseModel:
    """
    Generate new copy for the target section via AI or mock.

    Args:
        section_name: Section identifier
        user_prompt: User's edit instruction
        product_idea: Product context for AI
        current_context: Current section HTML (for AI context)
        use_mock: Skip LLM and return placeholder copy

    Returns:
        Pydantic model instance with section copy fields
    """
    schema = EDITABLE_SECTIONS[section_name]

    if use_mock:
        return _get_mock_copy(section_name, schema)

    # Build prompt with product and edit context
    prompt = (
        f"Product: {product_idea}\n\n"
        f"Current section HTML:\n{current_context[:2000]}\n\n"
        f"Edit instruction: {user_prompt}\n\n"
        f"Generate updated copy for the '{section_name}' section only. "
        f"Keep the product's voice and tone. Follow the exact field structure."
    )

    system_prompt = (
        "You are a landing page copywriter. "
        "Edit only the requested section. "
        "Preserve the product's voice and tone. "
        "Write concise, benefit-driven copy."
    )

    llm = get_llm_provider()
    logger.info(f"Generating section copy for '{section_name}': {user_prompt}")

    return llm.generate_structured(
        prompt=prompt,
        schema=schema,
        system_prompt=system_prompt,
        temperature=0.8
    )


def _get_mock_copy(section_name: str, schema: Type[BaseModel]) -> BaseModel:
    """Return placeholder copy for mock mode (no LLM call)."""
    mock_data = {
        "hero": {
            "headline": "The Smarter Way to Get Started",
            "subheadline": "Save hours every week with the tool that actually works for your workflow.",
            "cta_text": "Get Early Access",
            "trust_text": "No spam. Unsubscribe anytime."
        },
        "benefits": {
            "benefits": [
                {"title": "Works Instantly", "description": "Zero setup required. Start in under 2 minutes.", "icon_emoji": "⚡"},
                {"title": "Built to Last", "description": "Premium quality designed for daily use.", "icon_emoji": "🛡️"},
                {"title": "100% Free Trial", "description": "Try everything free for 30 days. No credit card.", "icon_emoji": "🎯"},
            ]
        },
        "features": {
            "features": [
                {"title": "Smart Design", "description": "Adapts to your needs throughout the day.", "stat": "24/7"},
                {"title": "Fast Setup", "description": "Ready to use in minutes, not hours.", "stat": "2 min"},
            ]
        },
        "how_it_works": {
            "how_it_works": [
                {"step_number": 1, "title": "Sign Up Free", "description": "Create your account in under 60 seconds."},
                {"step_number": 2, "title": "Set It Up", "description": "Follow the simple onboarding flow."},
                {"step_number": 3, "title": "Start Using It", "description": "You're ready to go immediately."},
            ]
        },
        "cta_repeat": {
            "headline": "Ready to Get Started?",
            "subtext": "Join thousands of users who already made the switch.",
            "cta_text": "Join the Waitlist",
            "urgency_text": "Limited early access — first 500 spots only."
        },
        "faq": {
            "faq_items": [
                {"question": "When does it launch?", "answer": "We're targeting Q2 2026. Waitlist members get priority access."},
                {"question": "Is the waitlist free?", "answer": "Yes, completely free. No credit card required."},
            ]
        },
        "waitlist": {
            "cta_text": "Reserve My Spot",
            "social_proof_text": "Join 2,000+ early adopters",
            "trust_text": "No spam, ever. Unsubscribe anytime."
        },
        "footer": {
            "footer_text": "© 2026 Product. All rights reserved."
        },
    }
    return schema(**mock_data[section_name])


def _build_template_context(section_name: str, copy: BaseModel) -> dict:
    """
    Convert Pydantic model fields into the dict format render_section() expects.
    Matches section_contexts in template_builder.py.
    """
    data = copy.model_dump()

    if section_name == "hero":
        # video_url and hero_image are None for copy-only edits
        return {
            "headline": data["headline"],
            "subheadline": data["subheadline"],
            "cta_text": data["cta_text"],
            "trust_text": data.get("trust_text"),
            "video_url": None,
            "hero_image": None,
        }
    elif section_name == "benefits":
        return {
            "heading": "Why This Product?",
            "benefits": data["benefits"],
        }
    elif section_name == "features":
        return {
            "features": data["features"],
            "product_name": "this product",
        }
    elif section_name == "how_it_works":
        return {
            "steps": data["how_it_works"],
        }
    elif section_name == "cta_repeat":
        return {
            "headline": data["headline"],
            "subtext": data["subtext"],
            "cta_text": data["cta_text"],
            "urgency_text": data.get("urgency_text"),
        }
    elif section_name == "faq":
        return {
            "faq_items": data["faq_items"],
        }
    elif section_name == "waitlist":
        return {
            "cta_text": data["cta_text"],
            "social_proof_text": data["social_proof_text"],
            "trust_text": data.get("trust_text"),
        }
    elif section_name == "footer":
        return {
            "footer_text": data["footer_text"],
        }
    else:
        return data
