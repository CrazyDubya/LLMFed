"""Database engine, session factory, and initialization for LLMFed.

init_db() is NOT called at import time (Rule 3, Rule 8). Callers
must invoke it explicitly during application startup.
"""
import logging
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models.db_models import Base

logger = logging.getLogger(__name__)

# Build engine kwargs based on the database backend.
_engine_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_args["connect_args"] = {"check_same_thread": False}
else:
    # Production pool tuning for PostgreSQL / MySQL
    _engine_args["pool_size"] = int(os.getenv("DB_POOL_SIZE", "20"))
    _engine_args["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    _engine_args["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    _engine_args["pool_pre_ping"] = True  # detect stale connections

engine = create_engine(DATABASE_URL, **_engine_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_MAX_INIT_RETRIES = 3


def init_db() -> None:
    """Initialize database tables with retry logic.

    Retries up to _MAX_INIT_RETRIES times with 1-second backoff (Rule 7).
    """
    for attempt in range(_MAX_INIT_RETRIES):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info(f"Database tables verified: {list(Base.metadata.tables.keys())}")
            return
        except Exception as e:
            logger.warning(f"init_db attempt {attempt + 1}/{_MAX_INIT_RETRIES} failed: {e}")
            if attempt == _MAX_INIT_RETRIES - 1:
                raise
            time.sleep(1)
