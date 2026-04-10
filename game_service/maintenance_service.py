"""
Maintenance Service — data lifecycle management for long-running simulations.

Provides:
- Narrative log archival (move old logs to an archive table or prune)
- Engine request cleanup (purge old processed requests)
- Bounded sliding-window metrics aggregation
- Database statistics and health checks
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from models.db_models import NarrativeLogDB, EngineRequestDB

logger = logging.getLogger(__name__)

# Default retention: keep the last N entries in each table
DEFAULT_NARRATIVE_RETENTION = 10_000
DEFAULT_ENGINE_REQUEST_RETENTION = 5_000


def archive_narrative_logs(
    db: Session,
    retention_count: int = DEFAULT_NARRATIVE_RETENTION,
) -> int:
    """Delete the oldest narrative logs beyond the retention window.

    Returns the number of rows deleted.
    """
    total = db.query(func.count(NarrativeLogDB.id)).scalar() or 0
    if total <= retention_count:
        return 0

    to_delete = total - retention_count
    # Find the cutoff ID
    cutoff_row = (
        db.query(NarrativeLogDB.id)
        .order_by(NarrativeLogDB.id.asc())
        .offset(to_delete - 1)
        .limit(1)
        .first()
    )
    if cutoff_row is None:
        return 0

    deleted = (
        db.query(NarrativeLogDB)
        .filter(NarrativeLogDB.id <= cutoff_row[0])
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Archived %d narrative logs (kept %d)", deleted, retention_count)
    return deleted


def archive_engine_requests(
    db: Session,
    retention_count: int = DEFAULT_ENGINE_REQUEST_RETENTION,
) -> int:
    """Delete the oldest processed engine requests beyond the retention window.

    Returns the number of rows deleted.
    """
    total = (
        db.query(func.count(EngineRequestDB.id))
        .filter(EngineRequestDB.status == "processed")
        .scalar()
        or 0
    )
    if total <= retention_count:
        return 0

    to_delete = total - retention_count
    cutoff_row = (
        db.query(EngineRequestDB.id)
        .filter(EngineRequestDB.status == "processed")
        .order_by(EngineRequestDB.id.asc())
        .offset(to_delete - 1)
        .limit(1)
        .first()
    )
    if cutoff_row is None:
        return 0

    deleted = (
        db.query(EngineRequestDB)
        .filter(
            EngineRequestDB.id <= cutoff_row[0],
            EngineRequestDB.status == "processed",
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Archived %d engine requests (kept %d)", deleted, retention_count)
    return deleted


def archive_game_narrative_logs(
    db: Session,
    world_id: str,
    retention_days: int = 90,
    current_game_date: Optional[str] = None,
) -> int:
    """Delete game narrative logs older than *retention_days* game-days.

    Requires the current game date (YYYY-MM-DD string) to compute the cutoff.
    Returns the number of rows deleted.
    """
    from models.show_models import GameNarrativeLogDB

    if current_game_date is None:
        from models.game_models import WorldDB

        world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
        if world is None:
            return 0
        current_game_date = getattr(world, "current_game_date", None)
        if current_game_date is None:
            return 0

    # Parse and compute cutoff
    try:
        from datetime import timedelta

        current_dt = datetime.strptime(current_game_date, "%Y-%m-%d")
        cutoff_dt = current_dt - timedelta(days=retention_days)
        cutoff_date = cutoff_dt.strftime("%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid game date format: %s", current_game_date)
        return 0

    deleted = (
        db.query(GameNarrativeLogDB)
        .filter(
            GameNarrativeLogDB.world_id == world_id,
            GameNarrativeLogDB.game_date < cutoff_date,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info(
            "Archived %d game narrative logs for world %s (before %s)",
            deleted,
            world_id,
            cutoff_date,
        )
    return deleted


def run_full_maintenance(
    db: Session,
    narrative_retention: int = DEFAULT_NARRATIVE_RETENTION,
    engine_request_retention: int = DEFAULT_ENGINE_REQUEST_RETENTION,
) -> Dict[str, int]:
    """Run all maintenance tasks and return a summary of actions taken."""
    results = {}
    try:
        results["narrative_logs_deleted"] = archive_narrative_logs(
            db, narrative_retention
        )
    except Exception as e:
        logger.error("Narrative log archival failed: %s", e)
        db.rollback()
        results["narrative_logs_deleted"] = -1

    try:
        results["engine_requests_deleted"] = archive_engine_requests(
            db, engine_request_retention
        )
    except Exception as e:
        logger.error("Engine request archival failed: %s", e)
        db.rollback()
        results["engine_requests_deleted"] = -1

    return results


def get_table_stats(db: Session) -> Dict[str, Any]:
    """Return row counts for key tables (useful for monitoring)."""
    stats = {}
    for model, name in [
        (NarrativeLogDB, "narrative_logs"),
        (EngineRequestDB, "engine_requests"),
    ]:
        try:
            stats[name] = db.query(func.count(model.id)).scalar() or 0
        except Exception:
            stats[name] = -1

    # Game tables (may not exist if game service not used)
    try:
        from models.show_models import GameNarrativeLogDB

        stats["game_narrative_logs"] = (
            db.query(func.count(GameNarrativeLogDB.id)).scalar() or 0
        )
    except Exception:
        stats["game_narrative_logs"] = -1

    try:
        from models.show_models import ShowDB

        stats["shows"] = db.query(func.count(ShowDB.id)).scalar() or 0
    except Exception:
        stats["shows"] = -1

    try:
        from models.show_models import MatchDB

        stats["matches"] = db.query(func.count(MatchDB.id)).scalar() or 0
    except Exception:
        stats["matches"] = -1

    return stats
