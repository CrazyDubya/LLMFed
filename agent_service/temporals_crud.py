"""CRUD for run-timeline gamification: Ripples, Trapdoors."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import RippleDB, TrapdoorDB
from models.temporals import RippleCause


def _to_dt(d: Optional[date]) -> Optional[datetime]:
    if d is None:
        return None
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


def create_ripple(
    db: Session,
    federation_id: str,
    cause: RippleCause | str,
    *,
    at_date: Optional[date] = None,
    agent_ids: Optional[List[str]] = None,
    storyline_ids: Optional[List[str]] = None,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a Ripple (effect). Returns ripple_id."""
    cause_val = cause.value if isinstance(cause, RippleCause) else str(cause)
    row = RippleDB(
        ripple_id=str(uuid.uuid4()),
        federation_id=federation_id,
        cause=cause_val,
        at_date=_to_dt(at_date) or datetime.now(timezone.utc),
        agent_ids=agent_ids or [],
        storyline_ids=storyline_ids or [],
        description=description,
        metadata_json=metadata or {},
    )
    db.add(row)
    return row.ripple_id


def create_trapdoor(
    db: Session,
    federation_id: str,
    *,
    from_branch: Optional[str] = None,
    to_branch: Optional[str] = None,
    reason: str = "",
    ripple_ids: Optional[List[str]] = None,
    at_date: Optional[date] = None,
) -> str:
    """Create a Trapdoor (change of direction). Returns trapdoor_id."""
    row = TrapdoorDB(
        trapdoor_id=str(uuid.uuid4()),
        federation_id=federation_id,
        at_date=_to_dt(at_date) or datetime.now(timezone.utc),
        from_branch=from_branch,
        to_branch=to_branch,
        reason=reason,
        ripple_ids=ripple_ids or [],
    )
    db.add(row)
    return row.trapdoor_id


def get_recent_ripples(
    db: Session,
    federation_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Return recent ripples for promoter/run-state context."""
    rows = (
        db.query(RippleDB)
        .filter(RippleDB.federation_id == federation_id)
        .order_by(RippleDB.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "ripple_id": r.ripple_id,
            "cause": r.cause,
            "agent_ids": r.agent_ids or [],
            "description": r.description,
        }
        for r in rows
    ]


def get_recent_trapdoors(
    db: Session,
    federation_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return recent trapdoors for promoter context."""
    rows = (
        db.query(TrapdoorDB)
        .filter(TrapdoorDB.federation_id == federation_id)
        .order_by(TrapdoorDB.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "trapdoor_id": r.trapdoor_id,
            "from_branch": r.from_branch,
            "to_branch": r.to_branch,
            "reason": r.reason,
        }
        for r in rows
    ]
