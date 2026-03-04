"""Landing page generation module."""

from app.services.landing_page.generator import generate_landing_page, generate_landing_page_sync
from app.schemas import LandingPageRequest

__all__ = [
    "generate_landing_page",
    "generate_landing_page_sync",
    "LandingPageRequest",
]
