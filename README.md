# ViralForge

Automated short-form video generation pipeline. Collects trending content from TikTok and YouTube, analyzes patterns with AI, generates scripts, creates video clips with voiceover, and composes publish-ready vertical videos.

## Prerequisites

- Python 3.9+
- Docker Desktop (optional, for full stack with PostgreSQL + Redis)

## Quick Start (Local)

Local mode uses SQLite and runs without Docker, Redis, or PostgreSQL.

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run database migrations

```bash
alembic upgrade head
```

### 3. Start the API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Start the Celery worker (separate terminal)

```bash
source venv/bin/activate
celery -A app.worker.celery_app worker --pool=threads --concurrency=4 --loglevel=info
```

### 5. Verify it's running

```bash
curl -s "http://localhost:8000/api/health" | python3 -m json.tool
```

You should see `"status": "healthy"`.

## Quick Start (Docker)

Docker mode uses PostgreSQL and Redis for production-like operation.

```bash
docker-compose up
```

This starts 4 containers: PostgreSQL, Redis, API server, and Celery worker. Migrations run automatically on boot.

The API is available at `http://localhost:8000`.

## Usage

### Run the full pipeline

```bash
curl -s -X POST "http://localhost:8000/api/generate" | python3 -m json.tool
```

This triggers the 5-stage pipeline:

1. **Trend Collection** — Scrapes trending TikTok/YouTube Shorts videos
2. **Trend Analysis** — AI analyzes trends for patterns and engagement velocity
3. **Content Generation** — Generates script, video clips, and voiceover audio
4. **Composition** — Combines everything into a final 9:16 MP4 with text overlays
5. **Review** — Saves output to `output/review/` for approval

The response includes a `job_id`. Use it to track progress:

```bash
curl -s "http://localhost:8000/api/jobs/1" | python3 -m json.tool
```

Poll until `status` shows `completed`.

### Review output

List generated videos:

```bash
curl -s "http://localhost:8000/api/videos" | python3 -m json.tool
```

Approve a video (moves to `output/approved/`):

```bash
curl -s -X POST "http://localhost:8000/api/videos/1/approve" | python3 -m json.tool
```

Reject a video (moves to `output/rejected/`):

```bash
curl -s -X POST "http://localhost:8000/api/videos/1/reject" | python3 -m json.tool
```

### Manual per-stage endpoints

For debugging, you can trigger each stage individually:

```bash
# Collect trending videos
curl -s -X POST "http://localhost:8000/api/collect-trends"

# Analyze trends
curl -s -X POST "http://localhost:8000/api/analyze-trends"

# Generate content (script + video + voiceover)
curl -s -X POST "http://localhost:8000/api/generate-content"

# Compose final video
curl -s -X POST "http://localhost:8000/api/compose-video?script_id=1&video_path=path.mp4&audio_path=path.mp3"
```

## Configuration

### Theme / Product Config

Edit `config/sample-data.yml` to define what videos are about:

```yaml
config:
  product_name: "HydroGlow Smart Bottle"
  tagline: "Stay hydrated, stay clean, stay informed"
  target_audience: "Health-conscious millennials and fitness enthusiasts"
  tone: "energetic and aspirational"
  style: "cinematic"
  video_duration_seconds: 20
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_MOCK_DATA` | Use mock data instead of real APIs | `true` |
| `ANTHROPIC_API_KEY` | Claude API key (trend analysis + script generation) | — |
| `APIFY_API_TOKEN` | Apify API token (TikTok scraping) | — |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | — |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///viralforge.db` |
| `REDIS_URL` | Redis connection (leave empty for local SQLite mode) | — |
| `CELERY_BROKER_URL` | Celery broker URL | `sqla+sqlite:///celery_broker.db` |

### Mock Mode

By default, `USE_MOCK_DATA=true`. This means:

- Trend collection returns pre-built sample data (no TikTok/YouTube API calls)
- Trend analysis returns mock patterns (no Claude API calls)
- Video generation creates solid-color test clips (no Stable Video Diffusion)
- Voiceover generates silent audio (no OpenAI TTS calls)

This lets you run the entire pipeline without any API keys.

### Real API Mode

Set `USE_MOCK_DATA=false` in `.env` and provide the required API keys. The pipeline will then make real API calls for trend scraping, AI analysis, video generation, and voiceover synthesis.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check with service status |
| POST | `/api/generate` | Run full 5-stage pipeline |
| GET | `/api/jobs` | List all pipeline jobs |
| GET | `/api/jobs/{id}` | Get job status and progress |
| POST | `/api/jobs/{id}/retry` | Retry a failed job from last checkpoint |
| POST | `/api/collect-trends` | Trigger trend collection |
| GET | `/api/trends` | List collected trends |
| POST | `/api/analyze-trends` | Trigger trend analysis |
| GET | `/api/trend-reports` | List trend reports |
| GET | `/api/trend-reports/latest` | Get latest trend report |
| POST | `/api/generate-content` | Generate script + video + voiceover |
| GET | `/api/scripts` | List generated scripts |
| GET | `/api/scripts/{id}` | Get script details |
| POST | `/api/compose-video` | Compose final video from components |
| GET | `/api/videos` | List generated videos |
| GET | `/api/videos/{id}` | Get video details |
| POST | `/api/videos/{id}/approve` | Approve video for publishing |
| POST | `/api/videos/{id}/reject` | Reject video |
| POST | `/api/test-task` | Test Celery worker connectivity |

## Project Structure

```
app/
  main.py                  # FastAPI application
  config.py                # Settings (env vars, defaults)
  models.py                # SQLAlchemy models (Job, Trend, Script, Video, etc.)
  schemas.py               # Pydantic schemas
  tasks.py                 # Celery tasks (pipeline stages)
  celery_app.py            # Celery application setup
  api/
    routes.py              # All API endpoints
  services/
    config_reader.py       # Theme/product config from YAML
    script_generator.py    # Claude AI script generation (5-step prompt chain)
    trend_collector/       # TikTok + YouTube trend scrapers
    trend_analyzer/        # AI trend pattern analysis
    video_generator/       # Video clip generation (mock + real providers)
    voiceover_generator/   # TTS audio generation (mock + OpenAI)
    video_compositor/      # Final video composition (MoviePy/FFmpeg)
config/
  sample-data.yml          # Theme and product configuration
output/
  review/                  # Generated videos awaiting approval
  approved/                # Approved videos
  rejected/                # Rejected videos
```

## License

Private project.
