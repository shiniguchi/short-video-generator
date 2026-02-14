from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool
from typing import AsyncGenerator
from app.config import get_settings

settings = get_settings()


def _build_engine_kwargs():
    """Build engine kwargs based on database type."""
    kwargs = {
        "echo": True,
        "future": True,
    }
    if settings.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
    return kwargs


engine = create_async_engine(settings.database_url, **_build_engine_kwargs())

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # CRITICAL: Prevents implicit queries after commit
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def get_task_session_factory():
    """Create a fresh async session factory for Celery task contexts.

    Celery workers (especially with prefork pool) run asyncio.run() which
    creates a new event loop. The module-level engine's connection pool is
    bound to the import-time event loop, causing 'attached to a different
    loop' errors with asyncpg. This function creates a fresh engine with
    NullPool (no connection reuse) to avoid the conflict.
    """
    task_engine = create_async_engine(
        settings.database_url,
        echo=True,
        future=True,
        poolclass=pool.NullPool,  # No pool = no stale loop references
    )
    return sessionmaker(
        task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
