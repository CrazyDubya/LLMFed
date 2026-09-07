"""Database engines and session factories for LLMFed.

The API uses SQLAlchemy's async session while legacy engine, CLI, and security
paths still use a synchronous session. Both factories point at the same
configured database and share the canonical model metadata.
"""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base

logger = logging.getLogger(__name__)

DEFAULT_URL = "sqlite+aiosqlite:///./llmfed.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_URL)


def _async_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _sync_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite:///"):
        return url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


ASYNC_DATABASE_URL = _async_url(DATABASE_URL)
SYNC_DATABASE_URL = _sync_url(DATABASE_URL)

# Keep `engine` as the async engine for existing API imports.
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Compatibility factory for the synchronous engine/CLI/security paths.
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    connect_args={"check_same_thread": False} if SYNC_DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


def init_db() -> None:
    """Create all registered tables using the synchronous compatibility engine."""
    # Import the barrel module so every model class is registered on Base.metadata.
    import models  # noqa: F401

    Base.metadata.create_all(bind=sync_engine)
    logger.info("Database initialized successfully")


async def init_db_async() -> None:
    """Async variant for callers that are already inside an event loop."""
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully (async)")
