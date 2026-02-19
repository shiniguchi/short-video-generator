from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import time
from collections import defaultdict

from app.api import routes
from app.config import get_settings

settings = get_settings()


# --- Simple in-process rate limiter (no extra dependency) ---

class _RateLimiter:
    """Token-bucket rate limiter keyed by client IP."""

    def __init__(self, requests_per_minute: int = 30):
        self.rpm = requests_per_minute
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        window = self._buckets[key]
        # Evict entries older than 60 s
        self._buckets[key] = window = [t for t in window if now - t < 60]
        if len(window) >= self.rpm:
            return False
        window.append(now)
        return True


_limiter = _RateLimiter(requests_per_minute=60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting ViralForge API...")
    yield
    # Shutdown
    print("Shutting down ViralForge API...")


app = FastAPI(
    title="ViralForge API",
    description="Short-form video generation pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — configurable origins; default "*" for dev, tighten via env var in production
_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if not _limiter.is_allowed(client_ip):
        return Response(content="Rate limit exceeded", status_code=429)

    return await call_next(request)


app.include_router(routes.router)
