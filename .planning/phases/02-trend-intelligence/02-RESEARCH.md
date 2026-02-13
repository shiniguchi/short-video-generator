# Phase 2: Trend Intelligence - Research

**Researched:** 2026-02-13
**Domain:** Social media API scraping, trend analysis, scheduled task execution
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 implements a trend intelligence system that collects viral content from TikTok and YouTube Shorts, then analyzes patterns using Claude API. The core technical stack combines Apify for TikTok scraping, YouTube Data API v3 for Shorts collection, Celery Beat for scheduled execution, aiosqlite for async database operations, and Claude API's structured outputs for analysis.

**Critical environment constraints:** Python 3.9.6 only, no Docker (local SQLite instead of PostgreSQL), local-first testing with mock data before connecting to external APIs.

**Primary technical challenges:**
1. YouTube Data API v3 has no native Shorts filter - requires client-side filtering of videos < 60s
2. YouTube quota management is critical (10,000 units/day default) - batch requests and caching essential
3. Celery workers are synchronous by default - need careful async integration with aiosqlite
4. Apify and YouTube both have rate limits requiring exponential backoff retry logic
5. Mock data strategy needed for local testing without burning API quotas

**Primary recommendation:** Use Celery 5.6.2 with task-level async integration, implement comprehensive retry logic with exponential backoff for all external APIs, use SQLite UPSERT for deduplication, and structure mock data as JSON fixtures matching real API responses.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery | 5.6.2 | Async task queue & scheduling | Industry standard for Python async tasks, Python 3.9+ compatible, stable 5.6 "Recovery" release |
| celery-pool-asyncio | latest | Async task support | Enables async/await within Celery tasks for aiosqlite integration |
| aiosqlite | latest | Async SQLite operations | Official asyncio bridge for SQLite, non-blocking database I/O |
| anthropic | latest | Claude API client | Official Anthropic SDK with structured output support |
| httpx | latest | Async HTTP client | Modern async HTTP client, preferred over aiohttp for simplicity |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-api-python-client | latest | YouTube Data API v3 | Required for YouTube Shorts scraping |
| google-auth-oauthlib | latest | YouTube API auth | Required for YouTube API authentication |
| tenacity | latest | Retry with backoff | Exponential backoff for API rate limiting |
| pydantic | ^2.0 | Data validation & schemas | Validates API responses, generates Claude schemas |
| python-dotenv | latest | Environment variables | API key management for local dev |
| pytest | latest | Testing framework | Mock data testing before API integration |
| pytest-mock | latest | Test mocking | Mock Apify/YouTube/Claude responses |
| pytest-asyncio | latest | Async test support | Test async tasks and aiosqlite operations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Celery | APScheduler | APScheduler simpler but doesn't scale, no distributed workers |
| aiosqlite | sqlite3 (sync) | Sync blocks event loop, defeats async benefits |
| httpx | requests | requests is sync-only, incompatible with async pattern |
| Apify | Direct TikTok scraping | TikTok blocks scrapers aggressively, Apify handles anti-bot measures |
| YouTube Data API | Direct scraping | YouTube blocks scrapers, API is official/stable |

**Installation:**
```bash
# Core dependencies
pip install celery[redis]==5.6.2 celery-pool-asyncio aiosqlite anthropic httpx

# YouTube API
pip install google-api-python-client google-auth-oauthlib

# Utilities
pip install tenacity pydantic python-dotenv

# Testing
pip install pytest pytest-mock pytest-asyncio
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── scrapers/           # External API integrations
│   ├── apify.py        # Apify TikTok scraper client
│   ├── youtube.py      # YouTube Data API client
│   └── mock_data/      # JSON fixtures for local testing
│       ├── tiktok_trending.json
│       └── youtube_shorts.json
├── analyzers/          # Trend analysis logic
│   ├── claude.py       # Claude API client with structured outputs
│   └── engagement.py   # Engagement velocity calculations
├── tasks/              # Celery task definitions
│   ├── scrape.py       # Scheduled scraping tasks
│   └── analyze.py      # Analysis tasks
├── models/             # Pydantic models
│   ├── trend.py        # Trend data models
│   └── report.py       # Trend report models
├── db/                 # Database operations
│   ├── schema.sql      # SQLite schema with UPSERT logic
│   └── operations.py   # aiosqlite CRUD operations
└── config.py           # Configuration (API keys, schedule, feature flags)
```

### Pattern 1: Celery Task with Async Integration
**What:** Celery tasks that call async functions using asyncio.run()
**When to use:** When Celery task needs aiosqlite or httpx async operations
**Example:**
```python
# tasks/scrape.py
from celery import shared_task
import asyncio
from scrapers.youtube import scrape_youtube_shorts
from db.operations import save_trends

@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,  # Exponential backoff
    retry_jitter=True,   # Add jitter to prevent thundering herd
    max_retries=5
)
def scrape_youtube_shorts_task():
    """Celery task wrapper for async YouTube scraping."""
    return asyncio.run(_scrape_youtube_shorts_async())

async def _scrape_youtube_shorts_async():
    """Actual async implementation."""
    trends = await scrape_youtube_shorts(limit=50)
    await save_trends(trends, platform="youtube")
    return len(trends)
```
**Source:** [Celery async integration patterns](https://docs.celeryq.dev/en/main/userguide/tasks.html)

### Pattern 2: SQLite UPSERT for Deduplication
**What:** Insert or update based on unique (platform, external_id) constraint
**When to use:** Every time saving scraped trends to prevent duplicates
**Example:**
```python
# db/schema.sql
CREATE TABLE trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    hashtags TEXT,  -- JSON array
    likes INTEGER,
    comments INTEGER,
    shares INTEGER,
    views INTEGER,
    duration INTEGER,
    creator_name TEXT,
    creator_id TEXT,
    sound_name TEXT,
    thumbnail_url TEXT,
    posted_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, external_id)
);

# db/operations.py
async def save_trend(db, trend):
    """UPSERT trend using ON CONFLICT."""
    await db.execute("""
        INSERT INTO trends (
            platform, external_id, title, description, hashtags,
            likes, comments, shares, views, duration,
            creator_name, creator_id, sound_name, thumbnail_url, posted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(platform, external_id)
        DO UPDATE SET
            likes = excluded.likes,
            comments = excluded.comments,
            shares = excluded.shares,
            views = excluded.views,
            collected_at = CURRENT_TIMESTAMP
        WHERE excluded.collected_at > trends.collected_at
    """, (
        trend.platform, trend.external_id, trend.title,
        trend.description, trend.hashtags_json,
        trend.likes, trend.comments, trend.shares, trend.views,
        trend.duration, trend.creator_name, trend.creator_id,
        trend.sound_name, trend.thumbnail_url, trend.posted_at
    ))
    await db.commit()
```
**Source:** [SQLite UPSERT documentation](https://sqlite.org/lang_upsert.html)

### Pattern 3: Claude Structured Outputs for Analysis
**What:** Use Claude API's output_config.format for guaranteed JSON schema
**When to use:** When analyzing trends and generating structured reports
**Example:**
```python
# analyzers/claude.py
from anthropic import Anthropic
from pydantic import BaseModel
from typing import List

class VideoStyle(BaseModel):
    category: str  # "cinematic", "talking-head", "montage", "text-heavy"
    confidence: float

class TrendPattern(BaseModel):
    format: str
    avg_duration: float
    hook_type: str
    text_overlay: bool
    audio_type: str

class TrendReport(BaseModel):
    analyzed_count: int
    styles: List[VideoStyle]
    patterns: List[TrendPattern]
    engagement_velocity_avg: float
    top_hashtags: List[str]

async def analyze_trends(trends: List[dict]) -> TrendReport:
    client = Anthropic()

    # Prepare trend summary for Claude
    trend_summary = "\n".join([
        f"- {t['title']} ({t['duration']}s, {t['likes']} likes, {t['engagement_velocity']:.2f} eng/hr)"
        for t in trends[:50]  # Limit context size
    ])

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"Analyze these trending videos and extract patterns:\n\n{trend_summary}"
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": TrendReport.model_json_schema()
            }
        }
    )

    import json
    report_data = json.loads(response.content[0].text)
    return TrendReport(**report_data)
```
**Source:** [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### Pattern 4: Mock Data Strategy for Local Testing
**What:** Use feature flag to switch between real APIs and mock JSON fixtures
**When to use:** Development and testing before connecting external APIs
**Example:**
```python
# config.py
import os

USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

# scrapers/youtube.py
import json
from pathlib import Path

async def scrape_youtube_shorts(limit=50):
    if USE_MOCK_DATA:
        # Load from fixture
        fixture_path = Path(__file__).parent / "mock_data" / "youtube_shorts.json"
        with open(fixture_path) as f:
            data = json.load(f)
        return data[:limit]
    else:
        # Real API call
        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        # ... actual API logic
```

**Mock data fixture structure (youtube_shorts.json):**
```json
[
  {
    "external_id": "dQw4w9WgXcQ",
    "title": "Epic Skateboard Trick",
    "description": "Watch this insane trick! #skateboarding",
    "duration": 45,
    "likes": 125000,
    "comments": 3400,
    "shares": 890,
    "views": 2500000,
    "creator_name": "SkateKing",
    "creator_id": "UC...",
    "thumbnail_url": "https://i.ytimg.com/vi/...",
    "posted_at": "2026-02-12T14:30:00Z",
    "hashtags": ["skateboarding", "tricks", "extreme"]
  }
]
```

### Pattern 5: Engagement Velocity Calculation
**What:** Normalize engagement metrics by time since posting
**When to use:** Before storing trends, to enable apples-to-apples comparison
**Example:**
```python
# analyzers/engagement.py
from datetime import datetime, timezone

def calculate_engagement_velocity(trend: dict) -> float:
    """
    Engagement velocity = (likes + comments + shares) / hours_since_posted

    Returns velocity in engagements per hour.
    """
    total_engagement = (
        trend.get('likes', 0) +
        trend.get('comments', 0) +
        trend.get('shares', 0)
    )

    posted_at = datetime.fromisoformat(trend['posted_at'].replace('Z', '+00:00'))
    hours_since = (datetime.now(timezone.utc) - posted_at).total_seconds() / 3600

    # Prevent division by zero (very recent posts)
    if hours_since < 0.1:
        hours_since = 0.1

    return total_engagement / hours_since
```
**Source:** [Engagement velocity formula](https://bsquared.media/what-is-social-media-engagement-velocity/)

### Pattern 6: Celery Beat Schedule Configuration
**What:** Configure periodic tasks to run every 6 hours
**When to use:** App initialization
**Example:**
```python
# celeryconfig.py
from celery.schedules import crontab

beat_schedule = {
    'scrape-tiktok-trends': {
        'task': 'tasks.scrape.scrape_tiktok_trends_task',
        'schedule': 21600.0,  # 6 hours in seconds
    },
    'scrape-youtube-shorts': {
        'task': 'tasks.scrape.scrape_youtube_shorts_task',
        'schedule': 21600.0,
    },
    'analyze-trends': {
        'task': 'tasks.analyze.analyze_trends_task',
        'schedule': crontab(minute=30, hour='*/6'),  # 30 min after scraping
    },
}

timezone = 'UTC'
```
**Source:** [Celery periodic tasks](https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html)

### Anti-Patterns to Avoid

- **Synchronous database calls in async context:** Never use `sqlite3` module directly in async code - always use `aiosqlite`
- **Missing retry logic on external APIs:** All Apify, YouTube, and Claude calls can fail - must have exponential backoff
- **Hardcoded API keys:** Use environment variables with `python-dotenv` for all credentials
- **No rate limiting:** YouTube has 10,000 unit/day quota - must track usage and implement caching
- **Infinite retries:** Always set `max_retries` on Celery tasks to prevent runaway failures
- **YouTube Shorts filtering server-side:** API has no Shorts-specific filter - must filter by duration < 60s client-side
- **Blocking async event loop:** Never call `time.sleep()` in async code - use `await asyncio.sleep()`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TikTok scraping | Custom scraper | Apify actors (lexis-solutions/tiktok-trending-videos-scraper) | TikTok has aggressive anti-bot measures, Apify handles CAPTCHAs, IP rotation, device emulation |
| API retry logic | Custom retry loops | tenacity library | Edge cases: jitter, max delay, retry filters, exponential backoff calculation |
| JSON schema validation | Manual dict validation | Pydantic models | Handles nested validation, type coercion, custom validators, auto-documentation |
| Task scheduling | Custom cron scripts | Celery Beat | Distributed task queue, failure recovery, task monitoring, horizontal scaling |
| Async SQLite | Threading/multiprocessing hacks | aiosqlite | Proper event loop integration, prevents database locks, handles connection lifecycle |
| Claude JSON parsing | Prompt engineering | Structured outputs (output_config.format) | Guaranteed valid JSON, no retry loops, schema enforcement at inference time |

**Key insight:** External APIs fail in unpredictable ways. Libraries like `tenacity` handle exponential backoff, jitter, max delay capping, and retry filtering that custom code consistently gets wrong. Similarly, Apify's anti-bot infrastructure is far more sophisticated than hand-rolled solutions.

## Common Pitfalls

### Pitfall 1: YouTube Data API Quota Burnout
**What goes wrong:** Naive implementation burns through 10,000 unit daily quota in minutes
**Why it happens:**
- Each `search.list()` costs 100 units
- Each `videos.list()` costs 1 unit per video
- Requesting 50 videos individually = 5000 units
- No caching = repeat requests every 6 hours
**How to avoid:**
- Batch video details requests (50 videos in 1 call = 1 unit total)
- Cache results for 6 hours (match scraping frequency)
- Use `fields` parameter to request only needed data
- Use ETags for conditional requests (304 = 0 units)
**Warning signs:**
- Quota exceeded errors before noon
- 403 errors with "quotaExceeded" message
**Example:**
```python
# BAD: Individual requests (50 units)
for video_id in video_ids[:50]:
    response = youtube.videos().list(part='snippet,statistics', id=video_id).execute()

# GOOD: Batch request (1 unit)
response = youtube.videos().list(
    part='snippet,statistics',
    id=','.join(video_ids[:50]),  # Up to 50 IDs
    fields='items(id,snippet(title,description),statistics(viewCount,likeCount))'
).execute()
```
**Sources:** [YouTube quota optimization](https://getlate.dev/blog/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota)

### Pitfall 2: YouTube Shorts Detection Assumptions
**What goes wrong:** Assuming `videoDuration: "short"` filter returns only Shorts
**Why it happens:**
- API's "short" means < 4 minutes, not < 60 seconds
- No native Shorts-specific filter exists in API v3
- Search UI has Shorts filter but API doesn't expose it
**How to avoid:**
- Always filter client-side: `duration < 60` after fetching video details
- Use `videoDuration: "short"` to narrow search, then post-filter
- Check actual duration field in video details response
**Warning signs:**
- Collected "Shorts" include 2-3 minute videos
- Trend analysis includes non-Short content
**Example:**
```python
# INCOMPLETE: Relies only on API filter
response = youtube.search().list(
    part='snippet',
    type='video',
    videoDuration='short',  # < 4 minutes, NOT Shorts!
    maxResults=50
).execute()

# COMPLETE: Client-side filtering
search_response = youtube.search().list(
    part='snippet',
    type='video',
    videoDuration='short',
    maxResults=50
).execute()

video_ids = [item['id']['videoId'] for item in search_response['items']]
details = youtube.videos().list(
    part='contentDetails',
    id=','.join(video_ids)
).execute()

# Filter to actual Shorts (< 60 seconds)
shorts = [
    video for video in details['items']
    if parse_duration(video['contentDetails']['duration']) < 60
]
```
**Sources:** [YouTube API Shorts filtering discussion](https://issuetracker.google.com/issues/232112727)

### Pitfall 3: Celery + aiosqlite Integration Issues
**What goes wrong:** Celery tasks hang or raise "RuntimeError: no running event loop"
**Why it happens:**
- Celery workers are synchronous by default
- aiosqlite requires async event loop
- Can't call async functions directly from sync Celery tasks
**How to avoid:**
- Use `asyncio.run()` to create event loop in task
- OR install `celery-pool-asyncio` for native async tasks
- Never mix sync and async DB calls in same codebase
**Warning signs:**
- Tasks stuck in "STARTED" state indefinitely
- RuntimeError exceptions in worker logs
**Example:**
```python
# WRONG: Calling async function from sync task
@shared_task
def save_trends_task(trends):
    await save_trends(trends)  # RuntimeError!

# RIGHT: Wrap in asyncio.run()
@shared_task
def save_trends_task(trends):
    asyncio.run(save_trends(trends))

# ALTERNATIVE: Use async pool (requires celery-pool-asyncio)
# celery -A app worker -P celery_pool_asyncio:TaskPool
@shared_task
async def save_trends_task(trends):
    await save_trends(trends)
```
**Sources:** [Celery async integration](https://pypi.org/project/celery-pool-asyncio/)

### Pitfall 4: Apify Rate Limiting and Cost Overruns
**What goes wrong:** Apify bills spike unexpectedly or actor runs fail with rate limit errors
**Why it happens:**
- Apify charges per compute unit (Actor runtime)
- Rate limit: 60 requests/second per resource
- Free tier has $5/month credit (~limited runs)
- No built-in retry on rate limit errors
**How to avoid:**
- Implement exponential backoff on Apify API calls
- Monitor Actor run costs in Apify console
- Set `maxResults` parameter to limit scraping scope
- Cache Apify results for 6+ hours
- Use `timeout` parameter to prevent runaway costs
**Warning signs:**
- Rate limit 429 errors from Apify API
- Unexpected charges beyond free tier
- Actor runs timing out (default 3600s)
**Example:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential
from apify_client import ApifyClient

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    reraise=True
)
async def run_apify_actor(actor_id: str, run_input: dict):
    client = ApifyClient(token=APIFY_API_TOKEN)

    run = client.actor(actor_id).call(
        run_input={
            **run_input,
            'maxResults': 50,  # Limit scope
        },
        timeout_secs=300,  # 5 min max
    )

    return client.dataset(run['defaultDatasetId']).list_items().items
```
**Sources:** [Apify rate limits](https://docs.apify.com/platform/limits), [Apify pricing](https://apify.com/pricing)

### Pitfall 5: Claude API Structured Output Schema Complexity
**What goes wrong:** 400 errors with "Schema too complex" or "Unsupported feature"
**Why it happens:**
- Structured outputs don't support all JSON Schema features
- Recursive schemas not allowed
- Numeric constraints (min/max) not supported
- Complex `{n,m}` regex quantifiers fail
**How to avoid:**
- Keep schemas flat (avoid deep nesting)
- Use `enum` instead of regex patterns where possible
- Set `additionalProperties: false` on all objects
- Use Pydantic models and let SDK transform schema
**Warning signs:**
- 400 errors from Claude API mentioning schema
- Responses don't match expected structure
**Example:**
```python
# BAD: Unsupported numeric constraints
class VideoMetrics(BaseModel):
    likes: int = Field(ge=0, le=1000000)  # min/max not supported!
    duration: int = Field(ge=1, le=60)

# GOOD: Remove constraints, validate in code
class VideoMetrics(BaseModel):
    likes: int
    duration: int

# Then validate manually:
def validate_metrics(metrics: VideoMetrics):
    assert 0 <= metrics.likes <= 1_000_000
    assert 1 <= metrics.duration <= 60
```
**Sources:** [Claude structured outputs limitations](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### Pitfall 6: Engagement Velocity Division by Zero
**What goes wrong:** `ZeroDivisionError` or `inf` values for very recent posts
**Why it happens:**
- Posts less than 1 minute old have `hours_since_posted` near zero
- Dividing by zero or near-zero produces invalid metrics
**How to avoid:**
- Set minimum threshold (e.g., 0.1 hours = 6 minutes)
- Skip velocity calculation for posts < threshold
- Store `posted_at` and calculate velocity at query time
**Warning signs:**
- `inf` or `NaN` values in engagement_velocity column
- Python exceptions during velocity calculation
**Example:**
```python
# BAD: No protection against division by zero
velocity = total_engagement / hours_since_posted

# GOOD: Minimum threshold
MIN_HOURS = 0.1  # 6 minutes
hours_since_posted = max(hours_since_posted, MIN_HOURS)
velocity = total_engagement / hours_since_posted
```

### Pitfall 7: Missing Idempotency in Tasks
**What goes wrong:** Retried tasks create duplicate database entries or double-charge APIs
**Why it happens:**
- Celery retries failed tasks automatically
- Database operations may partially succeed before failure
- External API calls aren't automatically idempotent
**How to avoid:**
- Use SQLite UPSERT for all trend storage
- Check if work already done before expensive API calls
- Use task IDs or timestamps as idempotency keys
**Warning signs:**
- Duplicate trends in database despite UNIQUE constraint
- Multiple Apify charges for same scraping run
**Example:**
```python
@shared_task(autoretry_for=(Exception,), max_retries=3)
def scrape_and_analyze_task():
    # BAD: No idempotency check
    trends = scrape_tiktok()  # Might be called 3+ times
    analyze_trends(trends)

    # GOOD: Check if already complete
    if task_already_complete(scrape_and_analyze_task.request.id):
        return "Already processed"

    trends = scrape_tiktok()
    analyze_trends(trends)
    mark_task_complete(scrape_and_analyze_task.request.id)
```
**Sources:** [Celery idempotency patterns](https://www.vintasoftware.com/blog/celery-wild-tips-and-tricks-run-async-tasks-real-world)

## Code Examples

Verified patterns from official sources:

### Celery Task with Retry Configuration
```python
# tasks/scrape.py
from celery import shared_task
from tenacity import retry, stop_after_attempt, wait_exponential

@shared_task(
    bind=True,  # Access task instance
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 min delay
    retry_jitter=True,  # Add randomness
    max_retries=5
)
def scrape_youtube_shorts_task(self):
    try:
        return asyncio.run(_scrape_youtube_shorts_async())
    except Exception as exc:
        # Log retry attempt
        logger.warning(f"Task retry {self.request.retries}/{self.max_retries}: {exc}")
        raise
```
**Source:** [Celery retry configuration](https://docs.celeryq.dev/en/main/userguide/tasks.html)

### aiosqlite Context Manager Pattern
```python
# db/operations.py
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "trends.db"

async def save_trends(trends: List[dict], platform: str):
    """Save multiple trends with UPSERT logic."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row  # Access columns by name

        for trend in trends:
            await db.execute("""
                INSERT INTO trends (platform, external_id, title, likes, comments, shares)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, external_id) DO UPDATE SET
                    likes = excluded.likes,
                    comments = excluded.comments,
                    shares = excluded.shares,
                    collected_at = CURRENT_TIMESTAMP
            """, (platform, trend['id'], trend['title'],
                  trend['likes'], trend['comments'], trend['shares']))

        await db.commit()

async def get_recent_trends(hours: int = 24):
    """Get trends collected in last N hours."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT * FROM trends
            WHERE collected_at > datetime('now', '-' || ? || ' hours')
            ORDER BY engagement_velocity DESC
            LIMIT 100
        """, (hours,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
```
**Source:** [aiosqlite documentation](https://aiosqlite.omnilib.dev/)

### YouTube Data API Batch Request
```python
# scrapers/youtube.py
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import isodate

def scrape_youtube_shorts(api_key: str, limit: int = 50) -> List[dict]:
    """Scrape trending YouTube Shorts with quota optimization."""
    youtube = build('youtube', 'v3', developerKey=api_key)

    # Step 1: Search for short videos (100 units)
    search_response = youtube.search().list(
        part='id',  # Only get IDs to save quota
        type='video',
        videoDuration='short',  # < 4 minutes
        order='viewCount',
        publishedAfter=(datetime.now() - timedelta(days=7)).isoformat() + 'Z',
        maxResults=limit
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

    if not video_ids:
        return []

    # Step 2: Batch fetch video details (1 unit for all 50 videos)
    details_response = youtube.videos().list(
        part='snippet,statistics,contentDetails',
        id=','.join(video_ids),
        fields='items(id,snippet(title,description,tags,thumbnails),statistics,contentDetails(duration))'
    ).execute()

    # Step 3: Filter to actual Shorts (< 60 seconds)
    shorts = []
    for video in details_response.get('items', []):
        duration_str = video['contentDetails']['duration']
        duration_seconds = isodate.parse_duration(duration_str).total_seconds()

        if duration_seconds < 60:
            shorts.append({
                'external_id': video['id'],
                'title': video['snippet']['title'],
                'description': video['snippet'].get('description', ''),
                'duration': int(duration_seconds),
                'likes': int(video['statistics'].get('likeCount', 0)),
                'comments': int(video['statistics'].get('commentCount', 0)),
                'views': int(video['statistics'].get('viewCount', 0)),
                'shares': 0,  # Not available in API
                'thumbnail_url': video['snippet']['thumbnails']['high']['url'],
                'hashtags': video['snippet'].get('tags', []),
                'posted_at': video['snippet']['publishedAt'],
            })

    return shorts
```
**Source:** [YouTube Data API](https://developers.google.com/youtube/v3/docs)

### Apify Actor Execution with Retry
```python
# scrapers/apify.py
from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class ApifyRateLimitError(Exception):
    pass

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(ApifyRateLimitError),
    reraise=True
)
def scrape_tiktok_trends(api_token: str, limit: int = 50) -> List[dict]:
    """Scrape TikTok trending videos via Apify."""
    client = ApifyClient(token=api_token)

    # Use lexis-solutions/tiktok-trending-videos-scraper
    actor_id = 'lexis-solutions/tiktok-trending-videos-scraper'

    run = client.actor(actor_id).call(
        run_input={
            'maxResults': limit,
            'region': 'US',  # Can configure per requirement
        },
        timeout_secs=300,  # 5 min timeout
    )

    # Check for rate limiting
    if run['status'] == 'FAILED':
        error_msg = run.get('statusMessage', '')
        if 'rate limit' in error_msg.lower():
            raise ApifyRateLimitError(error_msg)
        raise Exception(f"Apify actor failed: {error_msg}")

    # Fetch results from dataset
    dataset_items = client.dataset(run['defaultDatasetId']).list_items().items

    # Normalize to internal format
    return [
        {
            'external_id': item['id'],
            'title': item.get('title', ''),
            'description': item.get('description', ''),
            'duration': item.get('duration', 0),
            'likes': item.get('likes', 0),
            'comments': item.get('comments', 0),
            'shares': item.get('shares', 0),
            'views': item.get('views', 0),
            'creator_name': item.get('author', {}).get('nickname', ''),
            'creator_id': item.get('author', {}).get('id', ''),
            'sound_name': item.get('music', {}).get('title', ''),
            'thumbnail_url': item.get('cover', ''),
            'hashtags': [tag['name'] for tag in item.get('hashtags', [])],
            'posted_at': item.get('createTime', ''),
        }
        for item in dataset_items
    ]
```
**Source:** [Apify Python client](https://docs.apify.com/api/client/python/)

### Claude Structured Output for Trend Analysis
```python
# analyzers/claude.py
from anthropic import Anthropic
from pydantic import BaseModel, Field
from typing import List
import json

class VideoStyle(BaseModel):
    category: str = Field(description="cinematic, talking-head, montage, text-heavy, animation")
    confidence: float = Field(description="0.0 to 1.0")
    count: int = Field(description="Number of videos in this style")

class TrendPattern(BaseModel):
    format_description: str
    avg_duration_seconds: float
    hook_type: str = Field(description="question, shock, story, tutorial")
    uses_text_overlay: bool
    audio_type: str = Field(description="original, trending-sound, voiceover, music")

class TrendReport(BaseModel):
    analyzed_count: int
    date_range: str
    video_styles: List[VideoStyle]
    common_patterns: List[TrendPattern]
    avg_engagement_velocity: float
    top_hashtags: List[str]
    recommendations: List[str]

async def analyze_trends_with_claude(trends: List[dict]) -> TrendReport:
    """Analyze collected trends using Claude API with structured output."""
    client = Anthropic()

    # Calculate engagement velocities
    for trend in trends:
        trend['engagement_velocity'] = calculate_engagement_velocity(trend)

    # Prepare summary (limit to avoid token overflow)
    trend_summaries = [
        f"Title: {t['title']}\n"
        f"Duration: {t['duration']}s\n"
        f"Engagement: {t['likes']} likes, {t['comments']} comments, {t['views']} views\n"
        f"Velocity: {t['engagement_velocity']:.1f} eng/hr\n"
        f"Hashtags: {', '.join(t['hashtags'][:5])}\n"
        for t in trends[:50]  # Limit to top 50
    ]

    prompt = f"""Analyze these {len(trends)} trending short-form videos and extract patterns.

Focus on:
1. Visual style classification (cinematic, talking-head, montage, etc.)
2. Common format patterns (hooks, text overlays, audio choices)
3. What makes high-velocity content succeed

Videos:
{'---'.join(trend_summaries)}

Provide structured analysis."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        k: v for k, v in TrendReport.model_json_schema()["properties"].items()
                    },
                    "required": TrendReport.model_json_schema().get("required", []),
                    "additionalProperties": False
                }
            }
        }
    )

    # Parse guaranteed-valid JSON
    report_data = json.loads(response.content[0].text)
    return TrendReport(**report_data)
```
**Source:** [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### Mock Data Testing Pattern
```python
# tests/test_scrapers.py
import pytest
import json
from pathlib import Path
from scrapers.youtube import scrape_youtube_shorts
from scrapers.apify import scrape_tiktok_trends

@pytest.fixture
def mock_youtube_response():
    """Load mock YouTube API response."""
    fixture_path = Path(__file__).parent / "fixtures" / "youtube_search.json"
    with open(fixture_path) as f:
        return json.load(f)

@pytest.mark.asyncio
async def test_youtube_scraper_with_mock(mocker, mock_youtube_response):
    """Test YouTube scraper using mock data."""
    # Mock the YouTube API client
    mock_youtube = mocker.MagicMock()
    mock_youtube.search().list().execute.return_value = mock_youtube_response

    mocker.patch('googleapiclient.discovery.build', return_value=mock_youtube)

    # Run scraper
    results = scrape_youtube_shorts(api_key='fake-key', limit=10)

    # Assertions
    assert len(results) > 0
    assert all(r['duration'] < 60 for r in results)
    assert all('external_id' in r for r in results)
```
**Source:** [Pytest mocking patterns](https://pytest-with-eric.com/mocking/pytest-mocking/)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| YouTube v2 API | YouTube Data API v3 | 2015 | v2 deprecated, v3 required for all apps |
| Manual JSON parsing | Claude structured outputs | Nov 2025 | Guaranteed valid JSON, no retry loops needed |
| Celery < 5.6 | Celery 5.6.2 "Recovery" | Jan 2026 | Python 3.9-3.13 support, critical memory leak fixes |
| requests library | httpx | 2020+ | Async/await support, HTTP/2, better timeout handling |
| Hand-rolled TikTok scraping | Apify actors | 2021+ | Anti-bot bypassing, maintained scrapers, reliability |
| `output_format` param | `output_config.format` | Dec 2025 | Claude API parameter migration (old still works) |

**Deprecated/outdated:**
- **YouTube Data API v2:** Completely shut down, v3 required
- **Celery < 5.0:** Python 2 compatibility, use 5.6+ for Python 3.9+
- **`output_format` parameter:** Moved to `output_config.format` (transition period active)
- **Direct TikTok scraping:** TikTok actively blocks scrapers, Apify infrastructure required

## Open Questions

1. **TikTok Apify Actor Data Completeness**
   - What we know: Apify has multiple TikTok scrapers (clockworks, lexis-solutions, apidojo)
   - What's unclear: Exact output schema for trending videos (couldn't fetch README from WebFetch)
   - Recommendation: Test both `lexis-solutions/tiktok-trending-videos-scraper` and `clockworks/tiktok-trends-scraper` with small runs to compare output quality and structure. Check Apify Console for schema documentation.

2. **Video Style Classification Methodology**
   - What we know: Common categories are cinematic, talking-head, montage, text-heavy
   - What's unclear: Whether Claude can reliably classify from metadata alone (no video frames)
   - Recommendation: Test Claude's classification accuracy with metadata-only vs. providing thumbnail URLs. May need to download thumbnails and pass as base64 if metadata insufficient.

3. **Engagement Velocity Normalization**
   - What we know: Basic formula is `(likes + comments + shares) / hours_since_posted`
   - What's unclear: Whether TikTok and YouTube engagement should use same formula (different user behaviors)
   - Recommendation: Calculate separate velocity distributions for each platform, potentially normalize within-platform rather than across platforms.

4. **Celery Broker Choice**
   - What we know: Celery supports Redis, RabbitMQ, or database as broker
   - What's unclear: Best choice for local-first development (no Docker constraint)
   - Recommendation: Use Redis via local installation (brew/apt) or fall back to SQLite broker (slower but no dependencies). Redis preferred for production-like testing.

5. **Trend Report Storage Strategy**
   - What we know: Reports should be stored in database
   - What's unclear: Should reports be versioned (multiple per day)? How long to retain?
   - Recommendation: Store one report per analysis run with timestamp. Include `analysis_period_start/end` columns. Retain 30 days for trend-over-time analysis.

## Sources

### Primary (HIGH confidence)
- [Claude Structured Outputs - Official Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Celery 5.6 Documentation](https://docs.celeryq.dev/en/main/)
- [Celery Periodic Tasks](https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html)
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/)
- [SQLite UPSERT](https://sqlite.org/lang_upsert.html)
- [YouTube Data API v3 Reference](https://developers.google.com/youtube/v3/docs)
- [Apify API Documentation](https://docs.apify.com/api/v2)
- [Apify Platform Limits](https://docs.apify.com/platform/limits)

### Secondary (MEDIUM confidence)
- [YouTube API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost) - Official Google tool
- [Celery 2026 Complete Guide](https://devtoolbox.dedyn.io/blog/celery-complete-guide) - Third-party tutorial
- [YouTube API Quota Optimization](https://getlate.dev/blog/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota) - 2026 guide
- [Engagement Velocity Definition](https://bsquared.media/what-is-social-media-engagement-velocity/) - Marketing source
- [Celery Idempotency Patterns](https://www.vintasoftware.com/blog/celery-wild-tips-and-tricks-run-async-tasks-real-world) - Engineering blog
- [Pytest Mocking Guide](https://pytest-with-eric.com/mocking/pytest-mocking/) - Tutorial site

### Tertiary (LOW confidence - needs verification)
- [TikTok Trending Videos Scraper - Apify](https://apify.com/lexis-solutions/tiktok-trending-videos-scraper) - Couldn't access full README
- [Video Style Classification Examples](https://www.vidyard.com/blog/different-styles-of-videos/) - Marketing blog, not ML source
- YouTube Shorts API filter - Multiple sources confirm NO native filter exists, requires client-side filtering

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs/PyPI, version compatibility confirmed
- Architecture: MEDIUM-HIGH - Patterns sourced from official docs, but TikTok scraper specifics need runtime verification
- Pitfalls: HIGH - YouTube quota, Shorts filtering, and Celery+aiosqlite issues verified via official docs and community reports
- Claude structured outputs: HIGH - Official Anthropic docs with code examples
- Mock data strategy: MEDIUM - Common pattern but implementation details project-specific

**Research date:** 2026-02-13
**Valid until:** 2026-03-15 (30 days - stable ecosystem, but API quotas/limits may change)

**Key unknowns requiring investigation:**
1. Exact TikTok Apify actor output schema (test with actual run)
2. Claude's video classification accuracy from metadata alone (experiment needed)
3. Optimal Celery broker for local-first constraint (test Redis vs SQLite broker)
