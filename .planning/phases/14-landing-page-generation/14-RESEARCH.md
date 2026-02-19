# Phase 14: Landing Page Generation - Research

**Researched:** 2026-02-19
**Domain:** AI-driven landing page generation, single-file HTML, programmatic LP research, copy formulas
**Confidence:** MEDIUM-HIGH

## Summary

Phase 14 generates production-ready single-file HTML landing pages from product ideas, with AI-written copy, embedded video, and waitlist forms. The LP is research-driven—AI analyzes top-performing LPs in the same space to inform design and copy decisions.

The core technical stack combines **Playwright** for headless browser automation to research competitor LPs, **Claude 4.6 Opus/Sonnet** for copy generation using proven formulas (PAS, AIDA, BAB), and **FastAPI + Jinja2** for HTML template generation. Color extraction uses **colorgram.py** or **Pylette**, with **rcssmin** for CSS optimization. The output is a single self-contained HTML file with inline CSS, mobile-first responsive design, and honeypot spam prevention.

Key architectural pattern: **Research → Extract Patterns → Generate Copy → Assemble HTML → Optimize**. The LP is built as modular components (hero, benefits, waitlist, footer) to enable Phase 15's AI Section Editing capabilities.

**Primary recommendation:** Use Playwright to scrape top 10 LPs → extract design patterns with BeautifulSoup → prompt Claude with research context + copywriting formula → generate Jinja2 template → inline CSS with rcssmin → output single HTML file.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**LP visual style & structure:**
- **Dynamic, research-driven design**: AI researches top 10 performing LPs similar to the product idea (based on industry + target region) and designs the LP based on patterns found
- User provides industry and target region as inputs to guide research
- Heavily reuses images and videos produced by the existing marketing video pipeline
- **Default sections (lean)**: Hero (video + headline + CTA) + 3 benefits + waitlist form + footer
- Sections are built as modular components so Phase 15 can reorder/add/subtract them
- **Mobile-first** responsive design
- **Color scheme is user-configurable** with 3 options:
  - Option 1: Extract colors from product images/video frames
  - Option 2 (default): Research-driven — follow top-performing LP color patterns
  - Option 3: User picks from preset palettes

**Copy generation strategy:**
- **User inputs**: Product idea + target audience (both required)
- Industry, region, color preference are optional inputs
- **Tone**: Always conversational — friendly, direct, second-person ("you")
- **Research-informed copy**: AI analyzes top LP copy patterns in the same space, uses similar hooks/angles/formulas to generate copy
- **Social proof**: Implied proof only — soft signals like "Join X others" or "Built by the team behind..." — no fake testimonials or fabricated stats

**Video embed & hero layout:**
- **Video placement**: Claude's discretion, informed by research — follow what top-performing LPs do; research conversion data on placement if available
- **Autoplay behavior**: Autoplay muted + loop (pending research confirmation of best practice)
- **No GIFs** — too slow. Performance is a hard constraint
- **No-video fallback**: Use hero image from product images if video isn't available — LP still looks complete
- **Asset distribution across sections**: Research-driven — Claude investigates optimal asset placement for conversion and decides

**Generation interface & flow:**
- **Invocation**: Standalone CLI command OR triggered as last step of existing video pipeline — both paths work
- **Standalone required inputs**: Product idea + target audience
- **Standalone optional inputs**: Industry, region, color preference
- **Pipeline mode**: Automatically reuses product idea, audience, and assets from current pipeline run — zero extra input
- **Preview**: Generate then open in browser for preview — user confirms or regenerates
- **Output location**: Saved in pipeline output directory alongside video: `output/{run-id}/landing-page.html`

### Claude's Discretion

- Exact section spacing, typography, and visual polish
- Video placement decision (informed by LP research)
- Asset distribution across sections (informed by conversion research)
- Autoplay behavior (research best practice, default to muted loop)
- Loading performance optimizations
- Error state handling during generation

### Deferred Ideas (OUT OF SCOPE)

- Module reordering, adding, and subtracting sections — Phase 15 (AI Section Editing)
- Waitlist form backend processing — Phase 16 (Waitlist Collection)

</user_constraints>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Playwright** | 1.48+ | Headless browser automation for LP research | Industry standard for dynamic JS-heavy site scraping in 2026; auto-waits for elements, supports all major browsers, maintained by Microsoft |
| **BeautifulSoup4** | 4.12+ | HTML parsing after Playwright extraction | 10x faster parsing than Playwright's built-in; robust API; standard for HTML manipulation |
| **Claude 4.6 Opus/Sonnet** | Latest | Copy generation with proven formulas | Top-tier for copywriting tasks; follows instructions precisely; generates persuasive, natural-sounding text |
| **FastAPI + Jinja2** | 0.115+ / 3.1+ | HTML template generation | FastAPI official templating solution; separates logic from presentation; supports inheritance and composition |
| **colorgram.py** | 1.2+ | Color palette extraction from images/video | Simple API; fast; extracts dominant colors with RGB values |
| **rcssmin** | 1.1+ | CSS minification | Designed for runtime use; fastest pure-Python CSS minifier; simple API |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Pylette** | 0.3+ | Advanced color palette extraction | If need HSV colorspace or JSON export; richer metadata than colorgram |
| **python-dotenv** | 1.0+ | Environment variable management | Store API keys (Claude, web scraping services) securely |
| **opencv-python** | 4.10+ | Video frame extraction for color analysis | If extracting colors from video frames instead of images |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright | Selenium | Selenium is older, slower, more fragile; Playwright has better async support and auto-waiting |
| BeautifulSoup | lxml.html | lxml is faster but less forgiving with malformed HTML; BS4's lenient parsing is better for scraping wild web content |
| Claude 4.6 | Mistral Large | Mistral Large is excellent for copywriting but Claude has better instruction-following for structured output |
| colorgram.py | Pillow's ImagePalette | colorgram provides cleaner API and better dominant color detection |

**Installation:**
```bash
pip install playwright beautifulsoup4 fastapi jinja2 colorgram.py rcssmin python-dotenv
playwright install chromium  # Install browser binaries
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── landing_page/
│   ├── research.py          # Playwright LP scraping + pattern extraction
│   ├── copy_generator.py    # Claude-based copy generation with formulas
│   ├── color_extractor.py   # Extract palettes from images/video
│   ├── template_builder.py  # Jinja2 template rendering
│   ├── optimizer.py         # CSS minification, inline optimization
│   └── templates/
│       ├── base.html.j2     # Base layout with modular sections
│       ├── sections/
│       │   ├── hero.html.j2
│       │   ├── benefits.html.j2
│       │   ├── waitlist.html.j2
│       │   └── footer.html.j2
│       └── presets/
│           └── color_palettes.json
├── cli/
│   └── generate_landing_page.py  # CLI entry point
└── pipeline/
    └── integration.py        # Pipeline mode integration
```

### Pattern 1: Research-Driven Generation Pipeline

**What:** Five-stage pipeline: Research → Extract → Generate → Assemble → Optimize

**When to use:** When generating LPs that need to match industry standards rather than using fixed templates

**Flow:**
1. **Research Stage**: Playwright scrapes top 10 LPs in same industry/region
2. **Extract Stage**: BeautifulSoup parses HTML, extracts patterns (color schemes, section order, copy hooks, CTA placement)
3. **Generate Stage**: Claude receives research context + copywriting formula → generates copy
4. **Assemble Stage**: Jinja2 renders modular sections into single HTML
5. **Optimize Stage**: rcssmin inlines and minifies CSS; validates mobile-first breakpoints

**Example research extraction:**
```python
# Source: Playwright + BeautifulSoup pattern (web scraping best practices 2026)
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def research_competitor_lps(industry: str, region: str, count: int = 10):
    """Scrape top-performing LPs in industry/region."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Search for top LPs (e.g., via Google or curated list)
        search_query = f"best {industry} landing pages {region} 2026"
        await page.goto(f"https://www.google.com/search?q={search_query}")

        # Extract LP URLs (simplified)
        lp_urls = await extract_lp_urls(page)

        patterns = []
        for url in lp_urls[:count]:
            await page.goto(url, wait_until="networkidle")
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

            patterns.append({
                'url': url,
                'hero_headline': extract_hero_headline(soup),
                'cta_text': extract_cta_text(soup),
                'section_order': extract_section_order(soup),
                'color_scheme': extract_color_scheme(soup),
                'video_placement': detect_video_placement(soup)
            })

        await browser.close()
        return patterns
```

### Pattern 2: Modular Section Components

**What:** Each LP section is a standalone Jinja2 template that accepts standard props

**When to use:** Always — enables Phase 15 (AI Section Editing) to reorder/add/subtract sections

**Example:**
```jinja2
{# templates/sections/hero.html.j2 #}
{# Source: Mobile-first responsive design best practices 2026 #}
<section class="hero" id="hero">
  <div class="hero__content">
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subheadline">{{ subheadline }}</p>

    {% if video_url %}
    <video class="hero__video"
           autoplay muted loop playsinline
           poster="{{ video_poster }}">
      <source src="{{ video_url }}" type="video/mp4">
      {# Fallback to hero image if video fails #}
      <img src="{{ hero_image }}" alt="{{ headline }}" loading="eager">
    </video>
    {% else %}
    <img src="{{ hero_image }}" alt="{{ headline }}" class="hero__image" loading="eager">
    {% endif %}

    <a href="#waitlist" class="hero__cta">{{ cta_text }}</a>
  </div>
</section>

<style>
/* Mobile-first base styles (default: < 768px) */
.hero__cta {
  min-width: 48px;
  min-height: 48px;  /* Thumb-friendly touch target */
  padding: 14px 28px;
  font-size: 18px;
}

/* Tablet and up (>= 768px) */
@media (width >= 768px) {
  .hero__headline {
    font-size: 3rem;
  }
}

/* Desktop (>= 1024px) */
@media (width >= 1024px) {
  .hero__content {
    max-width: 1200px;
  }
}
</style>
```

### Pattern 3: Copywriting Formula Injection

**What:** Structure Claude prompts with proven copywriting formulas (PAS, AIDA, BAB)

**When to use:** Always for copy generation — formulas are "containers for AI prompts"

**Example:**
```python
# Source: AI copywriting proven formulas 2026
def generate_copy_with_formula(
    formula: str,  # "PAS" | "AIDA" | "BAB"
    product_idea: str,
    target_audience: str,
    research_context: dict
) -> dict:
    """Generate LP copy using proven copywriting formula."""

    formula_prompts = {
        "PAS": """
            Use the PAS (Problem-Agitate-Solution) formula:

            1. Problem: Identify the {target_audience}'s main pain point related to {product_idea}
            2. Agitate: Amplify the emotional cost of not solving it
            3. Solution: Present {product_idea} as the fix

            Research context (top-performing LPs in this space):
            {research_context}

            Generate:
            - Headline (Problem + Hook)
            - Subheadline (Agitate emotional cost)
            - 3 benefit statements (Solution details)
            - Primary CTA text

            Tone: Conversational, friendly, direct second-person ("you")
        """,
        "AIDA": """
            Use the AIDA (Attention-Interest-Desire-Action) formula:

            1. Attention: Grab {target_audience}'s attention with bold claim
            2. Interest: Build interest with specific benefits
            3. Desire: Create desire by showing transformation
            4. Action: Direct clear call-to-action

            Research context: {research_context}

            Generate headline, subheadline, 3 benefits, CTA.
            Tone: Conversational, friendly, second-person.
        """
    }

    prompt = formula_prompts[formula].format(
        product_idea=product_idea,
        target_audience=target_audience,
        research_context=research_context
    )

    # Call Claude API with structured output
    response = call_claude_api(prompt, model="claude-opus-4.6")
    return parse_copy_response(response)
```

### Pattern 4: Color Extraction Strategy

**What:** Extract dominant colors from existing pipeline assets (images/video frames)

**When to use:** When user selects Option 1 (extract from product assets) for color scheme

**Example:**
```python
# Source: Python color palette extraction libraries 2026
import colorgram

def extract_color_palette(image_path: str, num_colors: int = 5) -> list[dict]:
    """Extract dominant colors from product image/video frame."""
    colors = colorgram.extract(image_path, num_colors)

    palette = []
    for color in colors:
        palette.append({
            'rgb': f'rgb({color.rgb.r}, {color.rgb.g}, {color.rgb.b})',
            'hex': f'#{color.rgb.r:02x}{color.rgb.g:02x}{color.rgb.b:02x}',
            'proportion': color.proportion  # How much of image this color represents
        })

    return palette

def select_primary_secondary(palette: list[dict]) -> dict:
    """Choose primary (highest proportion) and secondary colors."""
    sorted_palette = sorted(palette, key=lambda c: c['proportion'], reverse=True)

    return {
        'primary': sorted_palette[0]['hex'],      # Most dominant
        'secondary': sorted_palette[1]['hex'],    # Second most dominant
        'accent': sorted_palette[2]['hex'],       # Third for CTAs
        'background': '#ffffff',                  # Default light
        'text': '#1a1a1a'                        # Default dark
    }
```

### Pattern 5: Single-File HTML with Inline CSS

**What:** Generate one self-contained HTML file with all CSS inlined and minified

**When to use:** Always — meets LP-03 requirement and enables zero-build deployment

**Example:**
```python
# Source: Single-file HTML inline CSS best practices 2026
import rcssmin
from jinja2 import Environment, FileSystemLoader

def generate_single_file_html(
    sections: list[str],
    styles: str,
    output_path: str
) -> None:
    """Generate single-file HTML with inline minified CSS."""

    # Minify CSS (critical + non-critical all inline)
    minified_css = rcssmin.cssmin(styles)

    # Render final HTML
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('base.html.j2')

    html = template.render(
        inline_css=minified_css,
        sections=sections,
        viewport_meta='<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    )

    # Write single file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # Validate file size (warn if > 100KB for performance)
    file_size_kb = len(html.encode('utf-8')) / 1024
    if file_size_kb > 100:
        print(f"Warning: HTML file is {file_size_kb:.1f}KB. Consider optimizing images.")
```

### Anti-Patterns to Avoid

- **Don't scrape without rate limiting**: Use delays between requests (2-5 seconds) to avoid getting blocked or overloading servers
- **Don't use SPAs for landing pages**: Single-file static HTML scores 100 on Lighthouse; React/Vue SPAs score lower due to client-side rendering overhead
- **Don't hardcode breakpoints**: Use content-based breakpoints where design breaks, not arbitrary device widths
- **Don't fake social proof**: User decision forbids fabricated testimonials/stats — use only implied soft signals
- **Don't auto-play with sound**: All browsers block non-muted autoplay; always use `autoplay muted loop playsinline`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Web scraping dynamic JS sites | Custom HTTP requests + regex parsing | **Playwright + BeautifulSoup** | Modern sites use React/Vue/Ajax; headless browser handles JS rendering, waits for elements, avoids detection |
| CSS minification | Manual whitespace removal | **rcssmin** | Edge cases like `calc()`, `url()`, quoted strings; hand-rolled breaks easily |
| Color palette extraction | Manual pixel iteration + clustering | **colorgram.py** or **Pylette** | K-means clustering with perceptual color weighting is complex; libraries handle edge cases |
| Responsive breakpoints | Fixed device widths (320px, 768px, 1024px) | Content-based breakpoints | Devices vary too much; design should break based on content, not arbitrary widths |
| Spam prevention | Custom bot detection | **Honeypot pattern** | Timing checks, hidden fields, checkbox tricks are well-tested; reinventing misses edge cases |
| Video format detection | Manual codec sniffing | **Multiple `<source>` tags** (AV1 → VP9 → H.264) | Browser auto-selects best supported format; handles fallback gracefully |

**Key insight:** Landing page generation involves well-trodden territory (scraping, templating, responsive design). The ecosystem has battle-tested solutions for every piece. Custom implementations introduce bugs, maintenance burden, and slower performance.

---

## Common Pitfalls

### Pitfall 1: Scraping Without Respecting robots.txt

**What goes wrong:** Automated scraping gets blocked or violates site policies, breaking research phase

**Why it happens:** Eagerness to gather data quickly without checking permissions

**How to avoid:**
- Always check `https://example.com/robots.txt` before scraping
- Use `User-Agent` header identifying your bot
- Implement rate limiting (2-5 second delays between requests)
- Scrape during off-peak hours where possible

**Warning signs:** 403 Forbidden errors, IP bans, CAPTCHA challenges

### Pitfall 2: Inline CSS Without Viewport Meta Tag

**What goes wrong:** Mobile-first responsive design doesn't work; page renders at desktop width on mobile

**Why it happens:** Forgetting the viewport meta tag makes mobile browsers assume desktop layout

**How to avoid:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```
Always include in `<head>`. Without it, `@media (width >= 768px)` queries don't trigger correctly on mobile.

**Warning signs:** Mobile preview looks zoomed out; pinch-to-zoom required; buttons too small to tap

### Pitfall 3: Video File Size Kills Performance

**What goes wrong:** LP loads slowly due to huge video file (10MB+), high bounce rate

**Why it happens:** Including 4K or uncompressed video for hero section

**How to avoid:**
- Target **< 2.5MB** for hero background video
- Use **720p max** for autoplay (1080p for featured video)
- Encode with **H.264 + WebM VP9** (or AV1) for modern browser support
- Provide fallback `poster` image for slow connections

**Warning signs:** Lighthouse Performance score < 90, LCP > 2.5s, mobile users report slow loading

### Pitfall 4: Honeypot Field Visible in CSS

**What goes wrong:** Legitimate users see and fill the honeypot field, their submissions get rejected as spam

**Why it happens:** Using `display: none` instead of more sophisticated hiding (bots detect `display: none`)

**How to avoid:**
```css
.honeypot {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
}
```
Use off-screen positioning instead of `display: none`. Name the field realistically (e.g., `website_url`, `company_name`).

**Warning signs:** Zero spam caught, real users complaining their form submissions don't work

### Pitfall 5: LLM Copy Generation Without Formula Structure

**What goes wrong:** AI generates generic, fluffy copy that doesn't convert; lacks clear value prop or CTA

**Why it happens:** Vague prompt like "write a landing page for X" without formula guidance

**How to avoid:**
- Use proven formulas (PAS, AIDA, BAB) as prompt structure
- Provide research context (what top LPs in the space do)
- Specify exact outputs needed (headline, subheadline, 3 benefits, CTA)
- Set tone explicitly ("conversational, friendly, second-person")

**Warning signs:** Copy reads like generic marketing fluff, no clear call-to-action, passive voice instead of "you"

### Pitfall 6: Not Testing Mobile Touch Targets

**What goes wrong:** CTAs and form inputs too small on mobile; users struggle to tap, abandon page

**Why it happens:** Designing desktop-first, forgetting thumb-friendly sizes

**How to avoid:**
- Minimum **48×48px** touch targets (Apple: 44px, Android: 48px)
- Use padding to expand tappable area without making visual element huge
- **8px spacing** between adjacent touch targets
- Test on actual mobile device, not just browser DevTools

**Warning signs:** High mobile bounce rate, analytics show tap struggles (rage taps), form abandonment

### Pitfall 7: Scraping Returns Incomplete HTML

**What goes wrong:** Research phase extracts partial data; JavaScript-rendered content missing

**Why it happens:** Using basic HTTP requests instead of headless browser for JS-heavy sites

**How to avoid:**
- Always use **Playwright** for modern LP scraping (not requests + BeautifulSoup alone)
- Wait for `networkidle` or specific elements before extracting HTML
- Parse with BeautifulSoup after Playwright loads full page

**Warning signs:** Scraped HTML missing sections that appear in browser, empty divs, placeholder content

---

## Code Examples

Verified patterns from research sources:

### Example 1: Mobile-First Responsive Hero Section

```html
<!-- Source: Mobile-first responsive design best practices 2026 -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ product_name }} - Landing Page</title>
  <style>
    /* Mobile-first base (< 768px) */
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
      color: #1a1a1a;
    }

    .hero {
      padding: 2rem 1rem;
      text-align: center;
    }

    .hero__headline {
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 1rem;
    }

    .hero__subheadline {
      font-size: 1.125rem;
      margin-bottom: 2rem;
      color: #4a5568;
    }

    .hero__video {
      width: 100%;
      max-width: 600px;
      height: auto;
      border-radius: 8px;
      margin-bottom: 2rem;
    }

    .hero__cta {
      display: inline-block;
      min-width: 48px;
      min-height: 48px;
      padding: 14px 32px;
      background: #2563eb;
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 18px;
      font-weight: 600;
      transition: background 0.2s;
    }

    .hero__cta:hover,
    .hero__cta:focus {
      background: #1d4ed8;
    }

    /* Tablet (>= 768px) */
    @media (width >= 768px) {
      .hero {
        padding: 4rem 2rem;
      }

      .hero__headline {
        font-size: 3rem;
      }

      .hero__subheadline {
        font-size: 1.5rem;
      }
    }

    /* Desktop (>= 1024px) */
    @media (width >= 1024px) {
      .hero {
        padding: 6rem 2rem;
      }

      .hero__headline {
        font-size: 3.5rem;
      }
    }
  </style>
</head>
<body>
  <section class="hero">
    <h1 class="hero__headline">{{ headline }}</h1>
    <p class="hero__subheadline">{{ subheadline }}</p>

    <video class="hero__video"
           autoplay muted loop playsinline
           poster="{{ video_poster_url }}">
      <source src="{{ video_url }}" type="video/mp4">
      <img src="{{ fallback_image }}" alt="{{ product_name }}">
    </video>

    <a href="#waitlist" class="hero__cta">{{ cta_text }}</a>
  </section>
</body>
</html>
```

### Example 2: Honeypot Spam Prevention Form

```html
<!-- Source: Honeypot spam prevention best practices 2026 -->
<form id="waitlist-form" action="/api/waitlist" method="POST">
  <label for="email">Email Address</label>
  <input
    type="email"
    id="email"
    name="email"
    required
    placeholder="you@example.com"
    style="min-height: 48px; font-size: 16px; padding: 12px;">

  <!-- Honeypot field: hidden from users, visible to bots -->
  <label for="website_url" class="honeypot-label">Website (leave blank)</label>
  <input
    type="text"
    id="website_url"
    name="website_url"
    class="honeypot-field"
    tabindex="-1"
    autocomplete="off">

  <!-- Hidden timestamp for submission speed check -->
  <input type="hidden" name="timestamp" id="timestamp" value="">

  <button type="submit" style="min-width: 48px; min-height: 48px; padding: 14px 28px; font-size: 18px;">
    Join Waitlist
  </button>
</form>

<style>
  /* Honeypot hiding technique */
  .honeypot-field,
  .honeypot-label {
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }
</style>

<script>
  // Set timestamp when form loads
  document.getElementById('timestamp').value = Date.now();

  // Validate on submit
  document.getElementById('waitlist-form').addEventListener('submit', function(e) {
    const honeypot = document.getElementById('website_url').value;
    const timestamp = document.getElementById('timestamp').value;
    const elapsed = Date.now() - parseInt(timestamp);

    // Reject if honeypot filled or submitted too quickly (< 2 seconds)
    if (honeypot !== '' || elapsed < 2000) {
      e.preventDefault();
      // Silently fail for bots (don't show error)
      return false;
    }
  });
</script>
```

### Example 3: Color Palette Extraction

```python
# Source: Python color extraction libraries 2026
import colorgram
from pathlib import Path

def extract_color_scheme(image_path: str | Path) -> dict:
    """
    Extract color palette from product image/video frame.
    Returns primary, secondary, accent colors for LP styling.
    """
    # Extract 5 dominant colors
    colors = colorgram.extract(str(image_path), 5)

    # Sort by proportion (most dominant first)
    sorted_colors = sorted(colors, key=lambda c: c.proportion, reverse=True)

    # Build color scheme
    scheme = {
        'primary': rgb_to_hex(sorted_colors[0].rgb),
        'secondary': rgb_to_hex(sorted_colors[1].rgb),
        'accent': rgb_to_hex(sorted_colors[2].rgb),
        'palette': [
            {
                'hex': rgb_to_hex(c.rgb),
                'rgb': f'rgb({c.rgb.r}, {c.rgb.g}, {c.rgb.b})',
                'proportion': round(c.proportion, 3)
            }
            for c in sorted_colors
        ]
    }

    return scheme

def rgb_to_hex(rgb) -> str:
    """Convert RGB object to hex string."""
    return f'#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}'

# Usage
if __name__ == '__main__':
    scheme = extract_color_scheme('output/run-123/hero-image.jpg')
    print(f"Primary: {scheme['primary']}")
    print(f"Secondary: {scheme['secondary']}")
    print(f"Accent: {scheme['accent']}")
```

### Example 4: Playwright LP Research

```python
# Source: Playwright web scraping best practices 2026
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import asyncio

async def research_landing_page(url: str) -> dict:
    """
    Scrape a competitor landing page and extract design patterns.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set user agent
        await page.set_extra_http_headers({
            'User-Agent': 'LandingPageResearchBot/1.0'
        })

        # Navigate and wait for full load
        await page.goto(url, wait_until='networkidle', timeout=30000)

        # Get fully-rendered HTML
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        # Extract patterns
        patterns = {
            'url': url,
            'title': soup.find('title').get_text() if soup.find('title') else '',
            'hero_headline': extract_hero_headline(soup),
            'cta_buttons': extract_cta_buttons(soup),
            'section_order': extract_section_order(soup),
            'has_video': bool(soup.find('video')),
            'video_placement': detect_video_placement(soup),
            'color_scheme': extract_inline_colors(soup)
        }

        await browser.close()
        return patterns

def extract_hero_headline(soup: BeautifulSoup) -> str:
    """Extract the main headline (usually first h1)."""
    h1 = soup.find('h1')
    return h1.get_text(strip=True) if h1 else ''

def extract_cta_buttons(soup: BeautifulSoup) -> list[dict]:
    """Find all CTA buttons and extract text + href."""
    ctas = []

    # Look for common CTA patterns
    for tag in soup.find_all(['a', 'button']):
        classes = ' '.join(tag.get('class', []))
        if any(keyword in classes.lower() for keyword in ['cta', 'btn', 'button', 'signup']):
            ctas.append({
                'text': tag.get_text(strip=True),
                'href': tag.get('href', ''),
                'classes': classes
            })

    return ctas

def detect_video_placement(soup: BeautifulSoup) -> str | None:
    """Determine where video appears (hero, middle, none)."""
    video = soup.find('video')
    if not video:
        return None

    # Check if video is within hero section
    hero = soup.find(class_=lambda c: c and 'hero' in c.lower())
    if hero and hero.find('video'):
        return 'hero'

    return 'middle'

# Usage
async def main():
    patterns = await research_landing_page('https://example.com/lp')
    print(f"Headline: {patterns['hero_headline']}")
    print(f"Video placement: {patterns['video_placement']}")
    print(f"CTAs: {len(patterns['cta_buttons'])}")

if __name__ == '__main__':
    asyncio.run(main())
```

### Example 5: FastAPI + Jinja2 Generation Endpoint

```python
# Source: FastAPI Jinja2 templates server-side rendering 2026
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.post("/api/generate-landing-page")
async def generate_landing_page(
    product_idea: str,
    target_audience: str,
    industry: str | None = None,
    region: str | None = None
) -> HTMLResponse:
    """
    Generate landing page HTML from product idea and audience.
    """
    # 1. Research competitor LPs
    research_patterns = await research_competitor_lps(
        industry or infer_industry(product_idea),
        region or "US"
    )

    # 2. Generate copy using PAS formula
    copy = generate_copy_with_formula(
        formula="PAS",
        product_idea=product_idea,
        target_audience=target_audience,
        research_context=research_patterns
    )

    # 3. Extract color scheme from assets (if Option 1)
    color_scheme = extract_color_scheme("output/hero-image.jpg")

    # 4. Render Jinja2 template
    html = templates.TemplateResponse(
        "landing_page.html.j2",
        {
            "request": {},  # Required by Jinja2Templates
            "headline": copy['headline'],
            "subheadline": copy['subheadline'],
            "benefits": copy['benefits'],
            "cta_text": copy['cta_text'],
            "video_url": "output/video.mp4",
            "video_poster": "output/poster.jpg",
            "color_scheme": color_scheme
        }
    )

    return html
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed LP templates | **Research-driven generation** (scrape top LPs → extract patterns → AI generates) | 2024-2025 | LPs match industry standards instead of generic templates; higher conversion |
| Selenium for web scraping | **Playwright** | 2023-2024 | Faster, more reliable; auto-waits for elements; better JS rendering |
| GPT-3.5 for copy | **Claude 4.6 Opus/Sonnet** | 2025-2026 | Better instruction-following for structured output; more natural conversational tone |
| `min-width` media queries | **Range syntax** `(width >= 768px)` | 2024 (CSS spec update) | Cleaner, more readable; better developer experience |
| Desktop-first design | **Mobile-first** with progressive enhancement | 2020-2021 | Better Core Web Vitals; reflects mobile-majority traffic |
| H.264 only | **Multi-codec** (AV1 → VP9 → H.264 fallback) | 2024-2025 | 30-50% smaller files with AV1/VP9; better performance; universal browser support via fallback |
| `display: none` honeypot | **Off-screen positioning** | 2023 | Bots detect `display: none`; position-based hiding more effective |

**Deprecated/outdated:**
- **jQuery for DOM manipulation** → Use vanilla JS (modern browsers have native equivalents)
- **Bootstrap/Tailwind for single-file LPs** → Hand-roll minimal CSS (no framework overhead)
- **CAPTCHA for spam prevention** → Honeypot + timing checks (better UX, no Google dependency)
- **GIFs for hero animations** → MP4/WebM video (10x smaller files, better quality)

---

## Open Questions

### 1. **How to programmatically identify "top-performing" LPs in an industry?**

**What we know:**
- Can scrape curated lists (e.g., "best SaaS landing pages 2026" articles)
- Can search Google for industry + "landing page" and scrape top results
- Landing page galleries exist (Unbounce, LandingPageFlow) but lack performance data

**What's unclear:**
- No public API for conversion rates or performance metrics
- Curated lists are subjective (editor-picked, not data-driven)
- Google ranking doesn't necessarily mean high-converting LP

**Recommendation:**
- **Phase 14**: Use curated lists + Google search top results as proxy for "top-performing"
- **Future enhancement**: Build internal database of LP patterns from scraping; track which patterns correlate with user regenerations (if users regenerate often, those patterns didn't work)
- **Alternative**: Partner with analytics service or scrape public A/B test case studies

### 2. **Video placement: hero vs. middle vs. background?**

**What we know:**
- Research says "including video can boost conversions by 80%" but doesn't specify placement
- User decision: "Claude's discretion, informed by research"
- Best practice: autoplay muted loop for hero background videos

**What's unclear:**
- Hero foreground video vs. hero background video vs. mid-page video — conversion differences?
- Does autoplay video in hero increase engagement or cause annoyance/bounce?

**Recommendation:**
- **Default**: Hero background video (autoplay muted loop) with headline/CTA overlaid — follows 2026 trend seen in top SaaS LPs
- **Research during Phase 14**: Scrape top 50 LPs, analyze video placement distribution, document in research output
- **Future**: A/B test different placements in Phase 17 (Analytics)

### 3. **How many sections is "optimal" for conversion?**

**What we know:**
- User decision: lean default (hero + 3 benefits + waitlist + footer)
- Research says "fewer mental steps = higher conversion"
- Long-form LPs work for cold traffic (AICPBSAWN formula), short for warm traffic

**What's unclear:**
- Does the optimal section count vary by industry? (e.g., B2B SaaS vs. consumer app)
- Phase 15 enables section editing, but what's the starting point that converts best?

**Recommendation:**
- **Phase 14**: Stick to user's lean default (4 sections total)
- **Research enhancement**: During LP scraping, track section count distribution by industry; if pattern emerges (e.g., fintech LPs average 6 sections), adjust default accordingly
- **Phase 15**: Let AI recommend adding sections based on industry research

---

## Sources

### Primary (HIGH confidence)

**Copywriting Formulas & AI:**
- [Landing Page Copywriting Frameworks: PAS, AIDA, BAB & More [2026]](https://www.landy-ai.com/blog/landing-page-copywriting-frameworks)
- [Copywriting Formulas: AIDA, PAS & More to Boost Conversions in 2026](https://universaldigitalservices.com/copywriting-formulas-aida-pas-convert/)
- [Brand Voice & Tone Building With Prompt Engineering](https://quiq.com/blog/brand-prompt-engineering/)
- [The Ultimate Guide to Prompt Engineering in 2026](https://www.lakera.ai/blog/prompt-engineering-guide)

**Web Scraping & Playwright:**
- [Web Scraping with Playwright and Python](https://scrapfly.io/blog/posts/web-scraping-with-playwright-and-python)
- [Playwright Web Scraping Tutorial for 2026](https://oxylabs.io/blog/playwright-web-scraping)
- [Web Scraping Best Practices in 2026 | ScrapingBee](https://www.scrapingbee.com/blog/web-scraping-best-practices/)
- [7 Web Scraping Best Practices You Must Be Aware of ['26]](https://research.aimultiple.com/web-scraping-best-practices/)

**Mobile-First Responsive Design:**
- [CSS Media Queries: The Complete Guide for 2026](https://devtoolbox.dedyn.io/blog/css-media-queries-complete-guide)
- [Mobile-First CSS Approach](https://medium.com/@usman_qb/mobile-first-css-approach-83e75e87d606)
- [How to Write Mobile-first CSS | Zell Liew](https://zellwk.com/blog/how-to-write-mobile-first-css/)

**Touch Targets & Accessibility:**
- [All accessible touch target sizes - LogRocket](https://blog.logrocket.com/ux-design/all-accessible-touch-target-sizes/)
- [Accessible Target Sizes Cheatsheet — Smashing Magazine](https://www.smashingmagazine.com/2023/04/accessible-tap-target-sizes-rage-taps-clicks/)
- [Accessible tap targets | web.dev](https://web.dev/articles/accessible-tap-targets)

**FastAPI + Jinja2:**
- [FastAPI - Templates (Official Docs)](https://fastapi.tiangolo.com/advanced/templates/)
- [How to Serve a Website With FastAPI Using HTML and Jinja2 – Real Python](https://realpython.com/fastapi-jinja2-template/)
- [How to Build Dynamic Frontends with FastAPI and Jinja2](https://developer-service.blog/how-to-build-dynamic-frontends-with-fastapi-and-jinja2/)

### Secondary (MEDIUM confidence)

**Landing Page Conversion Patterns:**
- [The Best CTA Placement Strategies For 2026 Landing Pages](https://www.landingpageflow.com/post/best-cta-placement-strategies-for-landing-pages)
- [11 Landing Page Best Practices (2026)](https://www.involve.me/blog/landing-page-best-practices)
- [Landing Page Best Practices 2026 — A Structure That Converts](https://toimi.pro/blog/landing-page-design-structure-conversion/)

**Video Autoplay & Performance:**
- [Video on Landing Page: Boost Conversions in 2026](https://www.involve.me/blog/video-landing-pages)
- [Autoplay Videos: Best Practices for UX & Performance](https://ignite.video/en/articles/basics/autoplay-videos)
- [We Hate Autoplay Too: 3 Experts on Landing Page Video Best Practices](https://unbounce.com/landing-pages/autoplay-landing-page-best-practices/)

**Video Codecs & Formats:**
- [Navigating the codec landscape for 2025: AV1, H.264, H.265, VP8 and VP9](https://uploadcare.com/blog/navigating-codec-landscapes/)
- [The State of Video Codecs in 2026](https://www.gumlet.com/learn/video-codec/)
- [Creating web optimized video with ffmpeg using VP9 and H265 codecs](https://pixelpoint.io/blog/web-optimized-video-ffmpeg/)

**Honeypot Spam Prevention:**
- [Add a Honeypot to Website Forms to Reduce Spam Signups](https://www.getvero.com/resources/add-a-honeypot-to-website-forms-to-reduce-spam/)
- [Honeypot Spam Prevention: Anti-Spam Technique | Thryv](https://www.thryv.com/blog/honeypot-technique-html-form-spam-protection/)
- [What is Honeypot Anti-Spam? [And How To Use It!]](https://formidableforms.com/defeat-spambots-honeypot-spam-protection/)

**Color Extraction:**
- [GitHub - obskyr/colorgram.py](https://github.com/obskyr/colorgram.py)
- [Generating color palettes from movies with Python](https://medium.com/@andrisgauracs/generating-color-palettes-from-movies-with-python-16503077c025)
- [Extract dominant colors of an image using Python | GeeksforGeeks](https://www.geeksforgeeks.org/extract-dominant-colors-of-an-image-using-python/)

**CSS Performance & Minification:**
- [Improve site performance by inlining your CSS - LogRocket](https://blog.logrocket.com/improve-site-performance-inlining-css/)
- [GitHub - ndparker/rcssmin: Fast CSS minifier for Python](https://github.com/ndparker/rcssmin)
- [How to Minify CSS with Python - The Python Code](https://thepythoncode.com/article/minimize-css-files-in-python)

**Static HTML vs SPA Performance:**
- [Single Page Application in 2026: Is it Right for You?](https://visionvix.com/single-page-application/)
- [Why Your Web App Feels Fast But Scores Low on Lighthouse](https://medium.com/selldone/why-your-web-app-feels-fast-but-scores-low-on-lighthouse-and-how-to-fix-it-edcc5cb76753)

**Environment Variables:**
- [How to Work with Environment Variables in Python](https://oneuptime.com/blog/post/2026-01-26-work-with-environment-variables-python/view)
- [GitHub - theskumar/python-dotenv](https://github.com/theskumar/python-dotenv)

### Tertiary (LOW confidence - WebSearch only, marked for validation)

- BeautifulSoup + Playwright integration patterns (mentioned in multiple sources but no official docs)
- "Top 10 performing LPs" identification methods (no authoritative source on programmatic discovery)

---

## Metadata

**Confidence breakdown:**
- **Standard stack: HIGH** — Playwright, BeautifulSoup, Claude, FastAPI+Jinja2 all have extensive documentation and 2026 usage verification
- **Architecture patterns: MEDIUM-HIGH** — Mobile-first, modular sections, copywriting formulas are proven, but research-driven LP generation is newer (2024-2025 trend)
- **Pitfalls: MEDIUM** — Common issues well-documented (viewport meta, touch targets, video size), but specific to this use case (research-driven generation) less battle-tested
- **Color extraction: MEDIUM** — Libraries well-established, but "extract from video frames for LP color scheme" pattern less documented
- **Don't hand-roll: HIGH** — Strong consensus on using libraries for scraping, minification, color extraction

**Research date:** 2026-02-19
**Valid until:** ~March 21, 2026 (30 days for stable stack; fast-moving areas like AI models may change sooner)
**Re-research triggers:** New Claude model release, Playwright major version update, significant changes to web scraping legal landscape
