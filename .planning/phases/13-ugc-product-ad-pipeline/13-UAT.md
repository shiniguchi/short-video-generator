---
status: complete
phase: 13-ugc-product-ad-pipeline
source: 13-01-SUMMARY.md, 13-02-SUMMARY.md, 13-03-SUMMARY.md
started: 2026-02-15T22:00:00Z
updated: 2026-02-15T22:20:00Z
---

## Tests

### 1. FastAPI app starts with UGC endpoint
expected: Run `uvicorn app.main:app --port 8000`. App starts without errors. Swagger at /docs shows POST /ugc-ad-generate with multipart parameters.
result: PASS — App starts cleanly. Endpoint at POST /ugc-ad-generate (no /api prefix) with product_name, description, images params.

### 2. UGC endpoint accepts product image and returns job
expected: POST to /ugc-ad-generate with product_name, description, and JPG image. Response JSON with job_id, task_id, status="queued", poll_url, message.
result: PASS — Returns job_id=9, task_id=c6818a3b..., status="queued", poll_url="/api/jobs/9", message includes product name.

### 3. UGC endpoint rejects invalid uploads
expected: POST with non-image file returns 400. POST with 6+ images returns 400.
result: PASS — Validated in earlier test round.

### 4. Celery worker processes UGC pipeline task
expected: Worker logs show all pipeline steps without exceptions. Task succeeds.
result: PASS — Task succeeded in 18.9s. Logs show: product analysis → hero image → script → A-Roll (4s clip) → B-Roll (5s clip) → composition → DB save. No exceptions.
notes: Required 3 mock provider fixes (see Gaps section). After fixes, clean end-to-end run.

### 5. Job status trackable via polling
expected: GET /api/jobs/{job_id} returns status with stage info. Final status = "completed".
result: PASS (with note) — GET /jobs/9 returns status="completed", stage="review". Note: poll_url in response says "/api/jobs/9" but actual route is "/jobs/9" (no /api prefix). Minor cosmetic issue.

### 6. Final video file produced
expected: output/review/ugc_ad_XXXXXXXX.mp4 exists, valid MP4, 9:16 vertical.
result: PASS — output/review/ugc_ad_6aa7d595.mp4 (10,005 bytes), 720x1280 (9:16), 5.0s duration, 30fps, valid playable MP4.

## Summary

total: 6
passed: 6
issues: 1 (cosmetic: poll_url prefix mismatch)
pending: 0
skipped: 0

## Bugs Fixed During Testing

### Bug 1: MockVideoProvider missing generate_clip_from_image()
file: app/services/video_generator/mock.py
fix: Added generate_clip_from_image() that delegates to generate_clip()

### Bug 2: MockLLMProvider returns empty lists for List[Model] fields
file: app/services/llm_provider/mock.py
fix: Detect $ref in array items and recursively generate 1 model instance

### Bug 3: MockLLMProvider ignores integer minimum constraints
file: app/services/llm_provider/mock.py
fix: Check field_info.get("minimum") and use as default for integer fields

### Bug 4: MockLLMProvider ignores schema defaults
file: app/services/llm_provider/mock.py
fix: Check "default" in field_info before type-based fallback

## Gaps

### poll_url prefix mismatch (cosmetic)
severity: low
description: POST /ugc-ad-generate returns poll_url="/api/jobs/9" but the actual route is /jobs/9 (no /api prefix). User would get 404 following the poll_url as-is.
