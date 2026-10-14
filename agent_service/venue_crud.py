"""CRUD for venues (place where card happens)."""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from models.db_models import VenueDB

logger = logging.getLogger(__name__)


def get_venue(db: Session, venue_id: str) -> Optional[VenueDB]:
    """Fetch venue by ID."""
    if not venue_id:
        return None
    try:
        return db.query(VenueDB).filter(VenueDB.venue_id == venue_id).first()
    except Exception as e:
        logger.warning("get_venue %s: %s", venue_id, e)
        return None


def venue_to_hint(v: VenueDB) -> Dict[str, Any]:
    """Turn VenueDB row into hint dict for prompts."""
    if not v:
        return {}
    return {
        "venue_id": v.venue_id,
        "name": v.name,
        "location": getattr(v, "location", None),
        "capacity": getattr(v, "capacity", 5000),
        "venue_type": getattr(v, "venue_type", "arena"),
        "concessions_available": getattr(v, "concessions_available", True),
        "ppv_capable": getattr(v, "ppv_capable", False),
    }


def get_default_venue_for_federation(db: Session, federation_id: str) -> Optional[VenueDB]:
    """Return first venue for federation, or None. Caller can create one if needed."""
    try:
        return (
            db.query(VenueDB)
            .filter(VenueDB.federation_id == federation_id)
            .first()
        )
    except Exception as e:
        logger.warning("get_default_venue_for_federation: %s", e)
        return None


def ensure_default_venue(db: Session, federation_id: str) -> Optional[str]:
    """Ensure federation has at least one venue; return venue_id. Creates one if none exist."""
    v = get_default_venue_for_federation(db, federation_id)
    if v:
        return v.venue_id
    try:
        new_venue = VenueDB(
            venue_id=str(uuid.uuid4()),
            federation_id=federation_id,
            name="Home Arena",
            location=None,
            capacity=5000,
            venue_type="arena",
            concessions_available=True,
            ppv_capable=False,
        )
        db.add(new_venue)
        db.commit()
        return new_venue.venue_id
    except Exception as e:
        logger.warning("ensure_default_venue: %s", e)
        db.rollback()
        return None
