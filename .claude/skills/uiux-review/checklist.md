# UI/UX Review Checklist

Concrete thresholds for each review category.

---

## P1: Accessibility (CRITICAL)

| ID | Rule | Threshold |
|----|------|-----------|
| A1 | Color contrast (text on background) | >= 4.5:1 normal, >= 3:1 large (18px+) |
| A2 | Focus ring visible on Tab navigation | Must be visible on all interactive elements |
| A3 | Icon-only buttons have `aria-label` | 0 violations |
| A4 | Form inputs have `<label>` or `aria-label` | 0 violations |
| A5 | Tab order matches visual reading order | Left-to-right, top-to-bottom |
| A6 | Heading hierarchy sequential | No h1 → h3 skips |
| A7 | Color not sole state indicator | Must also use icon/text/shape |
| A8 | Images have `alt` text | 0 missing (decorative: `alt=""`) |

## P2: Interaction (CRITICAL)

| ID | Rule | Threshold |
|----|------|-----------|
| I1 | Touch target size | >= 44x44px |
| I2 | Clickable elements have `cursor: pointer` | All buttons, links, clickable cards |
| I3 | Buttons disable during async ops | No double-submit |
| I4 | Error messages near the problem field | Not only top-of-page banners |
| I5 | Hover state on interactive elements | Visible change (color/shadow/scale) |
| I6 | Active/pressed feedback | Visual response within 100ms |
| I7 | Loading states for async content | Skeleton or spinner |
| I8 | Empty states have guidance | Not blank — show message or CTA |

## P3: Layout & Responsive (HIGH)

| ID | Rule | Threshold |
|----|------|-----------|
| L1 | No horizontal scrollbar | At 1440, 768, 375px |
| L2 | Body text on mobile | >= 16px |
| L3 | Spacing on consistent scale | 4/8/12/16/24/32/48px |
| L4 | Mobile navigation adapts | Hamburger or bottom nav |
| L5 | Content max-width consistent | Same across pages |
| L6 | Images scale proportionally | No stretch or overflow |
| L7 | No content behind fixed headers | Scroll padding applied |

## P4: Typography (HIGH)

| ID | Rule | Threshold |
|----|------|-----------|
| T1 | Body line height | 1.5 - 1.75 |
| T2 | Line length | 65-75 chars max |
| T3 | Visual hierarchy clear | H1 > H2 > H3 > body distinguishable |
| T4 | Font weights consistent | Max 3 weights per family |
| T5 | Body text dark enough | Not gray-400 on white |
| T6 | No text walls | Break with headings, lists, whitespace |

## P5: Color & Visual (MEDIUM)

| ID | Rule | Threshold |
|----|------|-----------|
| C1 | Primary action color distinct | One clear CTA color |
| C2 | Destructive actions use warning color | Red/orange for delete |
| C3 | Disabled elements visually muted | Reduced opacity or gray |
| C4 | Consistent border/shadow treatment | Same style for similar components |
| C5 | Palette limited | Primary + secondary + neutral + semantic |

## P6: Animation & Performance (MEDIUM)

| ID | Rule | Threshold |
|----|------|-----------|
| P1 | Transition duration | 150-300ms |
| P2 | Animate `transform`/`opacity` only | Not width/height/top/left |
| P3 | Respect `prefers-reduced-motion` | Disable animations when set |
| P4 | No layout shift on load | Space reserved for async content |

## P7: Consistency (MEDIUM)

| ID | Rule | Threshold |
|----|------|-----------|
| S1 | Same components look identical | Buttons, cards, inputs uniform |
| S2 | Icon style uniform | All outline OR all filled |
| S3 | No emoji as functional icons | Use SVG icons |
| S4 | Section spacing uniform | Same gap for same-level sections |
| S5 | Border radius consistent | Small (4-6px inputs), medium (8-12px cards) |
