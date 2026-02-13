---
phase: 02-trend-intelligence
plan: 02
subsystem: trend-intelligence
tags: [scrapers, api-integration, engagement-metrics, celery-tasks, upsert]
dependency_graph:
  requires: [02-01]
  provides: [tiktok-scraper, youtube-scraper, engagement-velocity, trend-collector, collection-task]
  affects: [02-03]
tech_stack:
  added: []
  patterns: [mock-data-cycling, retry-with-tenacity, sqlite-upsert, sync-async-bridge]
key_files:
  created:
    - app/scrapers/base.py
    - app/scrapers/tiktok.py
    - app/scrapers/youtube.py
    - app/services/__init__.py
    - app/services/engagement.py
    - app/services/trend_collector.py
  modified:
    - app/tasks.py
    - app/api/routes.py
decisions:
  - "Use httpx.Client() for synchronous Apify REST API calls (not apify-client library) to avoid async complexity in Celery tasks"
  - "Cycle mock data entries with modified external_ids (_dup_N suffix) to reach requested limit when mock fixtures < limit"
  - "Calculate engagement velocity at collection time and store in DB for query performance (not computed on-the-fly)"
  - "Use SQLite dialect-specific insert().on_conflict_do_update() for UPSERT on (platform, external_id)"
  - "Isolate platform collection errors - TikTok failure doesn't prevent YouTube collection"
  - "Minimum 0.1 hour (6 minutes) threshold in velocity calculation prevents division by zero for very recent posts"
metrics:
  duration: 323 seconds
  completed: 2026-02-13
---

# Phase 02 Plan 02: Trend Collection Pipeline - Scrapers, Engagement, UPSERT, Celery Task

**One-liner:** Working trend collection pipeline with TikTok/YouTube scrapers (mock/real API switching), engagement velocity calculator, SQLite UPSERT deduplication, Celery orchestration task, and REST API endpoints for triggering collection and querying trends.

## Objective

Build the complete "collect" half of trend intelligence: platform-specific scrapers with mock/real mode switching, engagement velocity calculation, database UPSERT operations to prevent duplicates, Celery task for orchestrated collection, and API endpoints for triggering and querying trends.

**Why this matters:** This plan creates the data ingestion pipeline that feeds all downstream trend analysis. The scrapers normalize data from different platforms into a unified format, engagement velocity provides a time-adjusted popularity metric, UPSERT ensures data freshness without duplicates, and the Celery task enables scheduled automated collection.

## Tasks Completed

### Task 1: TikTok and YouTube scrapers with mock/real switching

**Commit:** `8eb8883`

**What was done:**

1. **Created app/scrapers/base.py - shared utilities:**
   - `load_mock_data(filename)` helper loads JSON fixtures from mock_data/ directory
   - Centralized mock data loading for all scrapers
   - Logs count of loaded items for debugging

2. **Created app/scrapers/tiktok.py - TikTok scraper:**
   - Main entry: `scrape_tiktok_trends(limit=50)` returns normalized trend dicts
   - Mock mode: Loads from `tiktok_trending.json`, cycles entries to reach limit
   - Real mode: Uses Apify REST API (lexis-solutions~tiktok-trending-videos-scraper actor)
   - API flow: POST to start run → poll status with 10s intervals → fetch dataset items → normalize
   - Normalization maps Apify response fields to TrendCreate schema
   - Retry with `tenacity`: 3 attempts, exponential backoff (2x multiplier, 4-60s wait), retries on HTTP errors
   - Uses `httpx.Client()` for synchronous API calls (Celery tasks are sync)
   - Graceful error handling: returns empty list on total failure (doesn't crash task)

3. **Created app/scrapers/youtube.py - YouTube Shorts scraper:**
   - Main entry: `scrape_youtube_shorts(limit=50)` returns normalized trend dicts
   - Mock mode: Loads from `youtube_shorts.json`, cycles entries to reach limit
   - Real mode: Uses YouTube Data API v3 with `googleapiclient.discovery`
   - API flow: search().list() for short videos from last 7 days → videos().list() for details → filter duration < 60s
   - Normalization handles YouTube specifics: shares=0 (API doesn't expose), sound_name="" (not available), tags→hashtags
   - Duration parsed with `isodate.parse_duration()` and filtered to actual Shorts
   - Same retry configuration as TikTok scraper
   - Synchronous function (uses regular googleapiclient, not async)

4. **Mock data cycling logic:**
   - When limit > fixture count, duplicate entries with modified `external_id` (append `_dup_1`, `_dup_2`, etc.)
   - Ensures scrapers can return any requested limit even with small fixture sets
   - Preserves all other fields (engagement numbers, timestamps) for realistic testing

**Key files:**
- `app/scrapers/base.py` - 18 lines, load_mock_data() helper
- `app/scrapers/tiktok.py` - 167 lines, Apify integration + mock mode
- `app/scrapers/youtube.py` - 152 lines, YouTube Data API v3 + mock mode

**Verification:**
- Both scrapers return exactly 5 trends in mock mode when limit=5
- All trends have required fields: external_id, title, posted_at
- YouTube Shorts all have duration < 60 seconds
- No API calls made in mock mode (USE_MOCK_DATA=true default)

### Task 2: Engagement velocity calculator and database UPSERT operations

**Commit:** `d4e4220`

**What was done:**

1. **Created app/services/__init__.py:**
   - Package marker for services module

2. **Created app/services/engagement.py - engagement metrics:**
   - `calculate_engagement_velocity(trend_dict)` implements formula: `(likes + comments + shares) / hours_since_posted`
   - Parses ISO timestamp from `posted_at` field (handles both 'Z' and '+00:00' formats)
   - Calculates hours since posted using current UTC time
   - Minimum threshold: 0.1 hours (6 minutes) prevents division by zero for very recent posts
   - Returns float rounded to 2 decimal places
   - Graceful handling: defaults likes/comments/shares to 0, returns 0.0 if posted_at missing
   - `enrich_trends_with_velocity(trends)` adds velocity to each trend dict and sorts descending
   - Python 3.9 compatible: uses `from typing import List, Dict`

3. **Created app/services/trend_collector.py - DB save + orchestration:**
   - `async def save_trends(trends, platform)` handles UPSERT to database
   - Adds `platform` field to each trend dict before Pydantic validation
   - Validates each trend with TrendCreate schema
   - Uses `sqlalchemy.dialects.sqlite.insert` for SQLite-specific UPSERT
   - `on_conflict_do_update()` on (platform, external_id) prevents duplicates
   - On conflict, UPDATE: title, description, views, likes, comments, shares, engagement_velocity
   - Does NOT update collected_at on conflict (preserves first collection time)
   - Commits all inserts in single transaction
   - Returns count of saved/updated trends
   - `async def collect_all_trends()` orchestrates both platforms
   - Calls both scrapers (sync functions), enriches with velocity, saves to DB (async)
   - Error isolation: TikTok failure doesn't prevent YouTube collection
   - Returns dict with counts: `{"tiktok": 50, "youtube": 45}`

**Key files:**
- `app/services/engagement.py` - 72 lines, velocity calculation with edge case handling
- `app/services/trend_collector.py` - 110 lines, UPSERT logic + orchestration

**Verification:**
- Velocity calculation accurate within 1.0 margin (allows for time drift during test execution)
- Velocity for trend without posted_at returns 0.0 (graceful handling)
- Enrichment adds engagement_velocity field to all trends and sorts descending
- Full collection pipeline saves trends to database (tiktok: 50, youtube: 50)
- Running collection twice produces same DB count (UPSERT prevents duplicates)
- 100 trends after first run, 100 trends after second run (not 200) - UPSERT working

### Task 3: Celery collection task and API endpoint

**Commit:** `f149ed1`

**What was done:**

1. **Updated app/tasks.py - added collection task:**
   - Kept existing `test_task` for Celery verification
   - Added `collect_trends_task` with comprehensive retry configuration:
     - `bind=True` for access to task instance (retry count)
     - `name='app.tasks.collect_trends_task'` for explicit task routing
     - `max_retries=3` allows up to 3 automatic retries
     - `autoretry_for=(Exception,)` retries on any exception
     - `retry_backoff=True` enables exponential backoff
     - `retry_backoff_max=600` caps backoff at 10 minutes
     - `retry_jitter=True` adds randomization to prevent thundering herd
   - Task wraps async `collect_all_trends()` with `asyncio.run()` (Celery tasks are sync)
   - Logs start (with retry attempt number) and completion (with counts)
   - Returns `{"status": "success", "collected": {"tiktok": N, "youtube": N}}`
   - Logs errors before re-raising for retry

2. **Updated app/api/routes.py - added trend endpoints:**
   - Added `Optional` import from typing for Python 3.9 compatibility
   - Added `select` import from sqlalchemy for query building
   - `POST /collect-trends`: Triggers Celery collection task
     - Returns task_id for tracking, status "queued", description of what's being collected
     - Does not wait for task completion (async queuing)
   - `GET /trends`: Lists collected trends with optional filtering
     - Query parameters: `platform` (optional, filters to tiktok/youtube), `limit` (default 50)
     - Orders by collected_at descending (newest first)
     - Returns count + array of trend objects
     - Trend objects include: id, platform, external_id, title, creator, all engagement metrics, duration, engagement_velocity, collected_at
     - All fields from Trend model except internal metadata
     - collected_at serialized to ISO format

**Key files:**
- `app/tasks.py` - Added 20 lines for collect_trends_task
- `app/api/routes.py` - Added 50 lines for /collect-trends and /trends endpoints

**Verification:**
- Task imports and registers successfully (name: app.tasks.collect_trends_task)
- GET /trends returns 200 with count and trends array
- All trends include engagement_velocity field
- Platform filter works: GET /trends?platform=tiktok returns only TikTok trends
- POST /collect-trends returns 200 with task_id, status, description

## Deviations from Plan

None - plan executed exactly as written. All tasks completed as specified without requiring additional work or architectural changes.

## Success Criteria

- [x] `scrape_tiktok_trends(limit=50)` returns 50 normalized trend dicts in mock mode
- [x] `scrape_youtube_shorts(limit=50)` returns 50 normalized trend dicts in mock mode
- [x] `collect_all_trends()` saves to DB and returns counts for both platforms
- [x] Running collection twice does NOT create duplicate rows (UPSERT works)
- [x] `GET /trends` returns stored trends with engagement_velocity field
- [x] `POST /collect-trends` queues a Celery task
- [x] All engagement velocities are finite positive numbers (no inf, no NaN)

## Technical Details

### Scraper Architecture

**Design pattern: Sync scrapers + async DB operations**

Scrapers are synchronous functions because:
1. Celery tasks are synchronous by default
2. Both Apify REST API and YouTube Data API work well with sync clients
3. Simpler error handling and retry logic
4. No need for asyncio event loop management in worker processes

The bridge between sync and async happens in `collect_all_trends()`:
- Scrapers return sync results
- Enrichment (velocity calculation) is sync
- Save operations are async (use SQLAlchemy async session)
- Celery task wraps with `asyncio.run()` to bridge sync task → async DB

### Mock Data Cycling

**Problem:** Mock fixtures have 10 items each, but scrapers need to support limit=50+

**Solution:** Cycle through fixtures with modified external_ids:
```python
for cycle in range(ceil(limit / len(mock_data))):
    for item in mock_data:
        trend = item.copy()
        if cycle > 0:
            trend["external_id"] = f"{item['external_id']}_dup_{cycle}"
        result.append(trend)
```

**Benefits:**
- Scrapers work with any limit, not just 10
- Tests can validate UPSERT behavior (run twice, check deduplication)
- Original external_ids preserved for first cycle (realistic IDs)
- Duplicated cycles create unique IDs (UPSERT sees them as different trends)

### SQLite UPSERT Pattern

**Standard SQL:** `INSERT ... ON CONFLICT DO UPDATE`
**SQLite dialect:** Requires `sqlalchemy.dialects.sqlite.insert`

```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = sqlite_insert(Trend).values(**trend_values)
stmt = stmt.on_conflict_do_update(
    index_elements=['platform', 'external_id'],  # Composite unique constraint
    set_={
        'views': stmt.excluded.views,
        'likes': stmt.excluded.likes,
        # ... other updated fields
    }
)
```

**Why not update collected_at?** First collection timestamp is more useful for tracking when a trend first appeared. Subsequent scrapes update engagement metrics but preserve discovery time.

### Engagement Velocity Edge Cases

1. **Division by zero:** Posts < 6 minutes old use 0.1 hour minimum
2. **Missing posted_at:** Returns 0.0 (can't calculate velocity without time)
3. **Negative engagement:** Sum could theoretically be negative if API returns negative numbers - currently no protection (would need business logic decision on how to handle)
4. **Very old posts:** No special handling - velocity will be very low for old posts with low engagement (expected behavior)

### API Integration Choices

**TikTok - Why Apify REST API not apify-client library:**
- apify-client is async-first, would require AsyncApifyClient
- Celery tasks are sync, would need asyncio.run() wrapper
- httpx.Client() provides sync HTTP with retry logic via tenacity
- REST API is stable and well-documented
- Easier to test and mock

**YouTube - Why googleapiclient not async library:**
- Official Google client is synchronous
- Mature, well-maintained, comprehensive
- Discovery-based API (no need for manual endpoint management)
- Quota management easier with official client

## Dependencies

**Requires (from previous phases):**
- Phase 02-01: Trend model with all metadata columns, TrendCreate schema, mock data fixtures, config with USE_MOCK_DATA flag

**Provides (for next plans):**
- Complete trend scraping pipeline (both platforms)
- Engagement velocity calculation
- Database UPSERT to prevent duplicates
- Celery task for automated collection
- API endpoints for triggering and querying trends
- Foundation for scheduled collection (cron/Celery beat)

**Affects:**
- Plan 02-03 (Analysis): Will consume collected trends from database via GET /trends endpoint or direct DB queries
- Future scheduling plan: collect_trends_task ready for Celery Beat periodic scheduling

## Self-Check: PASSED

**Files created verification:**
```bash
✓ FOUND: app/scrapers/base.py
✓ FOUND: app/scrapers/tiktok.py
✓ FOUND: app/scrapers/youtube.py
✓ FOUND: app/services/__init__.py
✓ FOUND: app/services/engagement.py
✓ FOUND: app/services/trend_collector.py
```

**Commits exist verification:**
```bash
✓ FOUND: 8eb8883 (Task 1: scrapers with mock/real switching)
✓ FOUND: d4e4220 (Task 2: engagement velocity and UPSERT)
✓ FOUND: f149ed1 (Task 3: Celery task and API endpoints)
```

**Functional verification:**
```bash
✓ TikTok scraper returns 5 trends in mock mode
✓ YouTube scraper returns 5 trends in mock mode
✓ Engagement velocity calculation accurate within margin
✓ Collection pipeline saves 100 trends (50 + 50)
✓ UPSERT prevents duplicates (count stays 100 after second run)
✓ Task registration successful (name: app.tasks.collect_trends_task)
✓ GET /trends returns 200 with trends array
✓ GET /trends?platform=tiktok filters correctly
✓ POST /collect-trends returns 200 with task_id
```

## Next Steps

**Immediate (Plan 02-03):**
- Build Claude-based trend analyzer consuming trends from database
- Implement TrendReport generation (video styles, patterns, recommendations)
- Create analysis Celery task (runs after collection completes)
- Add GET /trend-reports API endpoint

**Future (Phase 3+):**
- Schedule collect_trends_task with Celery Beat (every 6 hours per config)
- Add trend deduplication cleanup task (remove old duplicate entries)
- Implement trend expiration (archive trends older than N days)
- Add trending score calculation (combines velocity + recency + virality)

**Testing:**
- Unit tests for engagement velocity edge cases
- Integration tests for UPSERT behavior
- Mock Apify/YouTube API responses for real mode testing
- Celery task retry behavior testing

## Notes

- All code Python 3.9 compatible (uses `typing.List, Optional, Dict` not `list[str]`)
- Mock data cycling creates unique external_ids to test UPSERT properly
- Scrapers return empty list on total failure (graceful degradation)
- Platform collection errors isolated (one platform failure doesn't crash entire collection)
- Engagement velocity stored in DB (not computed on query) for performance
- collected_at not updated on UPSERT conflict (preserves first seen timestamp)
- Celery task uses asyncio.run() to bridge sync task → async DB operations
- API endpoints return ISO timestamps (serialized from datetime objects)
- UPSERT verified working: 100 trends after first run, 100 after second (not 200)
