"""Standalone CLI for landing page generation.

Generates a complete, production-ready landing page from product idea and audience.
"""
import sys
import os
import logging
import argparse
import webbrowser
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DATABASE_URL for local SQLite (no PostgreSQL needed)
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///test_pipeline.db'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a complete landing page from product idea",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (mock mode)
  python scripts/generate_landing_page.py --idea "AI sleep tracker" --audience "Health-conscious millennials" --mock

  # With video and custom colors
  python scripts/generate_landing_page.py --idea "My Product" --audience "Target Users" --video output/run123/video.mp4 --color extract --image hero.jpg

  # Use preset palette
  python scripts/generate_landing_page.py --idea "SaaS Tool" --audience "Developers" --color preset --preset "ocean"
        """
    )

    # Required arguments
    parser.add_argument(
        '--idea',
        required=True,
        help='Product idea or name (e.g., "AI-powered sleep tracker")'
    )
    parser.add_argument(
        '--audience',
        required=True,
        help='Target audience (e.g., "Health-conscious millennials")'
    )

    # Optional arguments
    parser.add_argument(
        '--industry',
        help='Industry for LP research (e.g., "SaaS", "Health", "E-commerce")'
    )
    parser.add_argument(
        '--region',
        default='US',
        help='Target region for research (default: US)'
    )
    parser.add_argument(
        '--color',
        choices=['extract', 'research', 'preset'],
        default='research',
        help='Color scheme mode: extract (from image), research (from competitor LPs), preset (predefined palette). Default: research'
    )
    parser.add_argument(
        '--preset',
        help='Preset palette name (only used when --color=preset)'
    )
    parser.add_argument(
        '--video',
        help='Path to video file for hero section'
    )
    parser.add_argument(
        '--image',
        help='Path to hero image (used as fallback or for color extraction)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock data for all AI/scraping calls (faster, no API keys needed)'
    )
    parser.add_argument(
        '--no-open',
        action='store_true',
        help='Skip opening browser after generation'
    )

    args = parser.parse_args()

    # Validation
    if args.color == 'preset' and not args.preset:
        parser.error("--preset required when --color=preset")

    if args.color == 'extract' and not args.image:
        parser.error("--image required when --color=extract")

    # Import here to avoid loading heavy modules during --help
    from app.services.landing_page import generate_landing_page_sync, LandingPageRequest

    # Build request
    request = LandingPageRequest(
        product_idea=args.idea,
        target_audience=args.audience,
        industry=args.industry,
        region=args.region,
        color_preference=args.color,
        color_preset=args.preset,
        video_path=args.video,
        hero_image_path=args.image
    )

    # Display configuration
    print("=" * 60)
    print("LANDING PAGE GENERATOR")
    print("=" * 60)
    print(f"Product: {args.idea}")
    print(f"Audience: {args.audience}")
    print(f"Industry: {args.industry or 'Not specified (will use mock)'}")
    print(f"Region: {args.region}")
    print(f"Color Mode: {args.color}")
    if args.preset:
        print(f"Color Preset: {args.preset}")
    if args.video:
        print(f"Video: {args.video}")
    if args.image:
        print(f"Image: {args.image}")
    print(f"Mock Mode: {args.mock}")
    print()

    # Generate landing page
    try:
        result = generate_landing_page_sync(request, use_mock=args.mock)

        print("=" * 60)
        print("GENERATION COMPLETE!")
        print("=" * 60)
        print(f"Output: {result.html_path}")

        # Get file size
        html_path = Path(result.html_path)
        size_kb = html_path.stat().st_size / 1024
        print(f"Size: {size_kb:.1f} KB")

        print(f"Color Scheme: {result.color_scheme.source}")
        print(f"  Primary: {result.color_scheme.primary}")
        print(f"  Secondary: {result.color_scheme.secondary}")
        print(f"  Accent: {result.color_scheme.accent}")
        print(f"Sections: {', '.join(result.sections)}")
        print()

        # Open in browser
        if not args.no_open:
            abs_path = html_path.resolve()
            file_url = f"file://{abs_path}"
            print(f"Opening in browser: {file_url}")
            webbrowser.open(file_url)
        else:
            print("Skipped browser preview (--no-open)")

        print()
        print(f"To view: open {result.html_path}")

    except Exception as e:
        logger.error(f"Landing page generation failed: {e}", exc_info=True)
        print()
        print("=" * 60)
        print("GENERATION FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
