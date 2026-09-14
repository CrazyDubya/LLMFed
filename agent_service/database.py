import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Use aiosqlite for async sqlite
DEFAULT_URL = "sqlite+aiosqlite:///./llmfed.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_URL)

# Fallback conversion for sqlite URLs missing +aiosqlite
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
# Fallback conversion for postgres URLs missing +asyncpg
if DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    # connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Sync engine/session, for the handful of call sites that predate the async
# migration and can't easily be made async (a lazy CLI helper, a one-off
# demo script, and API-key auth's lookup inside a sync FastAPI dependency
# branch). Same underlying database, plain sync drivers (pysqlite —
# stdlib, always available — or psycopg2, already a requirement).
SYNC_DATABASE_URL = (
    DATABASE_URL
    .replace("sqlite+aiosqlite:///", "sqlite:///")
    .replace("postgresql+asyncpg://", "postgresql://")
)
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)
SessionLocal = sessionmaker(bind=sync_engine, autoflush=False)

Base = declarative_base()


async def get_db():
    """Async dependency to yield a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize the database tables asynchronously."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully.")


def init_db_sync():
    """Initialize the database tables synchronously (CLI/script use)."""
    Base.metadata.create_all(bind=sync_engine)
    logger.info("Database initialized successfully (sync).")
