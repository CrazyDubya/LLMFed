"""CRUD for media coverage: next-day recaps, live blogs."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone, timedelta

from models.db_models import MediaOutletDB, CoverageDB


def _get_or_create_default_outlet(db, federation_id: str) -> str:
    """Get or create default 'Recap Wire' outlet for federation."""
    row = db.query(MediaOutletDB).filter(
        MediaOutletDB.federation_id == federation_id,
        MediaOutletDB.name == "Recap Wire",
    ).first()
    if row:
        return row.outlet_id
    outlet_id = str(uuid.uuid4())
    db.add(MediaOutletDB(
        outlet_id=outlet_id,
        federation_id=federation_id,
        name="Recap Wire",
        outlet_type="blog",
        reach="federation",
    ))
    return outlet_id


def create_next_day_coverage(
    db,
    card_id: str,
    federation_id: str,
    card_date: date,
) -> str:
    """
    Create a Coverage record for next-day recap (scope=next_day, published_at=card_date+1).
    Returns coverage_id. No LLM call to write the article—just the data hook.
    """
    outlet_id = _get_or_create_default_outlet(db, federation_id)
    published_at = datetime.combine(
        card_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    coverage_id = str(uuid.uuid4())
    db.add(CoverageDB(
        coverage_id=coverage_id,
        federation_id=federation_id,
        outlet_id=outlet_id,
        scope="next_day",
        target_card_id=card_id,
        published_at=published_at,
    ))
    return coverage_id
