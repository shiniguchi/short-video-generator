from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from app.config import get_settings

settings = get_settings()

# SQLite doesn't support pool_size or pool_pre_ping the same way
engine_kwargs = {
    "echo": True,
    "future": True,
}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 5

engine = create_async_engine(settings.database_url, **engine_kwargs)

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # CRITICAL: Prevents implicit queries after commit
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
