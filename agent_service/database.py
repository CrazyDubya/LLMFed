"""Database engine, session factory, and initialization for LLMFed.

init_db() is NOT called at import time (Rule 3, Rule 8). Callers
must invoke it explicitly during application startup.
"""
import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models.db_models import Base

logger = logging.getLogger(__name__)

# For SQLite, connect_args are needed for FastAPI compatibility
_engine_args = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_args["connect_args"] = {"check_same_thread": False}

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


def _migrate_agents_columns() -> None:
    """Add new columns to agents table if missing (win_streak, loss_streak, alignment)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM pragma_table_info('agents') WHERE name IN ('win_streak','loss_streak','alignment')")
            )
            existing = {row[0] for row in result}
            if "win_streak" not in existing:
                conn.execute(text("ALTER TABLE agents ADD COLUMN win_streak INTEGER DEFAULT 0"))
                conn.commit()
            if "loss_streak" not in existing:
                conn.execute(text("ALTER TABLE agents ADD COLUMN loss_streak INTEGER DEFAULT 0"))
                conn.commit()
            if "alignment" not in existing:
                conn.execute(text("ALTER TABLE agents ADD COLUMN alignment VARCHAR"))
                conn.commit()
    except Exception as e:
        logger.warning(f"Migration skipped (columns may already exist): {e}")


def _migrate_storylines_payoff_phase() -> None:
    """Add payoff_phase column to storylines table if missing."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM pragma_table_info('storylines') WHERE name = 'payoff_phase'")
            )
            if not result.fetchone():
                conn.execute(text("ALTER TABLE storylines ADD COLUMN payoff_phase VARCHAR"))
                conn.commit()
    except Exception as e:
        logger.warning("Migration payoff_phase skipped (may already exist): %s", e)


def _migrate_audience_segment_preferences() -> None:
    """Add favorite_agent_ids and hated_agent_ids to audience_segments if missing."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM pragma_table_info('audience_segments') WHERE name IN ('favorite_agent_ids','hated_agent_ids')")
            )
            existing = {row[0] for row in result}
            if "favorite_agent_ids" not in existing:
                conn.execute(text("ALTER TABLE audience_segments ADD COLUMN favorite_agent_ids TEXT"))
                conn.commit()
            if "hated_agent_ids" not in existing:
                conn.execute(text("ALTER TABLE audience_segments ADD COLUMN hated_agent_ids TEXT"))
                conn.commit()
    except Exception as e:
        logger.warning("Migration audience_segment preferences skipped: %s", e)


def init_db() -> None:
    """Initialize database tables with retry logic.

    Retries up to _MAX_INIT_RETRIES times with 1-second backoff (Rule 7).
    Runs schema migration for new columns after create_all.
    """
    for attempt in range(_MAX_INIT_RETRIES):
        try:
            Base.metadata.create_all(bind=engine)
            _migrate_agents_columns()
            _migrate_storylines_payoff_phase()
            _migrate_audience_segment_preferences()
            logger.info(f"Database tables verified: {list(Base.metadata.tables.keys())}")
            return
        except Exception as e:
            logger.warning(f"init_db attempt {attempt + 1}/{_MAX_INIT_RETRIES} failed: {e}")
            if attempt == _MAX_INIT_RETRIES - 1:
                raise
            time.sleep(1)
