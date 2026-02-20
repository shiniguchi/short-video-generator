# Pitfalls Research

**Domain:** Adding per-stage review workflow UI to existing ViralForge CLI video pipeline
**Researched:** 2026-02-20
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: In-Memory Job State Evaporates on Worker Restart

**What goes wrong:**
The current `_jobs` dict in `router.py` stores generation progress in process memory. Any server restart, Docker container redeploy, or Uvicorn worker reload wipes every active job. SSE clients get `{"status": "not_found"}` and the user sees a stalled progress bar with no recovery path.

**Why it happens:**
`asyncio.create_task(_run_generation(...))` runs inside the FastAPI process — not in Celery. When the process dies mid-generation, the task dies with it. The `_jobs` dict is module-level, so it is also not shared between multiple Uvicorn worker processes (`--workers 2` would cause each process to have a separate dict and SSE clients could hit a different worker than the one running the task).

**How to avoid:**
- Persist job state to PostgreSQL immediately when a task starts, fails, or completes. `LandingPage.status` already exists — add a `generation_log` JSON column for progress messages.
- Use the existing Celery infrastructure for long-running tasks. The LP generation pipeline should be a Celery task, not an `asyncio.create_task`. SSE polls the DB for status, not the in-memory dict.
- Run Uvicorn with a single worker (`--workers 1`) if keeping in-memory approach for MVP, and document the constraint.

**Warning signs:**
- SSE progress bar freezes with no error on browser reload
- Server logs show "Job not found" after restart
- Docker Compose `restart: unless-stopped` causes silent job loss

**Phase to address:**
Review Workflow UI foundation phase — before any video review features are built

---

### Pitfall 2: Approved Stage State Lost When Regeneration Fires

**What goes wrong:**
User approves scenes 1–3, rejects scene 4. Regeneration request triggers. The regeneration code overwrites the entire `Script.scenes` JSON array, discarding scene 1–3 approval state. User must re-review all scenes again.

**Why it happens:**
The CLI pipeline treats generation output as a complete unit — all scenes are produced together and the whole script is saved atomically. There is no concept of partial approval. When a stage reruns, it writes a fresh output, not a delta.

**How to avoid:**
- Store per-scene approval state separately from the generated content. Add a `scene_reviews` JSON column to `Script` or a separate `SceneReview` table: `{scene_index, status, reviewed_at, reviewer_note}`.
- Regeneration should produce a candidate, not overwrite. New scenes are stored alongside the original. User picks which version to keep.
- Never mutate approved content in place. The regeneration output is a new row or a new entry in a `candidates` array.

**Warning signs:**
- Approve/reject actions modify `Script.scenes` directly
- Regeneration task ID matches the original task ID (overwrite not candidate)
- No `reviewed_at` timestamp exists in the data model

**Phase to address:**
Per-scene review state phase — before the regeneration loop is wired

---

### Pitfall 3: SSE Stream Leaks When Browser Tab Closes

**What goes wrong:**
User opens progress page, closes the tab while generation runs. The SSE generator function (`event_stream()`) keeps looping for up to 120 seconds, holding a database connection and asyncio coroutine. With 10 concurrent users, 10 × 120s = 20 minutes of leaked connections per batch.

**Why it happens:**
The current implementation uses `for _ in range(120)` with `await asyncio.sleep(1)`. When the browser closes the SSE connection, FastAPI/Starlette raises `anyio.EndOfStream` or `CancelledError` in the generator. If uncaught, the generator keeps running until the loop exits.

**How to avoid:**
- Wrap the SSE generator body in `try/except (anyio.EndOfStream, asyncio.CancelledError, GeneratorExit)` and `return` immediately on disconnect.
- Add a short-circuit: check `await request.is_disconnected()` at the top of each loop iteration.
- Set a shorter polling interval + max duration that matches the real pipeline duration (LP gen takes ~30–60s, not 120s).

**Warning signs:**
- Uvicorn shows open connections that never close after tab closes
- PostgreSQL `pg_stat_activity` shows idle connections held longer than pipeline duration
- Memory grows proportional to concurrent SSE connections

**Phase to address:**
Review Workflow UI foundation phase — SSE disconnect handling must be in the first SSE endpoint

---

### Pitfall 4: Video Files Served via StaticFiles Won't Seek in Browser

**What goes wrong:**
`<video src="/static/output/video.mp4">` works for playback but scrubbing/seeking fails. Browser sends HTTP Range requests (`Range: bytes=1000000-2000000`). FastAPI's `StaticFiles` does support range requests, but a custom `FileResponse` route without proper `Accept-Ranges`, `Content-Range`, and `206 Partial Content` handling will make the browser unable to seek.

**Why it happens:**
Developers add a `/media/{path}` route returning `FileResponse`. `FileResponse` in FastAPI does handle range requests — but only if the route does not process the file through `StreamingResponse` first (e.g., loading bytes into memory and re-streaming). The moment you do `open(path, 'rb').read()` and return as `StreamingResponse`, you lose range support and load potentially 100MB+ into worker memory.

**How to avoid:**
- Use `FileResponse` directly for video files — it handles range requests natively.
- Mount the output directory as `StaticFiles` — simpler, built-in range support: `app.mount("/media", StaticFiles(directory="output"), name="media")`.
- Never load video bytes into memory. Serve the file path, not the file content.
- Set correct MIME type: `video/mp4` for .mp4. Without it, Chrome will not play the file inline.

**Warning signs:**
- Video plays from the start but scrub bar is unresponsive
- Network tab shows `200 OK` response for video, not `206 Partial Content`
- Server memory spikes when preview page loads

**Phase to address:**
Video preview phase — first time any video file is served via the UI

---

### Pitfall 5: Mock/Real AI Toggle State Not Isolated Per Request

**What goes wrong:**
User A submits form with `mock=True`. User B submits form with `mock=False`. The factory function `get_video_generator()` reads from `settings` which is a module-level singleton. If settings are mutated (e.g., `settings.use_mock = True` based on form input), User B's generation runs in mock mode.

**Why it happens:**
The existing provider pattern reads from `get_settings()` which returns a cached singleton via `@lru_cache`. The form's `mock` checkbox must influence which provider is selected — but if that influence flows through global settings mutation rather than per-request injection, requests bleed into each other.

**How to avoid:**
- Pass `use_mock: bool` as an explicit argument through the call stack — do not mutate `settings`.
- The existing codebase already does this correctly for LP generation (`generate_landing_page(request, use_mock=use_mock)`). Apply the same pattern to video generation.
- Review factory functions: `get_video_generator()`, `get_voiceover_generator()`, `get_avatar_generator()`. Each must accept `use_mock` as a parameter, not read it from global settings.
- Add a test: submit two concurrent requests with different mock flags, verify providers are isolated.

**Warning signs:**
- Real AI calls appear in logs when mock mode was selected (or vice versa)
- API costs appear on Gemini/HeyGen dashboard for runs labeled as mock
- `get_settings()` is called inside a factory without passing `use_mock` as override

**Phase to address:**
Mock/real toggle phase — before any video generation is triggered from the web UI

---

### Pitfall 6: Multi-Stage SSE Reconnects Replay From Wrong Position

**What goes wrong:**
Video generation has 5 stages: trend collection → analysis → content generation → composition → review. Each stage takes 1–5 minutes. If the browser reconnects (tab switch, network blip), the SSE stream restarts from wherever the server's generator left off. If the generator tracks stage index in local variables, the client cannot recover its position — it either replays from the beginning or misses stages entirely.

**Why it happens:**
The current LP generation SSE tracks progress with hardcoded numbers (`_jobs[job_id]["progress"] = 10`, `= 20`, etc.). For multi-stage video pipelines with async Celery tasks, stage completion events are not captured in the SSE generator's local state — they happen in a separate Celery worker process. The SSE generator has no awareness of what happened between reconnects.

**How to avoid:**
- Store stage completion in the database (`Job.extra_data["completed_stages"]` already exists in `pipeline.py`). SSE generator queries DB each tick — it reads current state, not local variables.
- SSE messages include the full current state, not deltas: `{"stage": "composition", "completed": ["trend_collection", "trend_analysis", "content_generation"], "progress": 60}`. Client rebuilds UI from each message.
- Use `Last-Event-ID` header support so clients can resume from a specific event ID — though DB polling approach makes this unnecessary.

**Warning signs:**
- Progress bar resets to 0% on browser reconnect
- SSE generator has local variables like `stage_index = 0` or `completed_count = 0`
- Stage completion events are only tracked inside the Celery task, not written to DB

**Phase to address:**
Multi-stage pipeline SSE phase — design the SSE → DB polling pattern first, before wiring stages

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `_jobs` in-memory dict for video review | Works for single-process local dev, zero infra | Lost on restart, breaks with multiple workers, untraceable in logs | Local dev only, never if Docker restarts are possible |
| Store per-scene approval state in `Script.scenes` JSON alongside content | One column, no migration | Regeneration overwrites approval state, no audit trail | Never — approval state must be separate from content |
| `FileResponse` with file loaded into bytes first | Simpler code, works for small files | Loads 100MB+ into memory, no range request support, video seeking breaks | Never for video — always use path-based `FileResponse` or `StaticFiles` |
| Mutate `settings.use_mock` per request | Simple toggle, no refactor needed | Global state leak, concurrent requests interfere, breaks mock isolation | Never — pass `use_mock` as explicit argument |
| SSE stream with hardcoded progress percentages | Simple to implement | Doesn't reflect real stage durations, disconnects lose position | Acceptable for single-stage <30s tasks; avoid for multi-stage pipelines |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| CLI pipeline → web UI | Wrap CLI `main()` call in `asyncio.create_task` | Dispatch as Celery task; SSE polls DB for status |
| asyncio.create_task → background generation | Assume task survives server restart | Task dies with process — must use Celery or persist checkpoint to DB |
| Video file → browser `<video>` tag | Return `StreamingResponse(open(path, 'rb').read())` | Return `FileResponse(path, media_type="video/mp4")` |
| Per-scene approval → regeneration | Write new scene into same `scenes[i]` index | Write candidate to separate column; user promotes to approved |
| Mock toggle → form checkbox | Set `settings.use_mock = form_value` | Pass `use_mock=True/False` as function argument through call chain |
| Celery task → SSE progress | Publish events via Redis pub/sub or SSE directly from worker | Write stage progress to DB; SSE generator polls DB — simpler, no pub/sub dependency |
| Multi-stage pipeline → SSE reconnect | Track stage in SSE generator local variable | Read stage from DB on every poll tick; send full state snapshot not deltas |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| SSE polling too aggressively | High DB query load, Postgres CPU spikes | Poll every 2–3s not 100ms; pipeline stages take minutes not milliseconds | >5 concurrent review sessions with 500ms polling |
| Video file served through Python for preview | Server memory spikes, slow load, range requests fail | Serve via `StaticFiles` mount or `FileResponse`, not byte streaming | Any video >20MB |
| Loading all videos for review page at once | Page load timeout, OOM on large output directories | Paginate: load 20 most recent videos; lazy-load thumbnails | >100 videos in output/ directory |
| AI regeneration triggers without debounce | Same scene regenerated multiple times on double-click | Disable submit button immediately on click; backend: check if regeneration already running for this job | First click during network lag |
| Concurrent SSE connections with asyncio.sleep(1) hold event loop | All other async operations slow down under load | `asyncio.sleep` yields control — generally fine, but limit max concurrent SSE connections with a semaphore | >50 concurrent SSE streams |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Serving `output/` directory via `StaticFiles` without path traversal protection | `GET /media/../../../etc/passwd` exposes server files | Use `StaticFiles(directory="output", check_dir=True)`; never construct file paths from raw user input |
| No auth on regeneration endpoints | Unauthenticated user triggers expensive AI calls | Rate limit regeneration: 1 per job per 30 seconds; require session or API key |
| Job IDs are sequential integers exposed in URL | Enumeration attack — user hits `/jobs/1` through `/jobs/100` to see all jobs | Use UUIDs for job IDs (already done with `uuid4().hex[:8]` — keep this) |
| Mock flag accepted from form without cost guard | User submits `mock=False` on free tier, triggers real AI for thousands of scenes | Add cost estimate before real AI runs; require explicit confirmation for real generation |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Approve all" immediately moves to next stage with no undo | User accidentally approves bad frames with no rollback | Keep approved frames in `pending_submission` state for 30s; show "Undo" button before committing |
| Regeneration replaces preview immediately | User can't compare old vs new scene | Show side-by-side diff: original on left, candidate on right; user picks one |
| Progress bar at 100% with no next action prompt | User doesn't know what to do after generation completes | Auto-redirect to review page or show prominent "Review Scenes" CTA immediately on completion |
| Video preview shows spinner indefinitely if MIME type wrong | User thinks video is still loading; actually a browser error | Check browser console error explicitly; show "Preview unavailable" fallback with file download link |
| Review state not shown during regeneration | User submits another regeneration request thinking the first one stalled | Lock the "Regenerate" button for the scene currently being processed; show spinner with "Regenerating scene 3..." |

---

## "Looks Done But Isn't" Checklist

- [ ] **In-memory job dict:** Often survives local dev but breaks on Docker restart — verify by restarting the container mid-generation and checking if the job recovers
- [ ] **Video seek in browser preview:** Often plays from start but seek fails — verify by opening the video and clicking the middle of the scrub bar
- [ ] **Per-scene approval state:** Often stored inside `scenes[i]` alongside content — verify that regenerating one scene doesn't reset approval flags on other scenes
- [ ] **SSE disconnect handling:** Often the generator loops until timeout — verify by opening the progress page then closing the tab; check server logs for "connection closed" vs continued polling
- [ ] **Mock flag isolation:** Often reads from global settings — verify by submitting two concurrent requests with different mock flags and checking which provider is invoked
- [ ] **Multi-stage SSE resume:** Often restarts progress from 0% on reconnect — verify by opening progress page, closing tab, reopening it; progress should reflect current stage
- [ ] **File serving range requests:** Often returns 200 not 206 for video — check network tab; `206 Partial Content` required for seek to work

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| In-memory job state lost on restart | MEDIUM | 1. Check DB for last known `LandingPage.status`, 2. Surface "Generation interrupted" state in UI, 3. Provide "Retry generation" button that resumes from last DB checkpoint |
| Approved scene state overwritten by regeneration | HIGH | 1. Restore from DB backup (if backup exists), 2. User must re-review from scratch, 3. Add audit log table as preventive measure |
| SSE stream leaking connections | LOW | 1. Restart Uvicorn process, 2. Add `try/except GeneratorExit` to SSE generator, 3. Deploy fix |
| Video preview broken by wrong MIME type | LOW | 1. Add `media_type="video/mp4"` to `FileResponse`, 2. Or switch to `StaticFiles` mount — single line change |
| Mock/real provider bleed | MEDIUM | 1. Check AI provider API logs for unexpected calls, 2. Trace `use_mock` through call stack to find where it's read from settings, 3. Refactor to pass as argument |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| In-memory job state lost on restart | Review Workflow UI foundation | Restart container mid-generation, verify job status reads from DB not memory |
| Approved scene state overwritten | Per-scene review state phase | Reject scene 2, regenerate scene 2, verify scenes 1/3 approval unchanged |
| SSE stream disconnect leak | Review Workflow UI foundation | Close browser tab mid-stream, check server has no lingering SSE coroutines after 5s |
| Video seek broken | Video preview phase | Open video preview, seek to 50% mark, verify playback from new position |
| Mock/real provider bleed | Mock/real toggle phase | Send two concurrent requests (mock=True, mock=False), verify separate provider logs |
| Multi-stage SSE reconnect position loss | Multi-stage pipeline SSE phase | Close tab at stage 3 of 5, reopen, verify progress shows stage 3 not stage 1 |
| File path traversal via media endpoint | Video preview phase | Attempt `GET /media/../../../etc/passwd`, verify 404 or 403 |

---

## Sources

- [FastAPI Long-Running Background Tasks Discussion](https://github.com/fastapi/fastapi/discussions/7930) — confirms in-memory task state loss on restart
- [Understanding Pitfalls of Async Task Management in FastAPI](https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests) — task accumulation and state management
- [FastAPI Streaming Large Files Discussion](https://github.com/fastapi/fastapi/discussions/8229) — range request support requirements for video
- [Chrome OOM with FileResponse for large files](https://github.com/fastapi/fastapi/discussions/6464) — memory loading pitfall confirmed
- [Streaming Video with FastAPI](https://stribny.name/posts/fastapi-video/) — correct range request handling pattern
- [HTTP Range Requests and 206 Partial Content — MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/MIME_types) — MIME type requirement for video playback
- [FastAPI memory leak — GitHub discussion](https://github.com/fastapi/fastapi/discussions/11079) — connection leak patterns with long-lived generators
- Existing codebase: `app/ui/router.py` — in-memory `_jobs` dict confirmed as current implementation
- Existing codebase: `app/pipeline.py` — `completed_stages` in `Job.extra_data` confirmed as existing checkpoint pattern

---

*Pitfalls research for: ViralForge — Adding review workflow UI to existing CLI pipeline*
*Researched: 2026-02-20*
*Focus: Integration pitfalls when wiring CLI video pipeline into web UI with per-stage review, regeneration loops, video file serving, mock/real toggle, and multi-stage SSE*
