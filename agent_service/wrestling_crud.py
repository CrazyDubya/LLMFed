"""CRUD for titles, reigns, storylines (wrestling domain)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.db_models import TitleDB, ReignDB, StorylineDB

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_title_by_id(db: Session, title_id: str) -> Optional[TitleDB]:
    """Fetch title by ID."""
    if not title_id:
        return None
    try:
        return db.query(TitleDB).filter(TitleDB.title_id == title_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching title {title_id}: {e}")
        return None


def get_current_champion(db: Session, title_id: str) -> Optional[str]:
    """Return agent_id of current champion (most recent reign with no end_date)."""
    try:
        reign = (
            db.query(ReignDB)
            .filter(ReignDB.title_id == title_id, ReignDB.end_date.is_(None))
            .order_by(ReignDB.start_date.desc())
            .first()
        )
        return reign.champion_id if reign else None
    except SQLAlchemyError as e:
        logger.error(f"Error fetching champion for title {title_id}: {e}")
        return None


def start_reign(
    db: Session,
    title_id: str,
    champion_id: str,
    start_date: Optional[datetime] = None,
) -> Optional[ReignDB]:
    """End previous reign (if any) and start new reign. Returns new ReignDB."""
    start = start_date or _utc_now()
    try:
        prev = (
            db.query(ReignDB)
            .filter(ReignDB.title_id == title_id, ReignDB.end_date.is_(None))
            .first()
        )
        if prev:
            prev.end_date = start
            prev.end_reason = "lost"
            db.add(prev)
        reign = ReignDB(
            reign_id=str(uuid.uuid4()),
            title_id=title_id,
            champion_id=champion_id,
            start_date=start,
        )
        db.add(reign)
        return reign
    except SQLAlchemyError as e:
        logger.error(f"Error starting reign: {e}")
        return None


def get_storyline_by_id(db: Session, storyline_id: str) -> Optional[StorylineDB]:
    """Fetch storyline by ID."""
    if not storyline_id:
        return None
    try:
        return db.query(StorylineDB).filter(StorylineDB.storyline_id == storyline_id).first()
    except SQLAlchemyError as e:
        return None


def create_title(
    db: Session,
    federation_id: str,
    name: str,
    tier: str = "mid_card",
    prestige: int = 50,
) -> Optional[TitleDB]:
    """Create a new title."""
    try:
        title = TitleDB(
            title_id=str(uuid.uuid4()),
            federation_id=federation_id,
            name=name,
            tier=tier,
            prestige=prestige,
        )
        db.add(title)
        db.commit()
        db.refresh(title)
        return title
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating title: {e}")
        return None


def get_titles(
    db: Session,
    federation_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[TitleDB]:
    """Fetch titles, optionally filtered by federation."""
    try:
        q = db.query(TitleDB)
        if federation_id:
            q = q.filter(TitleDB.federation_id == federation_id)
        return q.offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching titles: {e}")
        return []


def create_storyline(
    db: Session,
    federation_id: str,
    title: str,
    participant_ids: Optional[List[str]] = None,
    storyline_type: str = "feud",
    heat: int = 50,
) -> Optional[StorylineDB]:
    """Create a new storyline."""
    try:
        now = _utc_now()
        story = StorylineDB(
            storyline_id=str(uuid.uuid4()),
            federation_id=federation_id,
            title=title,
            participant_ids=participant_ids or [],
            storyline_type=storyline_type,
            status="active",
            heat=heat,
            start_date=now,
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        return story
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating storyline: {e}")
        return None


def get_storylines(
    db: Session,
    federation_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[StorylineDB]:
    """Fetch storylines, optionally filtered by federation and status."""
    try:
        q = db.query(StorylineDB)
        if federation_id:
            q = q.filter(StorylineDB.federation_id == federation_id)
        if status:
            q = q.filter(StorylineDB.status == status)
        return q.offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching storylines: {e}")
        return []
