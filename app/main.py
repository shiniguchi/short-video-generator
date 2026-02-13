from fastapi import FastAPI
from app.config import get_settings

app = FastAPI(title="ViralForge API")

settings = get_settings()


@app.get("/")
async def root():
    return {"status": "ok", "service": "viralforge-api"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": "configured",
        "redis": "configured"
    }
