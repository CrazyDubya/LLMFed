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

Base = declarative_base()

# Sync engine for call sites that still use the classic Session API
# (db.query / db.commit without await). Async get_db() stays for routes
# that already await AsyncSession. FastAPI runs this sync dependency in a
# worker thread while async endpoints use the session on the event loop, so
# sqlite must not enforce same-thread checks.
SYNC_DATABASE_URL = (
    DATABASE_URL
    .replace("sqlite+aiosqlite:///", "sqlite:///")
    .replace("postgresql+asyncpg://", "postgresql://")
)
_sync_connect_args = {"check_same_thread": False} if SYNC_DATABASE_URL.startswith("sqlite") else {}
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    connect_args=_sync_connect_args,
)
SessionLocal = sessionmaker(bind=sync_engine, autoflush=False)


async def get_db():
    """Async dependency to yield a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db_sync():
    """Sync dependency for routes that still use Session.query/commit.

    Wrestling-game routes pass this session into sync game_service helpers.
    Do not use it for routes that await AsyncSession.execute/commit.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _model_base():
    # Models register on models.db_models.Base, not the unused Base above.
    import models  # noqa: F401
    from models.db_models import Base as ModelBase
    return ModelBase


async def init_db():
    """Initialize the database tables asynchronously."""
    model_base = _model_base()
    async with engine.begin() as conn:
        await conn.run_sync(model_base.metadata.create_all)
        logger.info("Database initialized successfully.")


def init_db_sync():
    """Initialize the database tables synchronously (CLI/script use)."""
    model_base = _model_base()
    model_base.metadata.create_all(bind=sync_engine)
    logger.info("Database initialized successfully (sync).")
