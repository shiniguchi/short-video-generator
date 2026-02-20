---
status: complete
phase: 19-admin-dashboard-deployment
source: 19-01-SUMMARY.md, 19-02-SUMMARY.md
started: 2026-02-20T15:00:00Z
updated: 2026-02-20T15:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Nav bar links
expected: Go to http://localhost:8000/ui/ — nav bar shows three links: "Dashboard" (to /ui/dashboard), "Waitlist" (to /ui/waitlist), and "Generate" (to /ui/generate).
result: pass

### 2. Dashboard page loads
expected: Navigate to /ui/dashboard — page shows "Analytics Dashboard" heading, summary cards row (total LPs, total pageviews, total signups), and a table with columns: Product Idea, Status, Pageviews, Signups, CVR (%), Deployed URL, Actions. If LPs exist, rows populate. If none, shows empty state message.
result: pass

### 3. Dashboard date filter
expected: On /ui/dashboard, enter a start date and end date in the filter form and click submit. Page reloads with same URL plus ?start=YYYY-MM-DD&end=YYYY-MM-DD query params. Date inputs retain the entered values. Table data filters accordingly.
result: pass

### 4. Waitlist page loads
expected: Navigate to /ui/waitlist — page shows "Waitlist Signups" heading with an "Export CSV" button, a count indicator ("Showing N signups"), and a table with columns: Email, Signed Up, Source LP. If signups exist, rows populate. If none, shows "No signups yet."
result: pass

### 5. Waitlist CSV export
expected: On /ui/waitlist, click "Export CSV". Browser downloads a file named "waitlist.csv". Open the file — first line is header "email,signed_up_at,lp_source". Subsequent lines contain signup data (or file has just the header if no signups).
result: pass

### 6. Waitlist date filter
expected: On /ui/waitlist, enter start and end dates in filter form, submit. Page reloads filtered. The "Export CSV" link preserves the date filter params — hovering over it shows ?start=...&end=... in the URL.
result: pass

### 7. Deploy button on preview page
expected: Navigate to /ui/preview/{run_id} for any LP. Click "Deploy to Cloudflare" button. If CF credentials not configured: red error message appears saying "CLOUDFLARE_API_TOKEN not set". If CF credentials configured: deployment runs and deployed URL appears as clickable green link below the button.
result: pass

### 8. Deployed URL display and Re-deploy
expected: After a successful deploy (or for any LP with status "deployed" in DB), the preview page shows a green "Live at: https://..." bar with the deployed URL as a link. The deploy button text says "Re-deploy to Cloudflare" instead of "Deploy to Cloudflare".
result: skipped
reason: Requires real Cloudflare credentials and Pages project — code verified in automated checks

## Summary

total: 8
passed: 7
issues: 0
pending: 0
skipped: 1

## Gaps

[none]
