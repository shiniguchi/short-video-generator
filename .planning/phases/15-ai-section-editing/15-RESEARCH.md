# Phase 15: AI Section Editing - Research

**Researched:** 2026-02-19
**Domain:** HTML section targeting, AI-driven partial regeneration, Jinja2 re-rendering
**Confidence:** HIGH

## Summary

Phase 15 adds AI-powered section editing on top of the existing Phase 14 LP generator. The core loop is: user targets a section by name → writes a natural language prompt → AI regenerates only that section's copy fields → Jinja2 re-renders the section HTML → regex replaces the section in the saved HTML → optimizer re-runs. No new libraries needed: `beautifulsoup4` is already in `requirements.txt`, and all rendering infrastructure (`render_section`, `get_section_list`, `optimize_html`) already exists in Phase 14 code.

The key architectural insight: Phase 14's `optimize_html()` consolidates all `<style>` blocks into `<head>`. So after section replacement, a new `<style>` block lands in `<body>`. Re-running `optimize_html()` on the result correctly re-consolidates CSS. No HTML integrity is broken.

**Primary recommendation:** Build a `section_editor.py` module with `edit_section(html_path, section_name, user_prompt)` as the entry point, and a `scripts/edit_lp_section.py` CLI command. Reuse `render_section()` and `optimize_html()` from Phase 14 directly.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `re` (stdlib) | built-in | Regex section replacement in HTML | No dependencies, fast, sufficient |
| `jinja2` | already installed | Re-render individual section templates | Already used by Phase 14 |
| `beautifulsoup4` | 4.14.3 | Optional: parse section context from HTML | Already in requirements.txt |
| `argparse` (stdlib) | built-in | CLI for section editing | Matches Phase 14 CLI pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rcssmin` | already installed | Re-optimize CSS after section replacement | Call `optimize_html()` after replacing |
| `app.services.llm_provider` | Phase 14 | AI copy generation | Already the project LLM abstraction |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| regex section replacement | BeautifulSoup HTML parsing | BS4 is safer for malformed HTML but adds complexity; regex is sufficient since we control the HTML output format |
| partial copy regen (fields only) | full LP regen | Partial is faster, preserves user context, meets requirement |

**Installation:**
```bash
# No new packages needed — all dependencies already installed
```

## Architecture Patterns

### Recommended Project Structure
```
app/services/landing_page/
├── section_editor.py     # NEW: edit_section() — the main Phase 15 entry point
├── generator.py          # Phase 14: full LP generation (unchanged)
├── copy_generator.py     # Phase 14: AI copy (reused for section-scoped prompts)
├── template_builder.py   # Phase 14: render_section() reused directly
├── optimizer.py          # Phase 14: optimize_html() reused after replacement
└── templates/sections/   # Phase 14: templates (unchanged)

scripts/
└── edit_lp_section.py    # NEW: CLI for section editing
```

### Pattern 1: Section-Scoped Copy Regeneration

**What:** Extract only the copy fields relevant to the target section, send a focused AI prompt to regenerate just those fields, re-render the section template, and splice it back into the HTML.

**When to use:** Every time a user targets a specific section with a natural language edit prompt.

**Section-to-copy-field mapping** (derived from `template_builder.py` `section_contexts`):

| Section | Copy Fields Used | Editable via AI |
|---------|-----------------|-----------------|
| `hero` | `headline`, `subheadline`, `cta_text`, `trust_text` | YES |
| `benefits` | `benefits` (list) | YES |
| `features` | `features` (list) | YES |
| `how_it_works` | `how_it_works` (list) | YES |
| `cta_repeat` | `headline` (hardcoded), `subheadline`, `cta_text`, `urgency_text` | YES |
| `faq` | `faq` (list) | YES |
| `waitlist` | `cta_text`, `social_proof_text`, `trust_text` | YES |
| `footer` | `footer_text` | YES |
| `gallery` | `images` (file paths — not copy) | NO — skip AI edit |

**Example:**
```python
# Source: Phase 14 template_builder.py section_contexts (verified)

# Pydantic schema for section-scoped edit output
class HeroSectionCopy(BaseModel):
    headline: str
    subheadline: str
    cta_text: str
    trust_text: Optional[str] = None

# Use generate_structured() from existing LLM provider
llm = get_llm_provider()
new_copy = llm.generate_structured(
    prompt=_build_section_edit_prompt(section_name, user_prompt, current_context),
    schema=HeroSectionCopy,
    system_prompt="You are a landing page copywriter. Edit only the requested section.",
    temperature=0.8
)
```

### Pattern 2: Regex Section Replacement

**What:** Replace a `<section data-section="NAME">...</section>` block in-place using a compiled regex.

**Verified working** (tested during research):
```python
# Source: tested in repo context 2026-02-19
import re

def replace_section_in_html(html: str, section_name: str, new_section_html: str) -> str:
    """Replace a section block in the full HTML by data-section attribute."""
    pattern = re.compile(
        r'<section[^>]*data-section=["\']' + re.escape(section_name) + r'["\'][^>]*>.*?</section>',
        re.DOTALL
    )
    return pattern.sub(new_section_html, html)
```

### Pattern 3: Re-Optimize After Replacement

**What:** After splicing in a new section (which has an embedded `<style>` block from the Jinja2 template), re-run `optimize_html()` to consolidate CSS back into `<head>`.

**Why required:** `optimize_html()` moves all `<style>` tags to `<head>`. The new section's `<style>` tag lands in `<body>`. Re-running `optimize_html()` fixes this correctly.

```python
# Source: Phase 14 optimizer.py — reuse as-is
from app.services.landing_page.optimizer import optimize_html, validate_html

# After section replacement:
replaced_html = replace_section_in_html(html, section_name, new_section_html)
final_html = optimize_html(replaced_html)   # consolidates CSS
validation = validate_html(final_html)      # structural check
html_path.write_text(final_html, encoding='utf-8')
```

### Pattern 4: Context Extraction for Edit Prompts

**What:** Pull current section content from saved HTML so the AI knows what it's editing. Use regex to extract the current `<section>` block contents.

```python
def extract_section_context(html: str, section_name: str) -> str:
    """Extract current section HTML for context in the edit prompt."""
    pattern = re.compile(
        r'<section[^>]*data-section=["\']' + re.escape(section_name) + r'["\'][^>]*>(.*?)</section>',
        re.DOTALL
    )
    match = pattern.search(html)
    return match.group(1).strip() if match else ""
```

### Anti-Patterns to Avoid

- **Regenerating the whole LP on section edit:** Slow and loses any other partial edits the user made. The whole point of Phase 15 is surgical edits.
- **Trying to parse CSS from optimized HTML to extract per-section styles:** The CSS is already namespaced by BEM class (`.hero__headline`, `.benefits__card`). Re-running `optimize_html()` after replacement handles CSS correctly without any manual CSS surgery.
- **Storing copy as intermediate JSON between edits:** Adds state management complexity. The HTML file IS the source of truth. Extract context from HTML when needed.
- **Using `generate_structured(prompt, LandingPageCopy)` for section edits:** This generates all 12+ fields. Instead, create small per-section Pydantic schemas with only the fields that section uses.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template re-rendering | Custom string interpolation | `render_section()` from Phase 14 | Already handles Jinja2 env, template path resolution |
| CSS consolidation after edit | Manual `<style>` injection | `optimize_html()` from Phase 14 | Handles extract-combine-minify-inject in one call |
| LLM structured output | Custom JSON parsing | `llm.generate_structured()` | Already handles schema validation, retries, mock |
| HTML section detection | Full HTML parser | Regex on `data-section` attribute | Phase 14 guarantees clean HTML output format |

**Key insight:** All infrastructure exists in Phase 14. Phase 15 is ~150 lines of new code that orchestrates existing components.

## Common Pitfalls

### Pitfall 1: CSS Duplication After Multiple Edits

**What goes wrong:** Each section replacement adds a new `<style>` block. After 5 edits, the HTML has 5 duplicate CSS blocks. Re-running `optimize_html()` each time prevents this — it extracts ALL `<style>` tags and rebuilds one minified block.

**Why it happens:** Phase 14 section templates embed their own `<style>` block. The optimizer was designed to be run once at generation time.

**How to avoid:** Always call `optimize_html()` after every section replacement. Never skip it.

**Warning signs:** HTML file size grows after each edit. CSS specificity conflicts in browser.

---

### Pitfall 2: Regex Fails on Nested `<section>` Tags

**What goes wrong:** The regex pattern `.*?</section>` stops at the first `</section>` it finds, which may be a nested section inside the target section.

**Why it happens:** Phase 14 section templates do NOT nest `<section>` tags — they use `<div>` for internal structure. So this is not currently a risk, but could break if templates are modified.

**How to avoid:** Verify no Phase 14 section template has nested `<section>` elements before relying on regex. (Verified during research: all 9 templates use `<div>` for internal structure, `<section>` only at root.)

**Warning signs:** Section replacement silently truncates content inside the section.

---

### Pitfall 3: `gallery` Section Has No Editable Copy

**What goes wrong:** User tries to AI-edit the `gallery` section, which only contains image file paths — not text copy. Sending a copy-edit prompt produces irrelevant output.

**Why it happens:** `gallery` section is driven by `product_images` (file paths), not `LandingPageCopy` fields.

**How to avoid:** In the CLI and section editor, skip or reject `gallery` as a valid section for AI editing. Tell user: "Gallery section shows product images. To change images, re-run generation with different `--images` files."

---

### Pitfall 4: Edit Prompt Loses Product Context

**What goes wrong:** AI generates generic copy not specific to the product because the edit prompt only includes the user's edit instruction ("make it shorter") without product context.

**Why it happens:** The AI doesn't know what product is being edited unless told.

**How to avoid:** Always inject product context into the edit prompt. Extract `product_idea` from the `LandingPageResult` metadata, or store it alongside the HTML file (e.g., as a `landing-page.json` sidecar with `product_idea`, `target_audience`, `sections`). The current `LandingPageResult` schema already has `product_idea`.

---

### Pitfall 5: Missing `data-section` on Generated HTML

**What goes wrong:** Section replacement regex finds nothing because the HTML was generated before Phase 14-02 added `data-section` attributes.

**Why it happens:** Old HTML files generated with an earlier version of the templates lack `data-section`.

**How to avoid:** Validate `data-section` presence at the start of `edit_section()`. If section is not found, return a clear error: "Section 'X' not found in this LP. Was it generated with Phase 14 or later?"

## Code Examples

### Full Section Edit Flow

```python
# Source: architectural design based on Phase 14 code (verified patterns)
# File: app/services/landing_page/section_editor.py

import re
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from app.services.landing_page.template_builder import render_section
from app.services.landing_page.optimizer import optimize_html, validate_html
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


def edit_section(
    html_path: str,
    section_name: str,
    user_prompt: str,
    product_idea: str,
    use_mock: bool = False
) -> dict:
    """
    Edit a single LP section using AI.

    Returns: {"success": bool, "html_path": str, "section": str, "warning": str}
    """
    path = Path(html_path)
    html = path.read_text(encoding='utf-8')

    # 1. Validate section exists
    if f'data-section="{section_name}"' not in html:
        return {"success": False, "error": f"Section '{section_name}' not found"}

    # 2. Extract current section context
    current_context = _extract_section_context(html, section_name)

    # 3. Generate new copy for this section
    new_section_copy = _generate_section_copy(
        section_name, user_prompt, product_idea, current_context, use_mock
    )

    # 4. Re-render section template with new copy
    template_context = _build_template_context(section_name, new_section_copy)
    new_section_html = render_section(section_name, template_context)

    # 5. Replace section in HTML
    updated_html = _replace_section(html, section_name, new_section_html)

    # 6. Re-optimize (consolidate CSS)
    final_html = optimize_html(updated_html)
    validation = validate_html(final_html)

    # 7. Save
    path.write_text(final_html, encoding='utf-8')

    return {
        "success": True,
        "html_path": str(path),
        "section": section_name,
        "warnings": validation.get("warnings", [])
    }


def _replace_section(html: str, section_name: str, new_html: str) -> str:
    pattern = re.compile(
        r'<section[^>]*data-section=["\']' + re.escape(section_name) + r'["\'][^>]*>.*?</section>',
        re.DOTALL
    )
    return pattern.sub(new_html, html)


def _extract_section_context(html: str, section_name: str) -> str:
    pattern = re.compile(
        r'<section[^>]*data-section=["\']' + re.escape(section_name) + r'["\'][^>]*>(.*?)</section>',
        re.DOTALL
    )
    match = pattern.search(html)
    return match.group(1).strip() if match else ""
```

### Section-Scoped Pydantic Schemas

```python
# Source: derived from template_builder.py section_contexts (Phase 14)
# These are small schemas — one per section — for generate_structured()

class HeroEditCopy(BaseModel):
    headline: str       # 5-8 words, benefit-driven
    subheadline: str    # 15-25 words
    cta_text: str       # 2-4 words
    trust_text: Optional[str] = None

class BenefitsEditCopy(BaseModel):
    benefits: List[dict]  # Each: {title, description, icon_emoji}

class FaqEditCopy(BaseModel):
    faq_items: List[dict]  # Each: {question, answer}

# etc. for cta_repeat, features, how_it_works, waitlist, footer
```

### CLI Command Pattern

```python
# Source: matches Phase 14 scripts/generate_landing_page.py pattern
# scripts/edit_lp_section.py

parser.add_argument('--lp', required=True, help='Path to landing-page.html')
parser.add_argument('--section', required=True,
    choices=['hero', 'benefits', 'features', 'how_it_works', 'cta_repeat', 'faq', 'waitlist', 'footer'],
    help='Section to edit')
parser.add_argument('--prompt', required=True, help='Edit instruction (e.g., "make headline shorter")')
parser.add_argument('--product', required=True, help='Product idea for AI context')
parser.add_argument('--mock', action='store_true', help='Use mock AI')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full LP regeneration on any edit | Surgical section replacement | Phase 15 | 10x faster edits, preserves other sections |
| Monolithic copy generation | Section-scoped Pydantic schemas | Phase 15 | Smaller prompts, more accurate edits |

## Open Questions

1. **Where to store `product_idea` + `target_audience` for edit context?**
   - What we know: `LandingPageResult` has `product_idea` and `sections` but not `target_audience`. CLI user would need to re-supply `--product`.
   - What's unclear: Should Phase 15 write a `landing-page.json` sidecar next to the HTML with product metadata, so future edits don't need `--product`?
   - Recommendation: Write a `landing-page.json` sidecar in Phase 15. Minimal: `{"product_idea": "...", "target_audience": "...", "sections": [...]}`. CLI reads it automatically if present.

2. **Should the CLI support `--list-sections` to show what sections exist in a given LP?**
   - What we know: `data-section` attributes make it trivial to extract section names via regex.
   - Recommendation: Yes, add `--list` flag as a discovery command. Zero complexity, high UX value.

3. **What happens to `gallery` section edits?**
   - Recommendation: Explicitly exclude from `--section` choices in the CLI. Return a clear message if called programmatically.

## Sources

### Primary (HIGH confidence)
- Phase 14 codebase (verified 2026-02-19):
  - `app/services/landing_page/template_builder.py` — `render_section()`, `get_section_list()`, `section_contexts`
  - `app/services/landing_page/optimizer.py` — `optimize_html()` behavior verified
  - `app/services/landing_page/templates/sections/*.html.j2` — all 9 templates verified for `data-section` attribute and no nested `<section>` tags
  - `app/services/llm_provider/base.py` — `generate_structured()` signature
  - `requirements.txt` — `beautifulsoup4==4.14.3` confirmed present

- Regex replacement approach: tested against real optimized HTML structure during research. Confirmed working.

### Secondary (MEDIUM confidence)
- Phase 14 summaries (14-02-SUMMARY.md, 14-03-SUMMARY.md) for architecture decisions
- Phase 14 CONTEXT.md for locked decisions carried forward

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, no new dependencies
- Architecture: HIGH — all reused Phase 14 patterns, tested regex approach
- Pitfalls: HIGH — derived from direct code inspection of Phase 14 templates and optimizer

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable domain — Phase 14 code won't change)
