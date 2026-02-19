# Performance Landing Page Design Checklist

This checklist is used by the LP generation pipeline to ensure every generated landing page
meets conversion best practices. The copy generator and template builder reference this file.

## Hero Section (Above the Fold)

- [ ] **Headline**: 5-8 words, benefit-driven, specific to product (not generic)
- [ ] **Headline**: Uses second-person "you" and addresses a pain point or desire
- [ ] **Subheadline**: 15-25 words, expands on headline with specificity
- [ ] **Layout**: Split layout on desktop (text left, media right). Stacked on mobile (text first).
- [ ] **CTA above fold**: Primary CTA button visible without scrolling on all devices
- [ ] **Hero media**: Product video or high-quality image visible above fold
- [ ] **CTA text**: Action verb + benefit (e.g., "Get Early Access", not just "Submit")
- [ ] **CTA contrast**: Button color contrasts with background (use accent color)
- [ ] **Trust micro-copy**: Small text near CTA — "Free to join" or "No spam, ever"

## Copy Rules

- [ ] **Benefits over features**: Lead with outcomes, not specs
- [ ] **Quantify**: Use numbers ("24-hour cold retention", "30-day battery", "2-minute setup")
- [ ] **Conversational tone**: Second-person, friendly, direct. No corporate jargon.
- [ ] **Scannable**: Short paragraphs, bullet points, bold key phrases
- [ ] **Social proof**: Specific numbers ("Join 2,000+ early adopters"), no fake testimonials
- [ ] **Objection handling**: Preempt doubts ("No credit card required", "Cancel anytime")

## Required Sections (in order)

1. **Hero**: Headline + subheadline + CTA + video/image (split layout)
2. **Benefits**: 3-4 product-specific benefits with product images and quantified outcomes
3. **Gallery**: Product image showcase grid (3-6 images, responsive masonry)
4. **Features**: Technical specs with stat numbers (dark background contrast)
5. **How It Works**: 3-step visual process with product images per step
6. **CTA Repeat**: Mid-page CTA with urgency copy
7. **FAQ**: 3-5 common objections answered
8. **Final CTA**: Waitlist form with email capture + privacy note
9. **Footer**: Minimal — copyright + product name

## Visual Density & Product Images

- [ ] **Use all available images**: Distribute product images across benefits, gallery, and how-it-works
- [ ] **Benefits cards**: Each benefit gets a product image (16:10 aspect, object-fit: cover)
- [ ] **Gallery section**: 3-6 images in responsive grid. First 2 images get tall treatment (span 2 rows)
- [ ] **How-it-works steps**: Each step gets a product photo (portrait 3:4, rounded corners, shadow)
- [ ] **Hero media**: Always show product video or hero image above fold
- [ ] **No text-only sections**: Every major section should have at least one visual element
- [ ] **Image sizing**: Use CSS aspect-ratio + object-fit: cover — never stretch or distort
- [ ] **Lazy loading**: All images below fold use loading="lazy"
- [ ] **Alt text**: Every image has descriptive alt (product name + context)
- [ ] **Image distribution**: Spread images evenly — benefits first, then how-it-works, then gallery

## Visual Design Rules

- [ ] **Color palette**: Max 3 colors (primary, accent, neutral). Accent = CTAs only.
- [ ] **White space**: Generous padding between sections (min 4rem desktop, 3rem mobile)
- [ ] **Visual rhythm**: Alternate section backgrounds (white / light gray / white)
- [ ] **Typography hierarchy**: H1 > H2 > H3 clearly distinct in size and weight
- [ ] **F-pattern**: Key content follows F-pattern scanning (top bar → left column → key points)
- [ ] **Section transitions**: Subtle background color changes between sections
- [ ] **No walls of text**: Max 3 lines per paragraph. Use bullets for lists.

## CTA Button Rules

- [ ] **Size**: Min 48px height, 14px+ padding, 18px+ font
- [ ] **Color**: High contrast accent color, different from any other element
- [ ] **Text**: 2-4 words, action verb first ("Get Access", "Join Free", "Start Now")
- [ ] **Repetition**: CTA appears 3+ times on page (hero, mid-page, bottom)
- [ ] **Hover state**: Visual feedback (scale, shadow, color shift)
- [ ] **Urgency nearby**: Add scarcity text near CTA ("Limited spots", "Early access closing soon")

## Mobile Optimization

- [ ] **Single column**: All content stacks vertically on < 768px
- [ ] **Touch targets**: Min 48x48px for all interactive elements
- [ ] **Font size**: Min 16px for body text (prevents iOS zoom on input focus)
- [ ] **No horizontal scroll**: All content fits within viewport width
- [ ] **Thumb-friendly**: CTA buttons full-width on mobile
- [ ] **Fast load**: Total page < 100KB HTML, images optimized, video lazy-loaded

## Form Design

- [ ] **Minimal fields**: Email only for waitlist (one field = highest conversion)
- [ ] **Inline layout**: Email + button side-by-side on desktop, stacked on mobile
- [ ] **Placeholder text**: "Enter your email" or "your@email.com"
- [ ] **Privacy note**: "We respect your privacy. Unsubscribe anytime."
- [ ] **Success feedback**: Clear confirmation message after submit
- [ ] **Spam prevention**: Honeypot field (off-screen, NOT display:none)

## Technical Requirements

- [ ] **Head order**: charset → viewport → title → meta description → OG tags → style
- [ ] **OG tags**: og:title, og:description, og:image for social sharing
- [ ] **Favicon**: Include favicon link (even if placeholder)
- [ ] **Single file**: All CSS inline, no external resources
- [ ] **CSS minified**: rcssmin optimization applied
- [ ] **Section H2**: Every section (except hero and footer) MUST have an H2 heading
- [ ] **Semantic HTML**: Proper h1/h2/h3 hierarchy, section tags, form labels
- [ ] **Alt text**: All images have descriptive alt attributes
- [ ] **Video**: autoplay muted loop playsinline, poster image fallback

## Conversion Psychology

- **Clarity**: Remove friction. Every element serves the conversion goal.
- **Specificity**: Vague copy kills conversion. Use numbers, product names, real benefits.
- **Urgency**: Limited availability, countdown, or early-access framing.
- **Social proof**: Real or implied numbers reduce doubt.
- **Trust**: Privacy notes, guarantees, and recognizable logos.
- **Visual hierarchy**: Guide the eye headline → media → benefits → CTA → form.

## Anti-Patterns (Never Do)

- Generic headlines ("Transform Your Workflow", "The Future of X")
- Benefits that apply to any product ("Save Time", "Boost Productivity")
- Multiple navigation links (kills conversion — one action only)
- CTA text "Submit" or "Click Here" (zero benefit communicated)
- Walls of text without visual breaks
- Emoji as primary icons at large sizes (use SVG or icon font)
- Same background color for all sections (no visual rhythm)
- Missing privacy note near email form
- Video file > 5MB without lazy loading
- Style tag before viewport meta tag
- Text-only sections when product images are available (use visuals!)
- Raw full-resolution images without CSS sizing (use aspect-ratio + object-fit)
- All images the same size/aspect ratio (vary with tall, square, landscape)
- Clustering all images in one section (spread across benefits, gallery, how-it-works)
- Sections without an H2 heading (every section needs a clear label)
