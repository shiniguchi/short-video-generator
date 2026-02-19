"""Standalone CLI for AI-powered LP section editing.

Edit a single section of a generated landing page using natural language prompts.
"""
import sys
import os
import json
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


def _read_sidecar(html_path: str) -> dict:
    """Read landing-page.json sidecar if it exists."""
    sidecar_path = Path(html_path).parent / "landing-page.json"
    if sidecar_path.exists():
        return json.loads(sidecar_path.read_text(encoding='utf-8'))
    return {}


def _write_sidecar(html_path: str, product_idea: str) -> None:
    """Write landing-page.json sidecar on first edit if it doesn't exist yet."""
    sidecar_path = Path(html_path).parent / "landing-page.json"
    if not sidecar_path.exists():
        sidecar_path.write_text(
            json.dumps({"product_idea": product_idea}, indent=2),
            encoding='utf-8'
        )
        logger.info(f"Wrote sidecar: {sidecar_path}")


def main():
    parser = argparse.ArgumentParser(
        description="AI-edit a single section of a generated landing page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all sections in an LP
  python scripts/edit_lp_section.py --lp output/abc123/landing-page.html --list

  # Edit hero section (mock mode, first time — writes sidecar)
  python scripts/edit_lp_section.py --lp output/abc123/landing-page.html --section hero --prompt "make headline shorter" --product "Smart Water Bottle" --mock

  # Subsequent edits — --product not needed (reads from sidecar)
  python scripts/edit_lp_section.py --lp output/abc123/landing-page.html --section benefits --prompt "add more urgency" --mock
        """
    )

    parser.add_argument(
        '--lp',
        required=True,
        help='Path to the landing-page.html file to edit'
    )
    parser.add_argument(
        '--section',
        choices=['hero', 'benefits', 'features', 'how_it_works', 'cta_repeat', 'faq', 'waitlist', 'footer'],
        help='Section to edit (not required for --list)'
    )
    parser.add_argument(
        '--prompt',
        help='Edit instruction (e.g., "make headline shorter and more urgent")'
    )
    parser.add_argument(
        '--product',
        help='Product idea for AI context. Falls back to sidecar file if not provided.'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all sections in the LP and exit'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock AI (no API key needed)'
    )
    parser.add_argument(
        '--no-open',
        action='store_true',
        help='Skip opening browser after edit'
    )

    args = parser.parse_args()

    # Import here to avoid loading heavy modules during --help
    from app.services.landing_page.section_editor import (
        edit_section, list_sections, get_editable_sections
    )

    # Resolve HTML path
    html_path = args.lp
    if not Path(html_path).exists():
        print(f"Error: LP file not found: {html_path}")
        sys.exit(1)

    # --list mode: show sections and exit
    if args.list:
        html = Path(html_path).read_text(encoding='utf-8')
        sections = list_sections(html)
        editable = get_editable_sections()

        print("=" * 60)
        print(f"SECTIONS IN: {html_path}")
        print("=" * 60)
        for section in sections:
            status = "editable" if section in editable else "not editable (gallery)"
            print(f"  {section:<20} [{status}]")
        print()
        print(f"Editable sections: {', '.join(editable)}")
        return

    # Edit mode: require --section and --prompt
    if not args.section:
        parser.error("--section is required for editing (or use --list to view sections)")
    if not args.prompt:
        parser.error("--prompt is required for editing")

    # Resolve product_idea: --product flag > sidecar file > error
    product_idea = args.product
    if not product_idea:
        sidecar = _read_sidecar(html_path)
        product_idea = sidecar.get("product_idea")
        if not product_idea:
            print("Error: --product required on first edit (no sidecar file found).")
            print(f"Tip: Run with --product 'Your Product Name' to save it for future edits.")
            sys.exit(1)
        logger.info("Using product_idea from sidecar file")

    # Display configuration
    print("=" * 60)
    print("LP SECTION EDITOR")
    print("=" * 60)
    print(f"LP: {html_path}")
    print(f"Section: {args.section}")
    print(f"Prompt: {args.prompt}")
    print(f"Product: {product_idea}")
    print(f"Mock Mode: {args.mock}")
    print()

    # Perform the edit
    result = edit_section(html_path, args.section, args.prompt, product_idea, use_mock=args.mock)

    if not result["success"]:
        print("=" * 60)
        print("EDIT FAILED")
        print("=" * 60)
        print(f"Error: {result['error']}")
        sys.exit(1)

    # Write sidecar on first edit if --product was provided
    if args.product:
        _write_sidecar(html_path, product_idea)

    # Display result
    warnings = result.get("warnings", [])
    print("=" * 60)
    print("EDIT COMPLETE!")
    print("=" * 60)
    print(f"Section: {result['section']}")
    print(f"Warnings: {', '.join(warnings) if warnings else 'none'}")
    print(f"To view: open {result['html_path']}")
    print()

    # Open browser unless --no-open
    if not args.no_open:
        abs_path = Path(result['html_path']).resolve()
        file_url = f"file://{abs_path}"
        print(f"Opening in browser: {file_url}")
        webbrowser.open(file_url)
    else:
        print("Skipped browser preview (--no-open)")


if __name__ == "__main__":
    main()
