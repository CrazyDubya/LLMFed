"""
Fatigue: per-agent off-camera state. Increment when working a card, decay on rest.

Travel squad builder excludes agents over threshold so they get rest.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from models.db_models import AgentFatigueDB

logger = logging.getLogger(__name__)

FATIGUE_INCREMENT_PER_CARD = 25
FATIGUE_DECAY_PER_REST_DAY = 20
FATIGUE_THRESHOLD_REST = 70  # Over this = should rest (excluded from travel squad)
FATIGUE_MAX = 100


def _utc_date(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)


def get_fatigue(db, agent_id: str, federation_id: str, as_of: date) -> int:
    """Return fatigue level (0-100) for agent as of date. 0 if no row."""
    row = (
        db.query(AgentFatigueDB)
        .filter(
            AgentFatigueDB.agent_id == agent_id,
            AgentFatigueDB.federation_id == federation_id,
            AgentFatigueDB.as_of_date <= _utc_date(as_of),
        )
        .order_by(AgentFatigueDB.as_of_date.desc())
        .first()
    )
    if not row:
        return 0
    level = row.fatigue_level or 0
    row_date = row.as_of_date.date() if hasattr(row.as_of_date, "date") else row.as_of_date
    rest_days = max(0, (as_of - row_date).days)
    for _ in range(rest_days):
        level = max(0, level - FATIGUE_DECAY_PER_REST_DAY)
    return min(FATIGUE_MAX, level)


def increment_fatigue(
    db,
    agent_ids: list,
    federation_id: str,
    work_date: date,
) -> None:
    """Increment fatigue for each agent who worked a card on work_date."""
    as_of_dt = _utc_date(work_date)
    for agent_id in agent_ids:
        row = (
            db.query(AgentFatigueDB)
            .filter(
                AgentFatigueDB.agent_id == agent_id,
                AgentFatigueDB.federation_id == federation_id,
            )
            .order_by(AgentFatigueDB.as_of_date.desc())
            .first()
        )
        current = (row.fatigue_level or 0) if row else 0
        new_level = min(FATIGUE_MAX, current + FATIGUE_INCREMENT_PER_CARD)
        db.add(AgentFatigueDB(
            agent_id=agent_id,
            federation_id=federation_id,
            fatigue_level=new_level,
            last_work_date=as_of_dt,
            as_of_date=as_of_dt,
        ))
    try:
        db.commit()
    except Exception as e:
        logger.warning("fatigue increment commit: %s", e)
        db.rollback()


def is_rested(agent_id: str, federation_id: str, as_of: date, db) -> bool:
    """True if agent is below rest threshold (can work)."""
    return get_fatigue(db, agent_id, federation_id, as_of) < FATIGUE_THRESHOLD_REST
