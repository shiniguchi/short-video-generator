from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import routes
from app.config import get_settings

settings = get_settings()


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

app.include_router(routes.router)
