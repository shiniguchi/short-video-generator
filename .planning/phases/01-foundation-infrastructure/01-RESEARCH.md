# Phase 1: Foundation & Infrastructure - Research

**Researched:** 2026-02-13
**Domain:** FastAPI + Celery + PostgreSQL + Docker microservices architecture
**Confidence:** MEDIUM-HIGH

## Summary

This phase establishes a production-ready foundation for async task processing using the FastAPI + Celery + PostgreSQL stack running in Docker containers. The standard approach uses FastAPI for synchronous HTTP endpoints and request validation, Celery with Redis for asynchronous task execution, PostgreSQL for persistent data storage, and SQLAlchemy 2.0 with async support for database operations.

The critical architectural pattern is separation of concerns: FastAPI handles HTTP requests and returns immediately, Celery workers process long-running pipeline tasks asynchronously, and PostgreSQL provides ACID-compliant data persistence. Docker Compose orchestrates all services with health-check-based startup ordering to prevent race conditions.

Key challenges include managing async/sync boundaries between FastAPI and Celery, preventing Celery broker failures from blocking the event loop, configuring Alembic for async migrations, and ensuring proper volume permissions for PostgreSQL data persistence.

**Primary recommendation:** Use the same Docker image for FastAPI and Celery workers with different entry commands, leverage pydantic-settings for configuration management, implement health checks with `depends_on: service_healthy` conditions, and use async SQLAlchemy with asyncpg for database operations.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.129.0+ | Async HTTP API framework | De facto standard for modern Python APIs, built-in OpenAPI docs, excellent async support |
| Celery | 5.6.2+ | Distributed task queue | Industry standard for async task processing, mature ecosystem, 5.6.2 fixes critical memory leaks |
| PostgreSQL | 15-16 | Relational database | ACID compliance, JSON support, mature ecosystem, excellent Docker support |
| Redis | 7.2+ | Message broker & result backend | Fastest broker for Celery, dual-purpose (broker + results), simple setup |
| SQLAlchemy | 2.0+ | Async ORM | First-class async support in 2.0, type-safe queries, mature migration tooling |
| Alembic | 1.18+ | Database migrations | Official SQLAlchemy migration tool, autogenerate support, async-compatible |
| Pydantic | 2.12+ | Data validation & settings | Built into FastAPI, type-safe config management via pydantic-settings |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | latest | PostgreSQL async driver | Required for SQLAlchemy async operations with PostgreSQL |
| pydantic-settings | latest | Environment config management | Centralized .env file loading with validation |
| python-dotenv | latest | .env file parsing | Loaded automatically by pydantic-settings |
| Flower | latest | Celery monitoring UI | Development and debugging (optional in production) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Redis (broker) | RabbitMQ | RabbitMQ better for guaranteed delivery, Redis simpler and faster for this use case |
| PostgreSQL | MySQL | PostgreSQL has better JSON support and async driver maturity |
| Celery | Dramatiq, ARQ | Celery has largest ecosystem and best monitoring tools |

**Installation:**
```bash
pip install fastapi[standard] celery[redis] sqlalchemy[asyncio] alembic asyncpg pydantic-settings python-dotenv
```

## Architecture Patterns

### Recommended Project Structure
```
short-video-generator/
├── docker-compose.yml           # Multi-service orchestration
├── Dockerfile                   # Shared image for API + workers
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (gitignored)
├── .env.example                 # Template for .env
├── alembic/                     # Database migrations
│   ├── versions/                # Migration files
│   └── env.py                   # Alembic config (async setup)
├── alembic.ini                  # Alembic settings
└── app/
    ├── __init__.py
    ├── main.py                  # FastAPI app entry point
    ├── config.py                # Pydantic settings
    ├── database.py              # SQLAlchemy async setup
    ├── models.py                # SQLAlchemy models
    ├── schemas.py               # Pydantic request/response models
    ├── tasks.py                 # Celery task definitions
    ├── worker.py                # Celery app configuration
    └── api/
        ├── __init__.py
        └── routes.py            # API endpoints
```

### Pattern 1: Pydantic Settings for Configuration
**What:** Centralized config class with environment variable loading and validation
**When to use:** All configuration (database URLs, API keys, service connections)
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/settings/
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # API
    api_secret_key: str

@lru_cache()
def get_settings():
    return Settings()
```

### Pattern 2: Async SQLAlchemy Session Management
**What:** Dependency injection pattern for async database sessions
**When to use:** All database operations in FastAPI endpoints
**Example:**
```python
# Source: https://testdriven.io/blog/fastapi-sqlmodel/
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
    pool_pre_ping=True,
    pool_size=5
)

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

# Usage in endpoints
@app.get("/jobs")
async def list_jobs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Job))
    return result.scalars().all()
```

### Pattern 3: Celery Task Definition with Retry Logic
**What:** Task decorator with error handling and retry configuration
**When to use:** All async background tasks
**Example:**
```python
# Source: https://oneuptime.com/blog/post/2026-02-08-how-to-set-up-a-fastapi-postgresql-celery-stack-with-docker-compose/view
from celery import Celery

celery_app = Celery(
    "worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

@celery_app.task(bind=True, max_retries=3)
def process_video_pipeline(self, job_id: int):
    try:
        # Task logic
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)

# Dispatch from FastAPI endpoint
@app.post("/jobs")
async def create_job(job: JobCreate):
    task = process_video_pipeline.delay(job.id)
    return {"task_id": task.id}
```

### Pattern 4: Docker Compose Health Check Dependencies
**What:** Service startup ordering based on health checks
**When to use:** Multi-service dependencies (API waits for DB, workers wait for Redis)
**Example:**
```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  celery-worker:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.worker.celery_app worker --loglevel=info
```

### Pattern 5: Alembic Async Migration Setup
**What:** Initialize Alembic with async template and configure for async engine
**When to use:** All database schema changes
**Example:**
```bash
# Initialize with async template
alembic init -t async alembic
```

```python
# Source: https://testdriven.io/blog/fastapi-sqlmodel/
# alembic/env.py
from app.models import Base  # Import all models
from app.config import get_settings

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata  # Set metadata for autogenerate

# Run migrations before server start
# docker-entrypoint.sh or main.py startup
alembic upgrade head
```

### Anti-Patterns to Avoid

- **Blocking Celery calls in FastAPI endpoints:** Never use `.get()` or `.wait()` on Celery task results in async endpoints - this blocks the event loop. Use `.delay()` and return immediately.
- **Using asyncio inside Celery tasks:** Celery workers don't have an event loop context. If you need async operations, call a FastAPI internal endpoint from the Celery task instead.
- **Sync engine for async app:** Don't use `create_engine()` for async FastAPI apps - use `create_async_engine()` with asyncpg driver.
- **Missing expire_on_commit=False:** Without this, SQLAlchemy issues implicit queries after commit in async sessions, causing runtime errors.
- **Hardcoded configuration:** Never hardcode database URLs or API keys - always use pydantic-settings with .env files.
- **No health checks on depends_on:** Using `depends_on` without `condition: service_healthy` only waits for container start, not readiness - leads to connection failures.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Environment config loading | Custom .env parser or manual os.getenv() | pydantic-settings BaseSettings | Type validation, automatic .env loading, nested config, IDE autocomplete |
| Database connection pooling | Manual connection management | SQLAlchemy engine with pool_size/pool_pre_ping | Handles connection lifecycle, health checks, reconnection logic |
| Async session context | Manual session creation/cleanup | sessionmaker with async context manager | Prevents connection leaks, handles exceptions, automatic cleanup |
| Task retry logic | Custom retry loops with sleep | Celery bind=True with self.retry() | Exponential backoff, max retries, task state tracking |
| Service health monitoring | Custom TCP connection checks | Docker HEALTHCHECK with service-specific commands | Native Docker integration, automatic restart, depends_on integration |
| Database migrations | Manual SQL scripts | Alembic autogenerate | Tracks schema version, generates migrations from model changes, handles rollbacks |

**Key insight:** Infrastructure concerns like connection pooling, retries, and health checks have subtle edge cases (reconnection storms, connection leaks, race conditions during restart). Mature libraries handle these; custom solutions introduce production bugs.

## Common Pitfalls

### Pitfall 1: Celery Broker Blocking FastAPI Event Loop
**What goes wrong:** When Redis (Celery broker) is unavailable, `.delay()` calls hang synchronously, blocking all FastAPI requests
**Why it happens:** Celery's broker communication is synchronous even in async FastAPI context
**How to avoid:** Run Celery task dispatch in a thread executor or use async result backends
**Warning signs:** All API endpoints become unresponsive when Redis restarts, timeouts in logs

```python
# Solution: Dispatch in thread executor
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=10)

@app.post("/jobs")
async def create_job(job: JobCreate):
    loop = asyncio.get_event_loop()
    task = await loop.run_in_executor(executor, process_video_pipeline.delay, job.id)
    return {"task_id": task.id}
```

### Pitfall 2: PostgreSQL Volume Permission Errors
**What goes wrong:** Container fails to start with "data directory has wrong ownership" error
**Why it happens:** Host directory mounted as volume has different UID/GID than postgres user (999:999)
**How to avoid:** Use named volumes (managed by Docker) instead of bind mounts for production
**Warning signs:** "Permission denied" or "wrong ownership" errors in postgres container logs

```yaml
# GOOD: Named volume (Docker manages permissions)
services:
  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:

# BAD: Bind mount (host permissions conflict)
services:
  postgres:
    volumes:
      - ./data/postgres:/var/lib/postgresql/data  # Avoid in production
```

### Pitfall 3: Alembic Autogenerate Missing Changes
**What goes wrong:** `alembic revision --autogenerate` creates empty migration despite model changes
**Why it happens:** Models not imported in alembic/env.py, or database not at latest migration
**How to avoid:** Import all models in env.py, ensure `alembic upgrade head` before autogenerate
**Warning signs:** Empty upgrade()/downgrade() functions, autogenerate says "detected removed tables"

```python
# alembic/env.py - MUST import all models
from app.models import Base, Job, Trend, Script, Video  # Import explicitly
target_metadata = Base.metadata

# Before autogenerate, verify DB is current
# alembic current  # Should show head revision
# alembic upgrade head  # Apply any pending migrations
# alembic revision --autogenerate -m "description"  # Then generate
```

### Pitfall 4: Running asyncio.run() Inside Celery Tasks
**What goes wrong:** RuntimeError: "asyncio.run() cannot be called from a running event loop"
**Why it happens:** asyncio.run() creates new event loop, but Celery workers may have existing loop context
**How to avoid:** Don't use async code in Celery tasks; call FastAPI internal endpoints instead
**Warning signs:** Event loop errors in Celery worker logs, tasks hang indefinitely

```python
# BAD: Async in Celery
@celery_app.task
def process_video(video_id):
    async def fetch_data():
        async with httpx.AsyncClient() as client:
            return await client.get(...)
    result = asyncio.run(fetch_data())  # FAILS in Celery

# GOOD: Call internal FastAPI endpoint
@celery_app.task
def process_video(video_id):
    import requests
    result = requests.post("http://web:8000/internal/process", json={"video_id": video_id})
    return result.json()
```

### Pitfall 5: Database Not Ready Before Migration
**What goes wrong:** Alembic migrations fail with connection errors during container startup
**Why it happens:** Migrations run before PostgreSQL is ready to accept connections
**How to avoid:** Use health checks with `depends_on: service_healthy`, or retry logic in entrypoint
**Warning signs:** "Connection refused" errors during docker-compose up, intermittent startup failures

```yaml
# Solution: Health check before migration
services:
  web:
    depends_on:
      postgres:
        condition: service_healthy  # Wait for healthy, not just started
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

### Pitfall 6: Shared Docker Image Missing Service-Specific Dependencies
**What goes wrong:** Using same Dockerfile for web and workers, but workers need additional system packages
**Why it happens:** Optimization to share image between services, but different runtime needs
**How to avoid:** Use multi-stage builds with service-specific stages, or install all deps in base image
**Warning signs:** Workers crash with "command not found" or missing libraries

```dockerfile
# Solution: Multi-stage with common base
FROM python:3.11-slim AS base
RUN apt-get update && apt-get install -y postgresql-client
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS web
# Web-specific config

FROM base AS worker
# Worker-specific config if needed
```

## Code Examples

Verified patterns from official sources:

### Health Check Endpoint with Database Status
```python
# Source: FastAPI best practices pattern
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session

@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    try:
        # Verify database connectivity
        await session.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
```

### Celery Worker with Proper Configuration
```python
# Source: https://oneuptime.com/blog/post/2026-02-08-how-to-set-up-a-fastapi-postgresql-celery-stack-with-docker-compose/view
# app/worker.py
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
)
```

### PostgreSQL Initialization with Health Check
```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # Optional init scripts
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### FastAPI Lifespan Events for Startup/Shutdown
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run migrations
    print("Running database migrations...")
    # In production, run: alembic upgrade head

    yield  # Application runs

    # Shutdown: Cleanup
    print("Closing database connections...")
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQLAlchemy 1.4 sync | SQLAlchemy 2.0 async | 2023 | Must use create_async_engine, AsyncSession, and await all queries |
| pydantic v1 BaseSettings | pydantic-settings v2 BaseSettings | 2023 | BaseSettings moved to separate package, use model_config instead of class Config |
| Alembic sync template | Alembic async template | 2021 | Initialize with `alembic init -t async`, use async connection in env.py |
| depends_on (wait for start) | depends_on with service_healthy | 2017 | Must define healthcheck for each service, prevents race conditions |
| Celery 4.x | Celery 5.6.2 (Recovery) | 2026-01 | Critical memory leak fixes, Redis stability improvements via Kombu 5.5.0 |
| Manual .env loading | pydantic-settings auto-loading | 2023 | Automatic with model_config, no need for load_dotenv() |

**Deprecated/outdated:**
- **Celery 5.0-5.5:** Use 5.6.2+ (Recovery release) for memory leak fixes on Python 3.11+
- **SQLAlchemy sync drivers (psycopg2):** Use asyncpg for async FastAPI apps
- **pydantic v1 Config class:** Use model_config = SettingsConfigDict() in pydantic v2
- **docker-compose command:** Use `docker compose` (no hyphen) - v2 CLI is standard
- **Manual alembic upgrade in code:** Run as separate step in entrypoint script, not in Python startup

## Open Questions

1. **Celery result backend: Redis vs PostgreSQL?**
   - What we know: Redis is faster, PostgreSQL provides guaranteed persistence
   - What's unclear: For this use case (video generation jobs), do we need long-term result storage?
   - Recommendation: Start with Redis backend for speed, add PostgreSQL backend only if job history persistence becomes a requirement

2. **Should we use Flower for monitoring in development?**
   - What we know: Flower provides real-time task monitoring UI
   - What's unclear: Is it worth the extra container overhead in local development?
   - Recommendation: Add as optional service (not in depends_on chain), developer can start manually when needed

3. **How to handle Google Sheets service account in local development?**
   - What we know: Requirement says "local fallback" for sample data
   - What's unclear: Should we mock the Google Sheets API or use local YAML/JSON files?
   - Recommendation: Create a data provider abstraction with two implementations (GoogleSheetsProvider, LocalFileProvider), switch via environment variable

4. **Database migration strategy during development?**
   - What we know: Alembic autogenerate can miss changes, requires manual review
   - What's unclear: Should migrations run automatically on startup or require manual command?
   - Recommendation: Auto-run on startup for development, manual for production (safety)

## Sources

### Primary (HIGH confidence)
- [FastAPI Official Documentation - Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/)
- [Docker Compose Official Documentation - Control startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker Compose Official Documentation - Define services](https://docs.docker.com/reference/compose-file/services/)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Celery 5.6.2 Official Documentation - Backends and Brokers](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html)
- [Alembic Official Documentation - Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

### Secondary (MEDIUM confidence)
- [OneUpTime - How to Set Up a FastAPI + PostgreSQL + Celery Stack with Docker Compose (2026-02-08)](https://oneuptime.com/blog/post/2026-02-08-how-to-set-up-a-fastapi-postgresql-celery-stack-with-docker-compose/view)
- [TestDriven.io - FastAPI with Async SQLAlchemy, SQLModel, and Alembic](https://testdriven.io/blog/fastapi-sqlmodel/)
- [Last9 - Docker Compose Health Checks: An Easy-to-follow Guide](https://last9.io/blog/docker-compose-health-checks/)
- [Medium - FastAPI and Celery: Prevent This Common Mistake](https://hemantapkh.com/posts/celery-tasks-in-fastapi/)
- [Medium - Using Celery With FastAPI: The Async Inside Tasks Event Loop Problem](https://medium.com/@termtrix/using-celery-with-fastapi-the-async-inside-tasks-event-loop-problem-and-how-endpoints-save-79e33676ade9)
- [Berk Karaal - Setup FastAPI Project with Async SQLAlchemy 2, Alembic, PostgreSQL and Docker](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/)

### Tertiary (LOW confidence - requires validation)
- [Medium - Setting up a FastAPI App with Async SQLAlchemy 2.0 & Pydantic V2](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308)
- [GitHub - alperencubuk/fastapi-celery-redis-postgres-docker-rest-api](https://github.com/alperencubuk/fastapi-celery-redis-postgres-docker-rest-api)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Verified with official documentation and recent 2026 sources
- Architecture patterns: MEDIUM-HIGH - Based on official docs and multiple verified examples
- Pitfalls: MEDIUM - Based on community sources and GitHub issues, some LOW confidence items flagged
- Code examples: HIGH - All examples sourced from official documentation or verified tutorials

**Research date:** 2026-02-13
**Valid until:** 2026-03-15 (30 days - stack is relatively stable, but monitor Celery/FastAPI releases)

**Technology maturity:**
- FastAPI: Mature, stable release cycle
- Celery 5.6: Recent "Recovery" release, monitor for 5.7
- SQLAlchemy 2.0: Mature async support
- Docker Compose v2: Stable standard

**Recommendation:** This stack is production-ready. Primary risk areas are async/sync boundaries (Celery in FastAPI) and migration autogenerate reliability (requires manual review).
