# ViralForge — Claude Code Development Prompt

## What to Build

Build **ViralForge**, a fully containerized (Docker Compose) Python web application that automatically generates short-form videos (TikTok / YouTube Shorts) by analyzing trending viral content and producing AI-generated videos aligned to a user-defined theme or product.

The system is controlled entirely via a Google Spreadsheet (master data). No dashboard UI for MVP. The complete pipeline must run locally in Docker with visible logs for every stage.

---

## Core Pipeline (8 Stages, Sequential)

### Stage 1: Trend Collection
- Scrape trending videos from **TikTok** (via Apify TikTok Trending Videos Scraper API — https://apify.com/lexis-solutions/tiktok-trending-videos-scraper) and **YouTube** (via YouTube Data API v3 `videos.list` with `chart=mostPopular`, filtered for Shorts < 60s — https://developers.google.com/youtube/v3/docs/videos/list).
- Collect: title, description, hashtags, view/like/comment/share counts, duration, creator handle, creator followers, sound name, thumbnail URL, video URL, category, country.
- Store in PostgreSQL. Deduplicate on `(platform, external_id)`. Retain 90 days of history.
- Run on configurable cron (default: every 6 hours). Collect top 50 trending per platform per run.

### Stage 2: Pattern Analysis
- Aggregate last 24h of collected trending videos.
- Use Claude API (Anthropic) to classify videos by style: cinematic, talking-head, montage, text-heavy, etc.
- Calculate engagement velocity: `(likes + comments + shares) / hours_since_posted`.
- Cluster top-performing videos and extract patterns: format (aspect ratio), average duration, hook type (question, statement, visual shock), text overlay strategy (position, presence), audio type (voiceover, trending sound, original).
- Output a structured **Trend Report JSON** stored in PostgreSQL and pushed as summary to Google Sheets.

### Stage 3: Script Generation
- Read theme/product config and content references from Google Sheets.
- Use Claude API to generate a **Video Production Plan** containing:
  - `video_prompt`: detailed text-to-video prompt (scene descriptions, camera angles, lighting, motion, style)
  - `duration_target`: in seconds (from config range)
  - `aspect_ratio`: from config (default 9:16)
  - `text_overlays[]`: array of `{text, start_time, end_time, position, font_style}`
  - `voiceover_script`: full narration with timing markers
  - `hook_text`: first 3 seconds hook
  - `cta_text`: call-to-action for final seconds
  - `hashtags[]`: recommended based on trend data
  - `title`: platform upload title
  - `description`: platform upload description
- Use a prompt chain: Theme Interpretation → Trend Alignment → Scene Construction → Narration Writing → Text Overlay Design.

### Stage 4: Video Generation
- Call AI video generation API based on config. Default: **Google Veo 3.1 Fast** (`veo-3.1-fast-generate-preview`) via Gemini API at $0.15/sec.
- Also support: Veo 3.1 Standard ($0.40/sec), OpenAI Sora 2 ($0.10/sec), Sora 2 Pro ($0.30-$0.50/sec).
- Set aspect ratio to `9:16` for vertical. Resolution from config (720p default).
- Veo generates 8-second clips — chain multiple generations for longer videos using the extend API.
- Poll for async completion. Download MP4 to local storage.
- Quality gate: use Claude Vision API to check if the generated video matches the prompt intent. Retry with refined prompt up to 3 times on failure.

### Stage 5: Voiceover Generation
- Generate TTS audio from `voiceover_script` using **OpenAI TTS API** (`tts-1-hd` model, $30/1M chars).
- Also support: ElevenLabs (via API), Fish Audio / Open Audio S1, Google Gemini TTS — selectable in config.
- Output: MP3/WAV audio file synced to video duration.

### Stage 6: Video Composition
- Use **FFmpeg** to composite: raw AI video + voiceover audio + text overlays + optional background music.
- Text overlay specs: font (default Montserrat Bold), position, color (#FFFFFF default), shadow (on, 2px black), animation (fade-in default), timing, auto-scaling font size.
- Output: final MP4 (H.264 video, AAC audio), 9:16 or 16:9 per config.
- Generate thumbnail from a configurable frame.

### Stage 7: Review Queue
- Save final video to `/output/review/` directory.
- Update Google Sheets Generation Log: set status = `pending_review`.
- User manually reviews locally, then updates status in Google Sheets to `approved` or `rejected`.
- Approved videos moved to `/output/approved/`. Rejected to `/output/rejected/`.

### Stage 8: Publishing (Post-MVP, Config-gated)
- Gated by `auto_post` boolean in Google Sheets config (default: `false`).
- When enabled, upload approved videos to:
  - **TikTok** via Content Posting API (https://developers.tiktok.com/products/content-posting-api/) — supports FILE_UPLOAD and PULL_FROM_URL, requires OAuth 2.0 and `video.upload` scope. Start with draft/inbox upload mode. Direct post requires TikTok app audit.
  - **YouTube Shorts** via YouTube Data API v3 `videos.insert` (https://developers.google.com/youtube/v3/guides/uploading_a_video) — OAuth 2.0, `youtube.upload` scope. Add `#Shorts` to title/description. Resumable upload. 1,600 quota units per upload (10,000/day limit).
- Update Google Sheets status to `posted` with platform URL.

---

## Google Sheets Master Data (3 Sheets)

### Sheet 1: Config
| Column | Type | Example |
|---|---|---|
| theme | TEXT | "Capital Tax Reform: Why taxing wealth creates a fairer economy" |
| target_audience | TEXT | "US millennials and Gen-Z interested in economic justice" |
| tone | TEXT | "Persuasive, urgent, fact-driven, empowering" |
| cta | TEXT | "Share if you agree. Link in bio for the full report." |
| video_model | ENUM | veo-3.1-fast \| veo-3.1 \| sora-2 \| sora-2-pro |
| tts_model | ENUM | openai-tts-1-hd \| elevenlabs \| fish-audio |
| duration_range | TEXT | "15-30" |
| aspect_ratio | ENUM | 9:16 \| 16:9 \| 1:1 |
| resolution | ENUM | 720p \| 1080p |
| videos_per_day | INT | 1 |
| auto_post | BOOL | false |
| platforms | TEXT | "tiktok,youtube" |
| schedule_cron | TEXT | "0 10 * * *" |

### Sheet 2: Product/Content References
| Column | Type | Description |
|---|---|---|
| ref_type | ENUM | url \| image \| text \| product |
| ref_value | TEXT | URL, image path, or text content |
| ref_description | TEXT | What this reference is about |
| priority | INT | 1-5 (higher = more weight in prompts) |
| active | BOOL | Include in current generation cycle |

### Sheet 3: Generation Log (System writes here)
| Column | Type | Description |
|---|---|---|
| gen_id | VARCHAR | Unique generation ID |
| generated_at | TIMESTAMP | When the video was generated |
| theme_used | TEXT | Theme config snapshot |
| trend_pattern | TEXT | Which trend pattern was used |
| video_prompt | TEXT | Full video generation prompt |
| voiceover_text | TEXT | Full voiceover script |
| video_model | TEXT | Which AI model was used |
| cost_usd | DECIMAL | Total API cost for this generation |
| output_path | TEXT | Local file path of generated video |
| status | ENUM | pending_review \| approved \| rejected \| posted |
| posted_url | TEXT | Platform URL after posting |

Use **Google Sheets API v4** with a service account (JSON key file). Service account email must have Editor access to the spreadsheet.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Framework | FastAPI (async, OpenAPI auto-docs) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 16 |
| Video Processing | FFmpeg |
| Containers | Docker + Docker Compose |
| Config | Google Sheets API v4 |
| LLM | Claude API (Anthropic) — script generation + trend analysis + quality check |
| Video Gen | Google Veo 3.1 via Gemini API (primary), OpenAI Sora 2 (fallback) |
| TTS | OpenAI TTS tts-1-hd (primary), ElevenLabs / Fish Audio (configurable) |

---

## Docker Architecture

6 app services + 2 infra services in `docker-compose.yml`:

| Service | Role | Port |
|---|---|---|
| viralforge-orchestrator | Pipeline coordinator, cron scheduler, API endpoint for manual trigger | 8080 |
| viralforge-trend-scraper | TikTok (Apify) + YouTube (Data API v3) trend collection | 8081 |
| viralforge-analyzer | LLM-based trend pattern analysis | 8082 |
| viralforge-generator | Video generation (Veo/Sora) + TTS (OpenAI) API calls | 8083 |
| viralforge-composer | FFmpeg video composition + text overlays | 8084 |
| viralforge-publisher | Post-MVP auto-posting to TikTok/YouTube (disabled by default) | 8085 |
| postgres | PostgreSQL 16 database | 5432 |
| redis | Redis for Celery task queue + caching | 6379 |

---

## Directory Structure

```
viralforge/
├── docker-compose.yml
├── .env.example                  # Template for API keys
├── .env                          # Actual API keys (gitignored)
├── services/
│   ├── orchestrator/
│   │   ├── Dockerfile
│   │   ├── main.py               # FastAPI app, scheduler, pipeline coordinator
│   │   └── requirements.txt
│   ├── trend-scraper/
│   │   ├── Dockerfile
│   │   ├── main.py               # Apify client + YouTube API client
│   │   └── requirements.txt
│   ├── analyzer/
│   │   ├── Dockerfile
│   │   ├── main.py               # Claude API for trend analysis
│   │   └── requirements.txt
│   ├── generator/
│   │   ├── Dockerfile
│   │   ├── main.py               # Veo/Sora video gen + OpenAI TTS
│   │   └── requirements.txt
│   ├── composer/
│   │   ├── Dockerfile
│   │   ├── main.py               # FFmpeg composition
│   │   └── requirements.txt
│   └── publisher/
│       ├── Dockerfile
│       ├── main.py               # TikTok + YouTube upload APIs
│       └── requirements.txt
├── shared/
│   ├── models/                   # Pydantic models shared across services
│   ├── db/                       # SQLAlchemy models + Alembic migrations
│   └── utils/                    # Google Sheets client, logging, cost tracker
├── config/
│   ├── google-service-account.json
│   └── fonts/                    # Montserrat, etc. for text overlays
├── output/
│   ├── review/                   # Pending human review
│   ├── approved/                 # Approved for posting
│   └── rejected/                 # Rejected videos
└── data/
    ├── postgres/                 # Persistent DB volume
    └── redis/                    # Redis persistence
```

---

## Environment Variables

```env
# Required
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SERVICE_ACCOUNT_PATH=/app/config/google-service-account.json
GOOGLE_GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
APIFY_API_TOKEN=your_apify_token
POSTGRES_PASSWORD=your_db_password
POSTGRES_USER=viralforge
POSTGRES_DB=viralforge
REDIS_URL=redis://redis:6379/0

# Optional (post-MVP)
ELEVENLABS_API_KEY=
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
YOUTUBE_OAUTH_CREDENTIALS_PATH=
```

---

## Key Constraints

1. **Local Docker first.** Every service must run in Docker Compose with full pipeline visible via `docker compose logs -f`. No cloud dependencies except external APIs.
2. **Google Sheets is the single source of truth.** All config reads from Sheets. All generation output writes back to Sheets. No other config files for business logic.
3. **Dynamically prompt-able.** Changing the `theme` cell in Google Sheets must change all generated content without any code modifications. The system works for SaaS products, ideology campaigns, physical goods — anything.
4. **Video duration is configurable.** The `duration_range` field in config controls target length. The video generation module must chain multiple API calls (Veo 8-sec clips) to hit the target.
5. **Manual review before posting (MVP).** Generated videos go to `/output/review/`. No auto-posting until `auto_post` is set to `true` in config.
6. **Cost tracking.** Every API call cost must be logged. Per-video cost written to Google Sheets Generation Log.
7. **Ultra-realistic video style.** Video generation prompts must emphasize photorealistic, cinematic quality. No cartoon or stylized content unless explicitly requested in theme.
8. **English only** for all generated content (titles, descriptions, voiceover, text overlays).
9. **1 video per day** is the MVP target. System must handle this reliably with proper error handling and retries.
10. **GCP Cloud Run migration path.** Each Docker service maps 1:1 to a future Cloud Run service. Use environment variables for all config. No hardcoded paths.

---

## How to Run

```bash
# Setup
git clone <repo> && cd viralforge
cp .env.example .env
# Fill in API keys in .env

# Start
docker compose up -d

# Check all services are healthy
docker compose ps

# View full pipeline logs
docker compose logs -f orchestrator

# Trigger manual video generation
curl -X POST http://localhost:8080/api/generate

# Check output
ls -la output/review/
```

---

## API Endpoints (Orchestrator)

| Method | Path | Description |
|---|---|---|
| POST | /api/generate | Trigger a full pipeline run manually |
| GET | /api/status | Get current pipeline status and last run info |
| GET | /api/history | List recent generations with costs |
| POST | /api/approve/{gen_id} | Approve a video (moves to /output/approved/) |
| POST | /api/reject/{gen_id} | Reject a video (moves to /output/rejected/) |
| GET | /api/trends/latest | Get latest trend report |
| GET | /health | Health check |
