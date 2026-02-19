# Phase 14: Landing Page Generation - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate a production-ready single-file HTML landing page from a product idea, with AI-written copy, embedded video, and waitlist form. The LP is research-driven — AI analyzes top-performing LPs in the same space to inform design and copy. Module reordering/adding/subtracting is Phase 15 (AI Section Editing). Waitlist backend processing is Phase 16.

</domain>

<decisions>
## Implementation Decisions

### LP visual style & structure
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

### Copy generation strategy
- **User inputs**: Product idea + target audience (both required)
- Industry, region, color preference are optional inputs
- **Tone**: Always conversational — friendly, direct, second-person ("you")
- **Research-informed copy**: AI analyzes top LP copy patterns in the same space, uses similar hooks/angles/formulas to generate copy
- **Social proof**: Implied proof only — soft signals like "Join X others" or "Built by the team behind..." — no fake testimonials or fabricated stats

### Video embed & hero layout
- **Video placement**: Claude's discretion, informed by research — follow what top-performing LPs do; research conversion data on placement if available
- **Autoplay behavior**: Autoplay muted + loop (pending research confirmation of best practice)
- **No GIFs** — too slow. Performance is a hard constraint
- **No-video fallback**: Use hero image from product images if video isn't available — LP still looks complete
- **Asset distribution across sections**: Research-driven — Claude investigates optimal asset placement for conversion and decides

### Generation interface & flow
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

</decisions>

<specifics>
## Specific Ideas

- "Research top 10 performing LPs similar to the idea" — design and copy should be data-informed, not template-based
- "Heavily use the images and videos produced for the marketing video" — leverage existing pipeline assets
- "Avoid any slow modules" — performance is a hard constraint, no GIFs, optimize for fast load
- Module system should be ready for Phase 15 to manipulate (reorder, add, subtract sections)

</specifics>

<deferred>
## Deferred Ideas

- Module reordering, adding, and subtracting sections — Phase 15 (AI Section Editing)
- Waitlist form backend processing — Phase 16 (Waitlist Collection)

</deferred>

---

*Phase: 14-landing-page-generation*
*Context gathered: 2026-02-19*
