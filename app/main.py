from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from contextlib import asynccontextmanager
from pathlib import Path
import os
import time
from collections import defaultdict

from app.database import get_session
from app.ui import router as ui_router
from app.config import get_settings
from app import ugc_router
from app.schemas import WaitlistSubmit

settings = get_settings()

# --- Auth helper ---

_security = HTTPBearer()


async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """Validate Bearer token against API_SECRET_KEY."""
    if credentials.credentials != settings.api_secret_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return credentials.credentials


# --- Rate limiter ---

class _RateLimiter:
    """Token-bucket rate limiter keyed by client IP."""

    def __init__(self, requests_per_minute: int = 30):
        self.rpm = requests_per_minute
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        window = self._buckets[key]
        self._buckets[key] = window = [t for t in window if now - t < 60]
        if len(window) >= self.rpm:
            return False
        window.append(now)
        return True


_limiter = _RateLimiter(requests_per_minute=60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting ViralForge API...")
    yield
    print("Shutting down ViralForge API...")


app = FastAPI(
    title="ViralForge API",
    description="Short-form video generation pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
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
    path = request.url.path
    if path == "/health" or path.startswith("/ui/"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if not _limiter.is_allowed(client_ip):
        return Response(content="Rate limit exceeded", status_code=429)

    return await call_next(request)


# --- API endpoints (health, waitlist, analytics) ---

@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check with DB + Redis status."""
    db_status = "disconnected"
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    redis_status = "not configured"
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            redis_status = "connected"
            await r.close()
        except Exception as e:
            redis_status = f"error: {str(e)}"

    overall = "healthy" if db_status == "connected" and redis_status in ("connected", "not configured") else "unhealthy"
    return {"status": overall, "database": db_status, "redis": redis_status, "version": "1.0.0"}


@app.post("/waitlist")
async def submit_waitlist(request: WaitlistSubmit, session: AsyncSession = Depends(get_session)):
    """Public waitlist signup from LP visitors."""
    from app.models import WaitlistEntry
    from app.schemas import WaitlistResponse
    from sqlalchemy.exc import IntegrityError

    existing = await session.execute(
        select(WaitlistEntry).where(WaitlistEntry.email == request.email)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="You're already on the waitlist!")

    entry = WaitlistEntry(email=request.email, lp_source=request.lp_source)
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="You're already on the waitlist!")

    return WaitlistResponse(message="Thanks! You're on the list.")


@app.get("/analytics/{lp_id}")
async def get_analytics(lp_id: str, _key: str = Depends(require_api_key)):
    """Get LP analytics from Cloudflare Worker."""
    from app.services.analytics.client import CloudflareAnalyticsClient
    client = CloudflareAnalyticsClient()
    return await client.get_lp_analytics(lp_id)


# --- Mount UI + static files ---

app.mount("/ui/static", StaticFiles(directory=str(Path(__file__).parent / "ui" / "static")), name="ui-static")
app.include_router(ui_router.router)

_output_dir = Path(__file__).parent.parent / "output"
_output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(_output_dir)), name="lp-output")

app.include_router(ugc_router.router)
