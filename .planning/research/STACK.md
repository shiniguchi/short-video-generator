# Technology Stack

**Project:** ViralForge - AI-Powered Short-Form Video Generation Pipeline
**Researched:** 2026-02-13
**Confidence:** HIGH

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | 3.11+ | Runtime environment | Industry standard for ML/AI pipelines. Python 3.11 offers 10-60% performance improvements over 3.10. Most AI libraries require 3.9+ minimum. |
| **FastAPI** | 0.129.0+ | API framework & orchestration | Async-first design, automatic OpenAPI docs, Pydantic integration, exceptional performance. Requires Python 3.10+. Industry standard for ML APIs in 2026. |
| **Celery** | 5.6.2+ | Async task queue | Battle-tested distributed task queue. Handles long-running video generation jobs. Supports retries, rate limiting, task prioritization. Requires Python 3.9+. |
| **Docker Compose** | v2 (latest) | Container orchestration | Go-based v2 is production-ready for single-server deployments. Manages 6 microservices + PostgreSQL + Redis with one command. v1 reached EOL July 2023. |

### Database & Cache

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **PostgreSQL** | 15+ | Primary database | ACID compliance for critical video metadata and workflow state. JSON support for flexible schema. Best async driver support via asyncpg. |
| **Redis** | 7.2+ | Message broker & cache | Dual role: Celery message broker + result backend. In-memory speed for task queue. Supports pub/sub for real-time updates. |
| **SQLAlchemy** | 2.0.46+ | ORM | Async support via `create_async_engine`. Type-safe queries. Migration support via Alembic. PostgreSQL dialect optimized for asyncpg driver. |
| **asyncpg** | 0.30+ | PostgreSQL driver | 5x faster than psycopg3. Native async/await. Binary protocol for PostgreSQL. Required for SQLAlchemy async. Supports PostgreSQL 9.5-18. |
| **redis-py** | 7.1.0+ (Feb 2026) | Redis client | Official Redis client. Native async support via `redis.asyncio`. Supports Redis 7.2-8.2. |

### AI & Video Generation

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **diffusers** | 0.36.0+ | Stable Video Diffusion | Hugging Face library for running SVD locally. Pre-built pipelines, interchangeable schedulers, battle-tested. Apache 2.0 license. Requires Python 3.8+. |
| **huggingface-hub** | 1.4.1+ | Model download & management | Official client for downloading SVD models. Caching, resume support, authentication. Requires Python 3.9+. |
| **OpenAI SDK** | 2.20.0+ | Sora API integration | Official Python SDK for Sora 2 video generation (paid tier). Async support. Supports sora-2 (fast) and sora-2-pro (quality). |
| **google-genai** | Latest | Veo 3.1 API integration | Official Python SDK for Google Veo video generation (paid tier). 8-second 720p/1080p/4k output with native audio. |
| **torch** | 2.x + CUDA | GPU acceleration | Required for local Stable Video Diffusion. CUDA support for NVIDIA GPUs. CPU fallback available but 10-50x slower. |

### LLM Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **langchain** | 0.3+ | LLM orchestration | Industry standard for LLM pipelines. Unified interface for OpenAI, Anthropic, local models. Prompt templates, chain composition, output parsing. |
| **langchain-openai** | Latest | OpenAI integration | Official LangChain package for GPT-4. Streaming support. Function calling for structured outputs. |
| **langchain-anthropic** | Latest | Claude integration | Official LangChain package for Claude Opus/Sonnet. Extended context for long-form analysis. |
| **anthropic** | 0.79.0+ | Claude SDK (direct) | Alternative to LangChain for Claude-only workflows. Requires Python 3.9+. Lower latency than LangChain wrapper. |

### Text-to-Speech

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **elevenlabs** | Latest | Premium TTS (paid) | Studio-quality voices (32 languages, 100+ accents). Flash v2.5 model: 75ms latency. Turbo v2.5: 250-300ms, production quality. Official Python SDK. |
| **Coqui TTS** | 0.22+ | Open-source TTS (free) | XTTS model supports 13 languages. Runs locally, no API costs. Quality lower than ElevenLabs but sufficient for MVP. Apache 2.0 license. |
| **pyttsx3** | 2.90+ | Fallback offline TTS | Pure offline TTS, no dependencies. Useful for testing without API calls. Lower quality, limited voices. |

### Video Processing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **ffmpeg-python** | 0.2.0+ | FFmpeg wrapper | Pythonic FFmpeg interface. Supports complex filter graphs. Industry standard, well-maintained. Better than moviepy for production pipelines. |
| **moviepy** | 2.0+ | High-level video editing | Compositing, text overlays, transitions. Built on FFmpeg. v2.0 (2025) introduced breaking changes but better async support. Python 3.9+. |
| **Pillow (PIL)** | 10.x+ | Image processing | Thumbnail generation, image preprocessing for video generation. Lightweight, fast. Required by many video libraries. |

### Data & Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **gspread** | 6.1.4+ | Google Sheets API | Official Python API for Sheets. OAuth2/service account auth. Batch updates, read/write ranges. Released May 2025. Requires Python 3.8+. |
| **pydantic** | 2.12.5+ | Data validation | FastAPI's core validator. v2 is 5-50x faster (Rust core). Type-safe schemas, automatic JSON serialization. Field validators, computed fields. |
| **python-dotenv** | 1.0+ | Environment variables | Load .env files into os.environ. Essential for API keys, secrets. Never commit .env to git (use .env.example template). |

### Social Media Scraping

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **httpx** | 0.27+ | HTTP client | Async HTTP client. Better than requests for async workflows. HTTP/2 support. Used by many modern scraping tools. |
| **BeautifulSoup4** | 4.12+ | HTML parsing | Industry standard for web scraping. Parser-agnostic. Simple API for navigating DOM. |
| **Playwright** | 1.47+ | Browser automation | Headless browser for JavaScript-heavy sites (TikTok, Instagram). Stealth mode, anti-detection features. More reliable than Selenium for 2026 social platforms. |

**WARNING:** Social media scraping in 2026 is legally and technically complex. TikTok/Instagram employ advanced anti-bot measures (TLS fingerprinting, behavioral analysis, IP quality detection). Official APIs are expensive or unavailable. Consider third-party APIs like Bright Data, ScrapeCreators, or EnsembleData for legal/reliable access.

### Development Tools

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Poetry** | 1.8+ | Dependency management | Modern Python packaging. Lock file for deterministic builds. Dependency groups (dev/test/prod). Replaces requirements.txt/setup.py. Python 3.9+. Released Feb 2026. |
| **Flower** | 2.0+ | Celery monitoring | Real-time web dashboard for Celery workers/tasks. Port 5555. Task history, worker stats, remote control. Essential for debugging async pipelines. |
| **pytest** | 8.x+ | Testing framework | Industry standard. Async test support via pytest-asyncio. Fixtures, parametrization, coverage reports. |
| **black** | 24.x+ | Code formatter | Opinionated, zero-config. Industry standard. Integrates with pre-commit hooks. |
| **ruff** | 0.8+ | Linter | 10-100x faster than flake8/pylint. Rust-based. Auto-fix support. Replaces flake8, isort, pydocstyle. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Web Framework** | FastAPI | Flask | Flask lacks native async, Pydantic integration, automatic OpenAPI docs. FastAPI is faster and type-safe. |
| **Web Framework** | FastAPI | Django | Too heavy for API-only service. ORM lock-in. Slower async support. Better for full-stack web apps. |
| **Task Queue** | Celery | RQ (Redis Queue) | RQ simpler but lacks advanced features: rate limiting, task routing, complex workflows. Celery is battle-tested at scale. |
| **ORM** | SQLAlchemy 2.0 | Django ORM | Requires Django framework. SQLAlchemy is framework-agnostic, better async support. |
| **ORM** | SQLAlchemy 2.0 | Raw SQL | Loss of type safety, migrations, cross-DB compatibility. Raw SQL acceptable for simple queries but not entire app. |
| **FFmpeg Wrapper** | ffmpeg-python | moviepy | moviepy has higher-level API but slower, more memory-intensive. ffmpeg-python better for production pipelines. Use both: moviepy for compositing, ffmpeg-python for encoding. |
| **Container Orchestration** | Docker Compose | Kubernetes | K8s overkill for single-server deployment. Docker Compose simpler, faster iteration. Migrate to K8s only if scaling beyond one server. |
| **Dependency Management** | Poetry | pip + requirements.txt | No lock file (requirements.txt non-deterministic). Poetry provides better dependency resolution, dev/prod separation. |
| **TTS** | ElevenLabs (paid) | Google Cloud TTS | ElevenLabs has more natural voices, lower latency (Flash v2.5: 75ms). Google TTS acceptable fallback. |
| **TTS** | Coqui TTS (free) | gTTS (Google) | gTTS requires internet, rate limits. Coqui runs locally, better for high-volume generation. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Docker Compose v1** | Reached EOL July 2023. Python-based (slow). Use v2 (Go-based, `docker compose` with space). | Docker Compose v2 |
| **Python < 3.9** | Most modern libraries require 3.9+. Missing type hint improvements, performance optimizations. | Python 3.11+ |
| **requests library** | Synchronous only. Use httpx for async workflows. requests still fine for sync-only scripts. | httpx (async) |
| **Selenium** | Slower, easier to detect. Playwright has better stealth mode, faster execution, simpler API. | Playwright |
| **aioredis** | Merged into redis-py. Use `redis.asyncio` from official redis-py client. | redis-py (async mode) |
| **asyncio-redis** | Not actively maintained. Superseded by redis-py async support. | redis-py (async mode) |
| **Pydantic v1** | v2 is 5-50x faster (Rust core). Breaking changes but migration guide available. | Pydantic v2 (2.12+) |
| **SQLAlchemy 1.x** | 2.0 has better async support, type hints, query API. 1.4 is transitional bridge. | SQLAlchemy 2.0+ |
| **moviepy v1** | No longer maintained. v2 (2025) has breaking changes but required for Python 3.11+ support. | moviepy 2.0+ |

## Installation

### Core Dependencies (pyproject.toml - Poetry)

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.129.0"
uvicorn = {extras = ["standard"], version = "^0.33.0"}
celery = "^5.6.2"
redis = "^7.1.0"
sqlalchemy = "^2.0.46"
asyncpg = "^0.30.0"
pydantic = "^2.12.5"
pydantic-settings = "^2.7.0"
python-dotenv = "^1.0.0"

# AI & Video Generation
diffusers = "^0.36.0"
huggingface-hub = "^1.4.1"
torch = "^2.0.0"
openai = "^2.20.0"
google-genai = "^0.8.0"

# LLM Integration
langchain = "^0.3.0"
langchain-openai = "^0.2.0"
langchain-anthropic = "^0.3.0"

# TTS
elevenlabs = "^1.0.0"
TTS = "^0.22.0"  # Coqui TTS

# Video Processing
ffmpeg-python = "^0.2.0"
moviepy = "^2.0.0"
Pillow = "^10.0.0"

# Data & Integration
gspread = "^6.1.4"
httpx = "^0.27.0"
beautifulsoup4 = "^4.12.0"
playwright = "^1.47.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^6.0.0"
black = "^24.0.0"
ruff = "^0.8.0"
flower = "^2.0.0"
```

### Install with Poetry

```bash
# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Install with dev dependencies
poetry install --with dev

# Activate virtual environment
poetry shell
```

### Install with pip (alternative)

```bash
# Core
pip install fastapi uvicorn[standard] celery redis sqlalchemy asyncpg pydantic pydantic-settings python-dotenv

# AI & Video
pip install diffusers huggingface-hub torch openai google-genai

# LLM
pip install langchain langchain-openai langchain-anthropic

# TTS
pip install elevenlabs TTS

# Video Processing
pip install ffmpeg-python moviepy Pillow

# Data & Integration
pip install gspread httpx beautifulsoup4 playwright

# Dev tools
pip install pytest pytest-asyncio pytest-cov black ruff flower

# Install Playwright browsers
playwright install chromium
```

### System Dependencies

```bash
# FFmpeg (required for video processing)
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install ffmpeg

# CUDA for GPU acceleration (optional, for local SVD)
# See: https://pytorch.org/get-started/locally/
# Example for CUDA 11.8:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Docker Compose Configuration

### Sample docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: viralforge
      POSTGRES_USER: viralforge
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://viralforge:${DB_PASSWORD}@postgres:5432/viralforge
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  worker-trend:
    build: .
    command: celery -A app.celery_app worker -Q trend-collection -n worker-trend@%h --loglevel=info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://viralforge:${DB_PASSWORD}@postgres:5432/viralforge
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  worker-video:
    build: .
    command: celery -A app.celery_app worker -Q video-generation -n worker-video@%h --loglevel=info --concurrency=1
    volumes:
      - .:/app
      - model_cache:/root/.cache/huggingface
    environment:
      - DATABASE_URL=postgresql+asyncpg://viralforge:${DB_PASSWORD}@postgres:5432/viralforge
      - REDIS_URL=redis://redis:6379/0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  worker-composition:
    build: .
    command: celery -A app.celery_app worker -Q video-composition -n worker-composition@%h --loglevel=info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://viralforge:${DB_PASSWORD}@postgres:5432/viralforge
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  flower:
    build: .
    command: celery -A app.celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  model_cache:
```

## Stack Patterns by Variant

### If running SVD locally (free, GPU required):
- Use `diffusers` + `torch` with CUDA
- Allocate dedicated GPU worker (concurrency=1)
- Cache models in Docker volume (`model_cache`)
- Expect 20-60 seconds per 14-frame video (GPU dependent)
- **Hardware:** NVIDIA GPU with 8GB+ VRAM (RTX 3060 minimum)

### If using Sora/Veo only (paid, no GPU):
- Skip `diffusers` + `torch` installation
- Use `openai` SDK for Sora or `google-genai` for Veo
- No GPU worker needed, use CPU-only containers
- Expect 30-120 seconds per video (API dependent)
- **Cost:** $0.10-0.50 per video (varies by model/length)

### If using ElevenLabs TTS (paid):
- Use `elevenlabs` SDK
- Flash v2.5 model for low latency (75ms)
- Turbo v2.5 for production quality (250-300ms)
- **Cost:** ~$0.30 per 1000 characters

### If using Coqui TTS (free):
- Use `TTS` package with XTTS model
- CPU or GPU inference (GPU 5-10x faster)
- Download models on first run (~1.5GB)
- **Quality:** Lower than ElevenLabs but acceptable for MVP

## Version Compatibility Matrix

| Package | Minimum Python | Notes |
|---------|----------------|-------|
| FastAPI 0.129+ | 3.10 | Official requirement |
| Celery 5.6+ | 3.9 | Tested through 3.13 |
| Pydantic 2.12+ | 3.8 | Recommend 3.10+ for full features |
| SQLAlchemy 2.0+ | 3.8 | Async requires 3.9+ |
| diffusers 0.36+ | 3.8 | Recommend 3.9+ |
| huggingface-hub 1.4+ | 3.9 | Official requirement |
| gspread 6.1+ | 3.8 | Latest features require 3.9+ |

**Recommended baseline: Python 3.11** for best compatibility, performance, and long-term support.

## GPU Requirements for Local Video Generation

| Model | VRAM | GPU Examples | Speed (14 frames) |
|-------|------|--------------|-------------------|
| Stable Video Diffusion | 8GB+ | RTX 3060, RTX 4060, A4000 | 20-40s |
| Stable Video Diffusion | 16GB+ | RTX 4080, RTX 4090, A5000 | 15-30s |
| Stable Video Diffusion XT | 12GB+ | RTX 3090, RTX 4070 Ti | 25-45s |

**No GPU?** Use Sora/Veo APIs exclusively. Skip torch/diffusers installation.

## Sources

### Official Documentation (HIGH Confidence)
- [FastAPI Official Docs](https://fastapi.tiangolo.com/) - PyPI version: 0.129.0
- [Celery Documentation](https://docs.celeryq.dev/en/stable/) - PyPI version: 5.6.2
- [Pydantic Validation](https://docs.pydantic.dev/latest/) - PyPI version: 2.12.5
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/) - PyPI version: 2.0.46
- [Diffusers Documentation](https://huggingface.co/docs/diffusers) - PyPI version: 0.36.0
- [Hugging Face Hub Client](https://huggingface.co/docs/huggingface_hub) - PyPI version: 1.4.1
- [OpenAI Python SDK](https://github.com/openai/openai-python) - PyPI version: 2.20.0
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) - PyPI version: 0.79.0
- [LangChain Documentation](https://docs.langchain.com/) - Ecosystem overview
- [gspread Documentation](https://docs.gspread.org/) - PyPI version: 6.1.4
- [redis-py Documentation](https://redis-py.readthedocs.io/) - PyPI version: 7.1.0
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/) - PostgreSQL driver
- [Poetry Documentation](https://python-poetry.org/docs/) - Latest: Feb 1, 2026
- [Flower Documentation](https://flower.readthedocs.io/) - Celery monitoring

### Video Generation Research (MEDIUM Confidence)
- [Build your own GenAI video generation pipeline](https://medium.com/@thierryjmoreau/build-your-own-genai-video-generation-pipeline-cdc1515d1db9)
- [Best AI Video Models 2026](https://flux-ai.io/blog/detail/Best-AI-Video-Models-2026-The-Ultimate-Guide-to-Image-to-Video-Generation-c776feaf6b2e/)
- [Stable Video Diffusion on Hugging Face](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid)
- [Veo on Vertex AI Documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [OpenAI Sora 2 Documentation](https://platform.openai.com/docs/guides/video-generation)

### Python Ecosystem Best Practices (MEDIUM Confidence)
- [Docker Compose Best Practices 2026](https://dasroot.net/posts/2026/01/docker-compose-best-practices-local-development/)
- [Building High-Performance Async APIs with FastAPI](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)
- [Social Media Scraping in 2026](https://scrapfly.io/blog/posts/social-media-scraping)
- [How to Use FFmpeg with Python in 2026](https://www.gumlet.com/learn/ffmpeg-python/)

### TTS & Audio (MEDIUM Confidence)
- [ElevenLabs Text-to-Speech API](https://elevenlabs.io/text-to-speech-api)
- [Top Python TTS Libraries](https://smallest.ai/blog/python-packages-realistic-text-to-speech)
- [Coqui TTS GitHub](https://github.com/coqui-ai/TTS)

---

*Technology Stack Research for ViralForge*
*Researched: 2026-02-13*
*Confidence: HIGH (verified via official PyPI, docs, and ecosystem sources)*
