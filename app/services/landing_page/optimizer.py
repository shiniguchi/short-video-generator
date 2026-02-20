"""HTML and CSS optimization for landing pages."""

import re
import logging
from typing import Dict

try:
    import rcssmin
except ImportError:
    rcssmin = None

logger = logging.getLogger(__name__)


def optimize_html(html: str) -> str:
    """
    Optimize HTML by extracting and minifying all CSS into a single style block.

    Args:
        html: Raw HTML string with multiple <style> tags

    Returns:
        Optimized HTML with single minified <style> tag in <head>
    """
    # Extract all <style> blocks
    style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL | re.IGNORECASE)
    style_matches = style_pattern.findall(html)

    if not style_matches:
        logger.warning("No <style> blocks found in HTML")
        return html

    # Concatenate all CSS
    combined_css = "\n".join(style_matches)

    # Minify CSS if rcssmin available
    if rcssmin:
        minified_css = rcssmin.cssmin(combined_css)
        logger.info(f"CSS minified: {len(combined_css)} -> {len(minified_css)} chars ({(1 - len(minified_css)/len(combined_css))*100:.1f}% reduction)")
    else:
        logger.warning("rcssmin not available, skipping CSS minification")
        minified_css = combined_css

    # Remove all existing <style> blocks
    html_no_styles = style_pattern.sub('', html)

    # Insert single minified <style> block before </head> (after meta tags)
    head_close_pattern = re.compile(r'(</head>)', re.IGNORECASE)
    optimized_html = head_close_pattern.sub(f'<style>{minified_css}</style>\n\\1', html_no_styles, count=1)

    return optimized_html


def validate_html(html: str) -> Dict[str, any]:
    """
    Validate HTML for critical landing page elements.

    Args:
        html: HTML string to validate

    Returns:
        Dict with {valid: bool, warnings: list[str]}
    """
    warnings = []

    # Check for viewport meta
    if 'viewport' not in html.lower():
        warnings.append("Missing viewport meta tag for mobile responsiveness")

    # Check for at least one h1
    if '<h1' not in html.lower():
        warnings.append("Missing h1 tag (important for SEO and hierarchy)")

    # Check for form element
    if '<form' not in html.lower():
        warnings.append("Missing form element (expected for waitlist signup)")

    # Check for external stylesheets (should be none for single-file HTML)
    if re.search(r'<link[^>]+rel=["\']stylesheet["\']', html, re.IGNORECASE):
        warnings.append("External stylesheet detected - LP should be self-contained")

    valid = len(warnings) == 0

    return {
        "valid": valid,
        "warnings": warnings
    }


def get_html_size_kb(html: str) -> float:
    """
    Calculate HTML file size in KB.

    Args:
        html: HTML string

    Returns:
        Size in kilobytes (float)
    """
    size_bytes = len(html.encode('utf-8'))
    size_kb = size_bytes / 1024

    if size_kb > 100:
        logger.warning(f"HTML size is {size_kb:.1f} KB (> 100 KB threshold)")

    return size_kb


# Beacon script template — uses %s to avoid conflicts with JS curly braces
BEACON_TEMPLATE = """<script>
(function(){
  var w="%s";var id="%s";
  if(!w)return;
  var b=function(e,d){navigator.sendBeacon(w+"/track",JSON.stringify(d));};
  b("pageview",{lp_id:id,event:"pageview",referrer:document.referrer||"direct"});
  var f=document.querySelector("form");
  if(f)f.addEventListener("submit",function(){b("form_submit",{lp_id:id,event:"form_submit"});});
})();
</script>"""


def inject_analytics_beacon(html: str, worker_url: str, lp_id: str) -> str:
    """Inject analytics beacon script before </body>. Call AFTER optimize_html()."""
    if not worker_url:
        return html  # No tracking in local dev
    beacon = BEACON_TEMPLATE % (worker_url.rstrip("/"), lp_id)
    return html.replace("</body>", beacon + "</body>", 1)
