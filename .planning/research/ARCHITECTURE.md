# Architecture Research

**Domain:** AI-Powered Video Generation Pipeline
**Researched:** 2026-02-13
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Google       │  │ Admin        │  │ External     │               │
│  │ Sheets       │  │ Dashboard    │  │ Integrations │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
├─────────┴──────────────────┴──────────────────┴───────────────────────┤
│                       ORCHESTRATION LAYER                             │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                  Orchestrator Service                        │    │
│  │  - Workflow management (Saga pattern)                        │    │
│  │  - Job scheduling & state tracking                           │    │
│  │  - Error handling & compensation                             │    │
│  └───────────────────┬─────────────────────────────────────────┘    │
│                      │                                                │
├──────────────────────┴────────────────────────────────────────────────┤
│                    PROCESSING SERVICES LAYER                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Trend   │  │ Pattern  │  │  Script  │  │  Video   │             │
│  │ Scraper  │→ │ Analyzer │→ │Generator │→ │Generator │→            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
│                                                                       │
│  ┌──────────┐  ┌──────────┐                                          │
│  │  Video   │  │Publisher │                                          │
│→ │ Composer │→ │ Service  │                                          │
│  └──────────┘  └──────────┘                                          │
│                                                                       │
├───────────────────────────────────────────────────────────────────────┤
│                      MESSAGE & TASK LAYER                             │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  Redis                                                      │      │
│  │  - Celery broker (task queue)                              │      │
│  │  - Job state & progress tracking                           │      │
│  │  - Service-to-service communication                        │      │
│  │  - Caching (API responses, intermediate results)           │      │
│  └────────────────────────────────────────────────────────────┘      │
├───────────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                                    │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  PostgreSQL (Single Shared Database)                       │      │
│  │  - Jobs table (pipeline state)                             │      │
│  │  - Trends table (scraped data)                             │      │
│  │  - Scripts table (generated content)                       │      │
│  │  - Videos table (asset metadata)                           │      │
│  │  - Audit logs & analytics                                  │      │
│  └────────────────────────────────────────────────────────────┘      │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Orchestrator Service** | Centralized workflow coordinator, job lifecycle management, error handling & compensation transactions, exposes REST API for external clients | FastAPI app with Celery tasks for async operations, implements Saga orchestration pattern |
| **Trend Scraper** | Fetch trending data from TikTok/YouTube APIs, normalize & store trend data, trigger analysis pipeline | FastAPI service with scheduled Celery tasks, API client libraries |
| **Pattern Analyzer** | Analyze trends for patterns, identify viral characteristics, generate insights for script generation | FastAPI service with ML/AI model integration (OpenAI API), receives trend data via Celery task |
| **Script Generator** | Generate video scripts based on patterns, validate script quality, format for video production | FastAPI service with LLM integration (GPT-4), content validation logic |
| **Video Generator** | Generate video assets from scripts, handle text-to-video AI generation, store video files | FastAPI service with AI video generation API integration, S3/GCS for asset storage |
| **Video Composer** | Combine video, voiceover, subtitles, add watermarks & branding, export final video | FastAPI service with FFmpeg for video processing, MoviePy for composition |
| **Publisher Service** | Upload videos to target platforms, schedule releases, handle platform-specific formatting | FastAPI service with platform API integrations (TikTok, YouTube), retry logic |
| **PostgreSQL** | Single shared database for all services, stores job state, trend data, scripts, video metadata | PostgreSQL with connection pooling (pgBouncer recommended for production) |
| **Redis** | Celery message broker, caching layer, job state tracking, inter-service communication | Redis with persistence enabled for durability |

## Recommended Project Structure

```
/
├── docker-compose.yml                    # Local development orchestration
├── docker-compose.prod.yml              # Production overrides (Cloud Run references)
├── .env.example                         # Environment template
│
├── services/
│   ├── orchestrator/                    # Central workflow coordinator
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py                  # FastAPI app entry
│   │   │   ├── api/                     # REST endpoints
│   │   │   │   ├── jobs.py              # Job CRUD operations
│   │   │   │   └── webhooks.py          # External event handlers
│   │   │   ├── workflows/               # Saga orchestration logic
│   │   │   │   ├── video_pipeline.py    # Main pipeline workflow
│   │   │   │   └── compensation.py      # Rollback handlers
│   │   │   ├── tasks/                   # Celery tasks
│   │   │   │   └── orchestration.py     # Task coordination
│   │   │   ├── models/                  # Database models (SQLAlchemy)
│   │   │   └── schemas/                 # Pydantic request/response schemas
│   │   └── requirements.txt
│   │
│   ├── trend-scraper/                   # Trend data collection
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/                     # Health check endpoint
│   │   │   ├── scrapers/                # Platform-specific scrapers
│   │   │   │   ├── tiktok.py
│   │   │   │   └── youtube.py
│   │   │   ├── tasks/                   # Celery tasks
│   │   │   │   ├── scrape.py            # Scheduled scraping
│   │   │   │   └── normalize.py         # Data normalization
│   │   │   └── models/                  # Database models
│   │   └── requirements.txt
│   │
│   ├── analyzer/                        # Pattern analysis
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── analyzers/               # Analysis engines
│   │   │   │   ├── engagement.py        # Engagement metrics
│   │   │   │   ├── content.py           # Content analysis
│   │   │   │   └── trends.py            # Trend identification
│   │   │   ├── tasks/                   # Celery tasks
│   │   │   │   └── analyze.py           # Analysis execution
│   │   │   └── models/
│   │   └── requirements.txt
│   │
│   ├── generator/                       # Script generation
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── generators/              # Content generation
│   │   │   │   ├── script.py            # Script creation
│   │   │   │   └── prompts.py           # LLM prompt templates
│   │   │   ├── tasks/                   # Celery tasks
│   │   │   │   └── generate.py          # Generation execution
│   │   │   └── models/
│   │   └── requirements.txt
│   │
│   ├── video-generator/                 # AI video generation
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── generators/              # Video generation clients
│   │   │   │   ├── runwayml.py          # Runway ML integration
│   │   │   │   ├── stable_diffusion.py  # SD Video integration
│   │   │   │   └── voiceover.py         # TTS integration
│   │   │   ├── tasks/                   # Celery tasks (long-running)
│   │   │   │   └── generate_video.py
│   │   │   └── models/
│   │   └── requirements.txt
│   │
│   ├── composer/                        # Video composition & editing
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   ├── composers/               # Composition logic
│   │   │   │   ├── editor.py            # FFmpeg wrapper
│   │   │   │   ├── subtitles.py         # Subtitle generation
│   │   │   │   └── watermark.py         # Branding overlay
│   │   │   ├── tasks/                   # Celery tasks
│   │   │   │   └── compose.py           # Video assembly
│   │   │   └── models/
│   │   └── requirements.txt
│   │
│   └── publisher/                       # Platform publishing
│       ├── Dockerfile
│       ├── app/
│       │   ├── main.py
│       │   ├── api/
│       │   ├── publishers/              # Platform integrations
│       │   │   ├── tiktok.py            # TikTok upload
│       │   │   └── youtube.py           # YouTube upload
│       │   ├── tasks/                   # Celery tasks
│       │   │   └── publish.py           # Upload & scheduling
│       │   └── models/
│       └── requirements.txt
│
├── shared/                              # Shared utilities
│   ├── __init__.py
│   ├── database.py                      # SQLAlchemy session factory
│   ├── celery_app.py                    # Celery app factory
│   ├── config.py                        # Environment config
│   ├── models/                          # Shared database models
│   │   ├── job.py
│   │   ├── trend.py
│   │   ├── script.py
│   │   └── video.py
│   └── schemas/                         # Shared Pydantic schemas
│
├── migrations/                          # Alembic database migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
└── tests/                               # Integration tests
    ├── test_pipeline.py
    └── test_services.py
```

### Structure Rationale

- **services/**: Each microservice is self-contained with its own Dockerfile, enabling independent deployment to Cloud Run
- **shared/**: Common code shared via Python package or Docker volume mount to avoid duplication
- **migrations/**: Centralized database migrations since we use a single shared database
- **docker-compose.yml**: Mirrors production architecture locally, making 1:1 mapping to Cloud Run straightforward
- **Celery tasks in each service**: Allows long-running operations to run asynchronously without blocking HTTP requests

## Architectural Patterns

### Pattern 1: Saga Orchestration (Recommended)

**What:** Centralized orchestrator manages the entire video generation pipeline as a distributed transaction with compensating actions for failures.

**When to use:** Complex workflows with 6+ dependent stages where you need clear visibility into state, centralized error handling, and coordinated rollback.

**Trade-offs:**
- **Pros:** Single source of truth for workflow state, easier debugging, centralized retry/timeout logic, clear transaction boundaries
- **Cons:** Orchestrator becomes a critical dependency (single point of failure), requires high availability setup

**Example:**
```python
# services/orchestrator/app/workflows/video_pipeline.py
from celery import chain, group
from shared.celery_app import celery_app

class VideoPipelineSaga:
    """Orchestrates the 8-stage video generation pipeline"""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.state = {}

    def execute(self):
        """Execute saga with compensation on failure"""
        try:
            # Sequential pipeline execution
            pipeline = chain(
                scrape_trends.s(self.job_id),
                analyze_patterns.s(self.job_id),
                generate_script.s(self.job_id),
                generate_video.s(self.job_id),
                generate_voiceover.s(self.job_id),
                compose_video.s(self.job_id),
                review_video.s(self.job_id),  # Can be manual or automated
                publish_video.s(self.job_id),
            )

            result = pipeline.apply_async()
            return result

        except Exception as e:
            # Execute compensation transactions
            self.compensate(e)

    def compensate(self, error):
        """Rollback completed stages on failure"""
        if self.state.get('video_published'):
            unpublish_video.apply_async((self.job_id,))
        if self.state.get('video_composed'):
            delete_composed_video.apply_async((self.job_id,))
        # Continue rolling back in reverse order...
```

**Why this is recommended for ViralForge:** Sequential 8-stage pipeline with dependencies requires orchestrator to track state, handle failures gracefully, and provide visibility into progress.

### Pattern 2: Database-as-Communication (Hybrid Approach)

**What:** Services share a single PostgreSQL database for state persistence and job coordination, while using Redis + Celery for async task execution.

**When to use:** When starting with a greenfield project where services are tightly coupled in a sequential pipeline, and you want to avoid the complexity of event sourcing or database-per-service.

**Trade-offs:**
- **Pros:** Simpler to implement, strong consistency, easier transactions across stages, single source of truth
- **Cons:** Services coupled via shared schema, harder to scale individual services independently, potential for schema migration conflicts

**Example:**
```python
# shared/models/job.py
from sqlalchemy import Column, String, Enum, TIMESTAMP, JSON
from shared.database import Base
import enum

class JobStatus(enum.Enum):
    PENDING = "pending"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_VIDEO = "generating_video"
    COMPOSING = "composing"
    REVIEWING = "reviewing"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    stage_data = Column(JSON)  # Intermediate results from each stage
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    # Each service updates this table as it progresses
    # Orchestrator monitors state transitions
```

**Why this works:** ViralForge has sequential dependencies where each stage needs output from the previous stage. Shared database provides transactional guarantees and simplifies state management.

### Pattern 3: Task Queue with Redis (FastAPI + Celery)

**What:** HTTP requests to FastAPI trigger Celery tasks that execute long-running operations asynchronously, with Redis as the message broker.

**When to use:** Operations that take more than a few seconds (AI generation, video processing, API calls) that would timeout HTTP connections.

**Trade-offs:**
- **Pros:** Fast API response times, horizontal scaling of workers, built-in retry/failure handling, monitoring via Flower
- **Cons:** Eventual consistency, need to poll for results or implement webhooks, additional complexity of message queue

**Example:**
```python
# services/generator/app/tasks/generate.py
from shared.celery_app import celery_app
from openai import OpenAI

@celery_app.task(bind=True, max_retries=3)
def generate_script(self, job_id: str, analysis_data: dict):
    """Generate video script from pattern analysis"""
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Update job status
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = JobStatus.GENERATING_SCRIPT
        db.commit()

        # Call LLM
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a viral video scriptwriter."},
                {"role": "user", "content": f"Create a script based on: {analysis_data}"}
            ]
        )

        # Store result
        script = Script(job_id=job_id, content=response.choices[0].message.content)
        db.add(script)
        db.commit()

        return {"job_id": job_id, "script_id": script.id}

    except Exception as e:
        # Celery auto-retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

### Pattern 4: One Process Per Container (Cloud Run Ready)

**What:** Each Docker service runs a single FastAPI/Uvicorn process, letting container orchestration handle replication and scaling.

**When to use:** Deploying to Cloud Run, Kubernetes, or any container orchestration platform. Required for serverless platforms.

**Trade-offs:**
- **Pros:** Aligns with Cloud Run architecture, simplified resource management, independent service scaling, easier monitoring
- **Cons:** More containers to manage (but orchestration handles this)

**Example:**
```dockerfile
# services/orchestrator/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app /app/app
COPY ../shared /app/shared

# Single process per container
CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
```

**Why this matters:** ViralForge explicitly targets Cloud Run deployment. Each Docker Compose service maps 1:1 to a Cloud Run service, so single-process containers are required.

## Data Flow

### Sequential Pipeline Flow

```
┌─────────────────┐
│  Google Sheets  │ (Master data source)
│  OR Dashboard   │
└────────┬────────┘
         │ POST /jobs (create new video request)
         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Service                     │
│  1. Create Job record (status: PENDING)                     │
│  2. Trigger saga execution via Celery                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓ Celery task chain
┌───────────────────────────────────────────────────────────────┐
│                   STAGE 1: Trend Collection                   │
│  Trend Scraper Service                                        │
│  - Celery task: scrape_trends(job_id)                        │
│  - Fetch TikTok/YouTube trending data                        │
│  - Store in PostgreSQL: trends table                         │
│  - Update Job: status = SCRAPING                             │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass trend_ids to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                   STAGE 2: Pattern Analysis                   │
│  Analyzer Service                                             │
│  - Celery task: analyze_patterns(job_id, trend_ids)          │
│  - Load trends from PostgreSQL                               │
│  - Run ML/AI analysis (engagement, content patterns)         │
│  - Store insights in PostgreSQL                              │
│  - Update Job: status = ANALYZING                            │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass analysis_id to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                 STAGE 3: Script Generation                    │
│  Generator Service                                            │
│  - Celery task: generate_script(job_id, analysis_id)         │
│  - Load analysis from PostgreSQL                             │
│  - Call OpenAI GPT-4 for script creation                     │
│  - Store script in PostgreSQL: scripts table                 │
│  - Update Job: status = GENERATING_SCRIPT                    │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass script_id to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                 STAGE 4: Video Generation                     │
│  Video Generator Service                                      │
│  - Celery task: generate_video(job_id, script_id)            │
│  - Load script from PostgreSQL                               │
│  - Call AI video generation API (Runway ML, Stable Video)    │
│  - Upload raw video to GCS/S3                                │
│  - Store video metadata in PostgreSQL: videos table          │
│  - Update Job: status = GENERATING_VIDEO                     │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass video_id to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                 STAGE 5: Voiceover Generation                 │
│  Video Generator Service (same service, different task)      │
│  - Celery task: generate_voiceover(job_id, script_id)        │
│  - Call TTS API (ElevenLabs, Google TTS)                     │
│  - Upload audio to GCS/S3                                    │
│  - Store audio metadata in PostgreSQL                        │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass video_id + audio_id to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                   STAGE 6: Video Composition                  │
│  Composer Service                                             │
│  - Celery task: compose_video(job_id, video_id, audio_id)    │
│  - Download raw video and audio from GCS/S3                  │
│  - Use FFmpeg to:                                            │
│    * Merge video + voiceover                                 │
│    * Add subtitles (via subtitle.py)                         │
│    * Add watermark/branding (via watermark.py)               │
│  - Upload final video to GCS/S3                              │
│  - Update PostgreSQL with final video URL                    │
│  - Update Job: status = COMPOSING                            │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass final_video_id to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                      STAGE 7: Review                          │
│  Orchestrator Service (approval gate)                        │
│  - Update Job: status = REVIEWING                            │
│  - Notification to admin for approval (webhook/email)        │
│  - Wait for approval (manual or automated quality check)     │
│  - If approved: proceed to publish                           │
│  - If rejected: trigger compensation (saga rollback)         │
└───────┬───────────────────────────────────────────────────────┘
        │ Pass final_video_id to next stage
        ↓
┌───────────────────────────────────────────────────────────────┐
│                     STAGE 8: Publishing                       │
│  Publisher Service                                            │
│  - Celery task: publish_video(job_id, final_video_id)        │
│  - Download final video from GCS/S3                          │
│  - Upload to TikTok/YouTube via platform APIs                │
│  - Schedule release if specified                             │
│  - Store publication status in PostgreSQL                    │
│  - Update Job: status = COMPLETED                            │
└───────┬───────────────────────────────────────────────────────┘
        │ Completion notification
        ↓
┌───────────────────────────────────────────────────────────────┐
│                        Orchestrator                           │
│  - Update Job: status = COMPLETED                            │
│  - Send webhook/notification to Google Sheets or Dashboard   │
│  - Log analytics                                             │
└───────────────────────────────────────────────────────────────┘
```

### Cross-Cutting Data Flows

#### Job State Tracking
```
PostgreSQL (jobs table)
    ↑ (read current status)
    ↓ (update status)
All Services ← query job state before executing
```

#### Caching Layer
```
Service → Check Redis cache → Hit? Return cached data
                            → Miss? Query PostgreSQL → Cache result → Return
```

#### Task Queue Flow
```
FastAPI Endpoint → Enqueue Celery task → Redis (broker)
                                            ↓
                                       Celery Worker (pulls task)
                                            ↓
                                       Execute task logic
                                            ↓
                                       Update PostgreSQL
```

### Key Data Flow Principles

1. **Orchestrator as Controller**: Orchestrator doesn't process data directly; it coordinates task execution via Celery chains
2. **Database as State Store**: PostgreSQL is single source of truth for job state, not Redis
3. **Redis for Transient Data**: Task queues, temporary caching, not persistent storage
4. **File Storage External**: Videos/audio stored in GCS/S3, only metadata in PostgreSQL
5. **Async Communication**: Services don't call each other's HTTP APIs; they communicate via Celery tasks

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-100 jobs/day** | Single Docker Compose deployment on one VM, 1 worker per service, shared PostgreSQL and Redis instances |
| **100-1K jobs/day** | Migrate to Cloud Run, scale video-generator and composer services to 2-3 instances, use Cloud SQL for PostgreSQL with connection pooling (pgBouncer), use Memorystore for Redis |
| **1K-10K jobs/day** | Scale Celery workers independently (10+ for video-generator/composer), implement Redis Cluster for high availability, add CDN for video delivery (Cloud CDN), consider database read replicas |
| **10K+ jobs/day** | Split video-generator into separate services per AI provider, implement CQRS pattern (separate read/write databases), consider database-per-service for independence, add Kafka for event streaming |

### Scaling Priorities

1. **First bottleneck: Video Generation & Composition** - These are CPU/GPU intensive and slow (minutes per video). Scale by:
   - Running multiple Celery workers for video-generator and composer services
   - Using Cloud Run's auto-scaling (up to max instances)
   - Implementing job prioritization queue

2. **Second bottleneck: Database Connections** - All services share one PostgreSQL. Scale by:
   - Adding pgBouncer connection pooling
   - Implementing database query caching in Redis
   - Moving read-heavy queries to read replicas
   - Eventually splitting to database-per-service if coupling becomes problematic

3. **Third bottleneck: External API Rate Limits** - TikTok, YouTube, OpenAI APIs have rate limits. Scale by:
   - Implementing rate limiter in orchestrator
   - Queueing publish jobs with backoff
   - Using multiple API keys/accounts if allowed

## Anti-Patterns

### Anti-Pattern 1: Direct Service-to-Service HTTP Calls

**What people do:** Configure services to call each other's HTTP endpoints directly (e.g., Orchestrator calls `http://analyzer:8000/analyze`)

**Why it's wrong:**
- Tight coupling makes deployment order critical
- Synchronous calls cause cascading failures and timeouts
- Difficult to implement retries and compensation
- Doesn't work well with Cloud Run's autoscaling (cold starts)

**Do this instead:** Use Celery task chains for service orchestration. Orchestrator enqueues tasks, workers process asynchronously.

```python
# BAD: Direct HTTP calls
response = requests.post("http://analyzer:8000/analyze", json=data)
result = response.json()

# GOOD: Celery task chain
from tasks.analyze import analyze_patterns
result = analyze_patterns.apply_async((job_id, data))
```

### Anti-Pattern 2: Storing Large Files in PostgreSQL

**What people do:** Store video files, audio files, or images as BYTEA or large text columns in PostgreSQL

**Why it's wrong:**
- Bloats database, slowing down all queries
- PostgreSQL has ~1GB limit for TOAST storage
- Makes backups extremely large and slow
- Wastes database connections for file uploads

**Do this instead:** Store files in object storage (GCS/S3), save only metadata and URLs in PostgreSQL

```python
# BAD: Storing in database
video.file_data = video_bytes  # Don't do this!

# GOOD: Store in object storage
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('viralforge-videos')
blob = bucket.blob(f'videos/{job_id}/final.mp4')
blob.upload_from_string(video_bytes)

video.storage_url = blob.public_url  # Store URL in database
```

### Anti-Pattern 3: Running Multiple Workers in One Container

**What people do:** Use `CMD ["fastapi", "run", "app/main.py", "--workers", "4"]` in Dockerfile for Cloud Run

**Why it's wrong:**
- Cloud Run already handles horizontal scaling (multiple containers)
- Multiple workers share container CPU quota inefficiently
- Breaks Cloud Run's autoscaling assumptions
- Makes resource allocation unpredictable

**Do this instead:** Single process per container, let Cloud Run scale container count

```dockerfile
# BAD: Multiple workers
CMD ["fastapi", "run", "app/main.py", "--workers", "4"]

# GOOD: Single worker, scale via Cloud Run
CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
```

### Anti-Pattern 4: Polling for Job Status

**What people do:** Client polls `GET /jobs/{job_id}` every few seconds to check if video is ready

**Why it's wrong:**
- Wastes API quota and database connections
- High latency (up to polling interval)
- Creates unnecessary load during long-running jobs

**Do this instead:** Implement webhooks or use WebSockets for status updates

```python
# BAD: Client-side polling
while True:
    response = requests.get(f"/jobs/{job_id}")
    if response.json()["status"] == "completed":
        break
    time.sleep(5)

# GOOD: Webhook callback
@app.post("/webhooks/job-complete")
async def job_complete(webhook_data: JobCompleteWebhook):
    # Orchestrator calls this when job completes
    notify_client(webhook_data.job_id, webhook_data.video_url)
```

### Anti-Pattern 5: Shared Database Without Schema Versioning

**What people do:** Multiple services directly modify shared database schema without migration coordination

**Why it's wrong:**
- Schema changes break other services unexpectedly
- Difficult to rollback deployments
- No audit trail of schema changes
- Testing becomes unreliable

**Do this instead:** Centralized migrations with Alembic, versioned and tested before deployment

```bash
# Centralized migrations directory
/migrations/
  alembic.ini
  env.py
  versions/
    001_initial.py
    002_add_trends_table.py
    003_add_job_stage_data.py

# Run migrations before deploying services
docker-compose run migrations alembic upgrade head
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Google Sheets API** | REST API via gspread library | Read master data, write back video URLs. Use service account auth. Cache reads in Redis (15min TTL). |
| **TikTok API** | OAuth + REST API | Rate limit: 100 uploads/day per account. Implement queue with backoff. Requires developer account approval. |
| **YouTube Data API** | OAuth + REST API | Rate limit: 10,000 quota units/day. Uploads cost 1,600 units. Monitor quota usage. |
| **OpenAI API** | REST API with API key | Use GPT-4 for script generation. Implement timeout (60s) and retries (3x). Track token usage for cost control. |
| **Runway ML / Stable Video** | REST API with API key | Video generation takes 2-5 minutes. Use webhooks for completion notification to avoid polling. |
| **ElevenLabs / Google TTS** | REST API | Voice generation. Cache common phrases. Monitor character usage for billing. |
| **GCS / S3** | SDK (google-cloud-storage / boto3) | Store video/audio files. Use signed URLs for temporary access. Implement lifecycle policies (delete after 30 days). |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Orchestrator ↔ All Services** | Celery tasks (via Redis) | Orchestrator enqueues tasks, services execute. No direct HTTP calls. |
| **All Services ↔ PostgreSQL** | SQLAlchemy ORM | Shared models in `/shared/models/`. Use connection pooling. Read-heavy queries should cache in Redis. |
| **All Services ↔ Redis** | Direct Redis client | Used for Celery broker, caching, and temporary state. Not for persistent data. |
| **Services ↔ Cloud Storage** | SDK with credentials | Each service has read/write access to video storage bucket. Use service account keys. |
| **Orchestrator ↔ External Clients** | REST API (FastAPI) | Only orchestrator exposes public API. Other services are internal. |

### Docker Compose to Cloud Run Migration Path

The architecture is designed for 1:1 mapping:

```yaml
# docker-compose.yml (local)
services:
  orchestrator:
    build: ./services/orchestrator
    ports: ["8000:8080"]

  trend-scraper:
    build: ./services/trend-scraper

  # ... other services

# Maps to:
# Cloud Run:
#   - viralforge-orchestrator (public, with load balancer)
#   - viralforge-trend-scraper (internal)
#   - viralforge-analyzer (internal)
#   - viralforge-generator (internal)
#   - viralforge-video-generator (internal)
#   - viralforge-composer (internal)
#   - viralforge-publisher (internal)
#
# Cloud SQL: PostgreSQL instance
# Memorystore: Redis instance
# GCS: viralforge-videos bucket
```

**Key migration considerations:**
- Local: Use `docker-compose.yml` for development
- Production: Deploy each service to Cloud Run via `gcloud run deploy`
- Service discovery: Cloud Run uses internal DNS for service-to-service (but we avoid this via Celery)
- Secrets: Local uses `.env`, Cloud Run uses Secret Manager
- Networking: Local uses Docker network, Cloud Run uses VPC connector for Cloud SQL/Memorystore access

## Build Order and Dependencies

### Suggested Build Order

For greenfield implementation, build in this order to minimize rework:

#### Phase 1: Foundation (Week 1-2)
1. **Shared library** (`/shared/`)
   - Database models
   - Celery app factory
   - Configuration management
   - Pydantic schemas

2. **Docker Compose setup**
   - PostgreSQL service
   - Redis service
   - Basic networking

3. **Database migrations** (`/migrations/`)
   - Alembic setup
   - Initial schema (jobs, trends, scripts, videos)

#### Phase 2: Core Services (Week 3-4)
4. **Orchestrator service**
   - FastAPI app with REST API
   - Job CRUD operations
   - Basic Celery task for testing
   - Health check endpoints

5. **Trend Scraper service**
   - Platform API integrations (TikTok, YouTube)
   - Celery task for scheduled scraping
   - Data normalization and storage

#### Phase 3: Processing Pipeline (Week 5-7)
6. **Analyzer service**
   - Pattern analysis algorithms
   - OpenAI integration for insights
   - Celery task for async analysis

7. **Generator service**
   - Script generation with GPT-4
   - Template management
   - Content validation

8. **Video Generator service**
   - AI video generation API integration
   - Voiceover generation (TTS)
   - File upload to GCS/S3

#### Phase 4: Post-Processing (Week 8-9)
9. **Composer service**
   - FFmpeg video processing
   - Subtitle generation
   - Watermark overlay
   - Video assembly

#### Phase 5: Publishing & Workflow (Week 10-11)
10. **Publisher service**
    - Platform upload integrations
    - Scheduling logic
    - Error handling and retries

11. **Saga orchestration** (in Orchestrator)
    - Pipeline coordination
    - Compensation transactions
    - Error recovery

#### Phase 6: Production Readiness (Week 12+)
12. **Monitoring & Observability**
    - Flower for Celery monitoring
    - Logging (structured JSON)
    - Metrics (Prometheus/Cloud Monitoring)

13. **Cloud Run deployment**
    - Migrate from Docker Compose
    - Configure Cloud SQL and Memorystore
    - Set up CI/CD pipeline

### Dependency Graph

```
                          ┌─────────────┐
                          │   Shared    │
                          │   Library   │
                          └──────┬──────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ↓                  ↓                  ↓
      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
      │    Docker    │   │   Database   │   │  Orchestrator│
      │   Compose    │   │  Migrations  │   │    Service   │
      └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
             │                  │                   │
             └──────────┬───────┴───────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ↓              ↓              ↓
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Trend   │  │ Analyzer │  │Generator │
   │ Scraper  │  │          │  │          │
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ↓            ↓            ↓
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Video   │  │ Composer │  │Publisher │
   │Generator │  │          │  │          │
   └──────────┘  └──────────┘  └──────────┘
```

**Critical path:** Shared → Database → Orchestrator → Processing Services → Saga Workflow

**Parallelizable:** Once Orchestrator is built, processing services (Scraper, Analyzer, Generator, Video Generator, Composer, Publisher) can be built in parallel by different developers, as long as they follow the shared models and task interface contracts.

## Confidence and Sources

**Confidence Level: HIGH**

This architecture is based on:
- Official FastAPI documentation (Docker deployment patterns)
- Official Celery documentation (application architecture)
- Multiple verified 2026 sources on microservices patterns
- AWS, Azure, and Google Cloud reference architectures
- Production examples from Netflix and other tech companies

**Key Sources:**

### Microservices & AI Pipelines
- [Microservices Are the Only Way to Scale AI Agents](https://www.startuphub.ai/ai-news/ai-video/2026/microservices-are-the-only-way-to-scale-ai-agents/) - StarupHub (2026)
- [Microservices Architecture for AI Applications: Scalable Patterns and 2025 Trends](https://medium.com/@meeran03/microservices-architecture-for-ai-applications-scalable-patterns-and-2025-trends-5ac273eac232) - Medium (2025)
- [AI Architectures in 2026: Components, Patterns, and Practical Code](https://medium.com/@angelosorte1/ai-architectures-in-2026-components-patterns-and-practical-code-1df838dab854) - Medium (2026)
- [From AI Pilots to Production Reality: Architecture Lessons from 2025 and What 2026 Demands](https://www.dataa.dev/2026/01/01/from-ai-pilots-to-production-reality-architecture-lessons-from-2025-and-what-2026-demands/) - C4 Blog (2026)

### FastAPI + Celery Patterns
- [FastAPI Best Practices for Production: Complete 2026 Guide](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026) - FastLaunchAPI (2026)
- [The Complete Guide to Background Processing with FastAPI × Celery/Redis](https://blog.greeden.me/en/2026/01/27/the-complete-guide-to-background-processing-with-fastapi-x-celery-redishow-to-separate-heavy-work-from-your-api-to-keep-services-stable/) - IT & Life Hacks Blog (2026)
- [Modern FastAPI Architecture Patterns for Scalable Production Systems](https://medium.com/algomart/modern-fastapi-architecture-patterns-for-scalable-production-systems-41a87b165a8b) - Medium
- [Async Architecture with FastAPI, Celery, and RabbitMQ](https://medium.com/cuddle-ai/async-architecture-with-fastapi-celery-and-rabbitmq-c7d029030377) - Medium

### Video Processing Pipelines
- [Rebuilding Netflix Video Processing Pipeline with Microservices](https://netflixtechblog.com/rebuilding-netflix-video-processing-pipeline-with-microservices-4e5e6310e359) - Netflix TechBlog
- [Automated Video Processing with FFmpeg and Docker](https://img.ly/blog/building-a-production-ready-batch-video-processing-server-with-ffmpeg/) - IMG.LY Blog
- [Pipeline video generation: How to generate video content and subtitles](https://fastercapital.com/content/Pipeline-video-generation--How-to-generate-video-content-and-subtitles-using-your-pipeline.html) - FasterCapital
- [Implementing a Dynamic Live Video Watermarking Pipeline](https://medium.com/trackit/implementing-a-dynamic-live-video-watermarking-pipeline-953bd9693087) - TrackIt

### Orchestration Patterns
- [How to Create Orchestration Pattern in Microservices](https://oneuptime.com/blog/post/2026-01-30-microservices-orchestration-pattern/view) - OneUptime (2026)
- [Saga Pattern Demystified: Orchestration vs Choreography](https://blog.bytebytego.com/p/saga-pattern-demystified-orchestration) - ByteByteGo
- [Event-driven Solution - Saga Orchestration](https://ibm-cloud-architecture.github.io/eda-saga-orchestration/) - IBM Cloud Architecture

### Database Patterns
- [Database Per Service Pattern for Microservices](https://www.geeksforgeeks.org/database-per-service-pattern-for-microservices/) - GeeksForGeeks
- [PostgreSQL in the Microservices Architecture](https://reintech.io/blog/postgresql-microservices-architecture) - Reintech
- [Redis in Microservices Architecture: Patterns and Anti-Patterns](https://reintech.io/blog/redis-microservices-patterns-antipatterns) - Reintech
- [How Redis Simplifies Microservices Design Patterns](https://thenewstack.io/how-redis-simplifies-microservices-design-patterns/) - The New Stack

### Cloud Run & Docker
- [Deploy services using Compose | Cloud Run](https://docs.cloud.google.com/run/docs/deploy-run-compose) - Google Cloud Docs
- [Cloud Run and Docker collaboration](https://cloud.google.com/blog/products/serverless/cloud-run-and-docker-collaboration) - Google Cloud Blog
- [FastAPI Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/) - FastAPI Official Docs

---
*Architecture research for: ViralForge - AI-Powered Short Video Generation Pipeline*
*Researched: 2026-02-13*
