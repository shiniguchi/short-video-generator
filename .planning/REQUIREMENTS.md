# Requirements: ViralForge

**Defined:** 2026-02-19
**Core Value:** Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

## v2.0 Requirements

Requirements for Smoke Test Platform milestone. Each maps to roadmap phases.

### Landing Page Generation

- [ ] **LP-01**: User can generate a landing page from a product idea input
- [ ] **LP-02**: AI generates LP copy using proven formulas (Pain+Solution+Hook headline, benefits, CTAs)
- [ ] **LP-03**: Generated LP is a single self-contained HTML file with inline CSS
- [ ] **LP-04**: Generated LP is mobile-responsive (viewport meta, thumb-friendly targets, single-column)
- [ ] **LP-05**: Generated LP includes embedded product video in hero section
- [ ] **LP-06**: User can edit individual LP sections via AI prompts after generation (e.g., "make headline shorter", "add urgency")
- [ ] **LP-07**: Generated LP includes waitlist email capture form with honeypot spam prevention

### Waitlist & Email Collection

- [ ] **WAIT-01**: Visitor can submit email via LP waitlist form
- [ ] **WAIT-02**: Email is validated server-side (format + basic domain check)
- [ ] **WAIT-03**: Duplicate emails are rejected with friendly message
- [ ] **WAIT-04**: Visitor sees confirmation message after successful signup
- [ ] **WAIT-05**: Waitlist entries are stored in database with timestamp and source LP

### Cloudflare Deployment

- [ ] **DEPLOY-01**: User can deploy a generated LP to Cloudflare Pages with one action
- [ ] **DEPLOY-02**: Deployed LP is publicly accessible at a Cloudflare Pages URL
- [ ] **DEPLOY-03**: Deployment status is tracked in database (generated, deployed, archived)
- [ ] **DEPLOY-04**: LP includes analytics beacon script before deployment

### Analytics & Tracking

- [ ] **ANLYT-01**: Cloudflare Worker tracks page views per LP (visitor count)
- [ ] **ANLYT-02**: Cloudflare Worker tracks form submissions per LP (signup count)
- [ ] **ANLYT-03**: Analytics data is stored in Cloudflare D1 database
- [ ] **ANLYT-04**: Python backend can query analytics data from D1 via Worker HTTP proxy
- [ ] **ANLYT-05**: Referrer/traffic source is captured with each page view

### Admin Dashboard

- [ ] **DASH-01**: User can view list of all waitlist signups with email and timestamp
- [ ] **DASH-02**: User can see conversion rate per LP (signups / visitors)
- [ ] **DASH-03**: User can export waitlist emails to CSV
- [ ] **DASH-04**: User can filter dashboard data by date range
- [ ] **DASH-05**: Dashboard displays per-LP traffic, signup count, and CVR

### Web UI

- [ ] **UI-01**: User can input product idea via browser form
- [ ] **UI-02**: User can trigger LP generation from the web UI
- [ ] **UI-03**: User can preview generated LP before deployment
- [ ] **UI-04**: User can trigger deployment to Cloudflare from the web UI
- [ ] **UI-05**: User can view all generated LPs and their status in the web UI

## Future Requirements (v2.1+)

### Referral & Growth

- **REF-01**: Each signup gets a unique referral link
- **REF-02**: Referral chain is tracked (who referred whom)
- **REF-03**: Social proof counter on LP ("Join X others")

### Optimization

- **OPT-01**: A/B test multiple LP variants per product idea
- **OPT-02**: Multiple LP templates (video-first, screenshot-first, text-heavy)
- **OPT-03**: UTM parameter tracking for detailed traffic source attribution

### Notifications

- **NOTIF-01**: Webhook notifications on new signup (Slack/email)
- **NOTIF-02**: Daily digest email with signup stats

## Out of Scope

| Feature | Reason |
|---------|--------|
| Rich page builder / WYSIWYG editor | Contradicts single-file HTML philosophy; users edit HTML directly if needed |
| Double opt-in email confirmation | Adds email sending complexity/cost; single opt-in sufficient for smoke test |
| Real-time collaborative editing | Requires WebSockets, conflict resolution; overkill for smoke test workflow |
| Built-in email campaign sending | Users should use proper email tools (Mailchimp, etc.); export CSV instead |
| Heatmaps / session replay | Expensive (Hotjar $31+/mo), privacy concerns; core metrics sufficient |
| Custom domain per LP | DNS management, SSL certs, costs; Cloudflare *.pages.dev subdomain sufficient |
| Payment processing | LPs collect waitlist signups only, no actual purchases |
| Multi-language LPs | English only for all generated content |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LP-01 | — | Pending |
| LP-02 | — | Pending |
| LP-03 | — | Pending |
| LP-04 | — | Pending |
| LP-05 | — | Pending |
| LP-06 | — | Pending |
| LP-07 | — | Pending |
| WAIT-01 | — | Pending |
| WAIT-02 | — | Pending |
| WAIT-03 | — | Pending |
| WAIT-04 | — | Pending |
| WAIT-05 | — | Pending |
| DEPLOY-01 | — | Pending |
| DEPLOY-02 | — | Pending |
| DEPLOY-03 | — | Pending |
| DEPLOY-04 | — | Pending |
| ANLYT-01 | — | Pending |
| ANLYT-02 | — | Pending |
| ANLYT-03 | — | Pending |
| ANLYT-04 | — | Pending |
| ANLYT-05 | — | Pending |
| DASH-01 | — | Pending |
| DASH-02 | — | Pending |
| DASH-03 | — | Pending |
| DASH-04 | — | Pending |
| DASH-05 | — | Pending |
| UI-01 | — | Pending |
| UI-02 | — | Pending |
| UI-03 | — | Pending |
| UI-04 | — | Pending |
| UI-05 | — | Pending |

**Coverage:**
- v2.0 requirements: 31 total
- Mapped to phases: 0
- Unmapped: 31

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after initial definition*
