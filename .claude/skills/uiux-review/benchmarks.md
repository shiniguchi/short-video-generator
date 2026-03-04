# UI/UX Benchmarks

Top-tier patterns to compare against during review. These represent current best practices from leading SaaS/creator tools.

---

## Dashboard Patterns

**Best-in-class**: Linear, Vercel, Notion

| Pattern | What they do right |
|---------|-------------------|
| Card grid | Clean cards with subtle shadows, consistent padding (24px), clear hierarchy |
| Status indicators | Dot + text label, never color alone |
| Empty states | Illustration + clear CTA, not blank space |
| Data density | Show key metrics without clutter, progressive disclosure |
| Quick actions | Hover-reveal action buttons on rows/cards |

## List / Table Pages

**Best-in-class**: Linear, Notion, GitHub

| Pattern | What they do right |
|---------|-------------------|
| Bulk actions | Sticky bar appears on selection, clear count + actions |
| Filtering | Inline filter chips, not hidden in dropdown menus |
| Sorting | Click column headers, clear sort direction indicator |
| Pagination | Infinite scroll or simple prev/next, not complex page numbers |
| Row hover | Subtle background change + action reveal |

## Form / Creation Flows

**Best-in-class**: Stripe, Clerk, Typeform

| Pattern | What they do right |
|---------|-------------------|
| Progressive disclosure | Show fields as needed, not all at once |
| Inline validation | Validate on blur, show error below field immediately |
| Smart defaults | Pre-fill sensible values, reduce friction |
| Clear CTAs | One primary action, secondary actions less prominent |
| Step indicators | Show progress in multi-step flows |

## Review / Detail Pages

**Best-in-class**: Figma, GitHub PR review, Notion

| Pattern | What they do right |
|---------|-------------------|
| Side-by-side compare | Before/after or original/edited views |
| Inline editing | Click to edit, not separate edit page |
| Comment/feedback | Contextual annotations, not separate feedback form |
| Stage progress | Clear visual pipeline showing current stage |
| Action hierarchy | Primary approve/reject prominent, secondary actions tucked |

## Landing Pages

**Best-in-class**: Webflow showcases, Framer templates, Stripe

| Pattern | What they do right |
|---------|-------------------|
| Hero section | Clear headline (max 8 words), subhead, single CTA |
| Social proof | Logos, testimonials, or metrics near the fold |
| Visual rhythm | Alternating section layouts, consistent spacing |
| Mobile-first | Content reflows gracefully, no pinch-zoom needed |
| Fast load | Optimized images, minimal JS, instant paint |

## Video / Media Review

**Best-in-class**: Frame.io, Vimeo Review, Loom

| Pattern | What they do right |
|---------|-------------------|
| Video player | Clean controls, no clutter over content |
| Timeline interaction | Scrubable, clickable markers for key moments |
| Version history | Clear before/after, easy rollback |
| Export/share | One-click actions, clear format options |

---

## Cross-Cutting Principles

These apply to every page:

1. **Whitespace is a feature** — generous padding, breathing room between sections
2. **One action per screen** — clear what the user should do next
3. **Instant feedback** — every click produces visible response within 100ms
4. **Forgiving design** — undo > confirm dialogs, non-destructive defaults
5. **Progressive disclosure** — show essentials first, details on demand
6. **Consistent motion** — same easing (ease-out), same duration (200ms) everywhere
7. **Mobile isn't an afterthought** — test at 375px first, expand up
