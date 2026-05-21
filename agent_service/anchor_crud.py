"""CRUD for world anchor and conceptual card (target card for marquee show)."""

import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.db_models import WorldAnchorDB, ConceptualCardDB

logger = logging.getLogger(__name__)


def get_world_anchor(db: Session, federation_id: str) -> Optional[WorldAnchorDB]:
    """Fetch world anchor for federation."""
    if not federation_id:
        return None
    try:
        return db.query(WorldAnchorDB).filter(WorldAnchorDB.federation_id == federation_id).first()
    except SQLAlchemyError as e:
        logger.error("Error fetching world anchor: %s", e)
        return None


def get_conceptual_card(db: Session, federation_id: str) -> Optional[Dict[str, Any]]:
    """Fetch conceptual/target card for federation."""
    if not federation_id:
        return None
    try:
        row = db.query(ConceptualCardDB).filter(ConceptualCardDB.federation_id == federation_id).first()
        if not row:
            return None
        return {
            "federation_id": row.federation_id,
            "main_event_target": row.main_event_target,
            "title_matches_target": row.title_matches_target or [],
            "planned_storyline_payoffs": row.planned_storyline_payoffs or [],
            "metadata": row.metadata_json or {},
        }
    except SQLAlchemyError as e:
        logger.error("Error fetching conceptual card: %s", e)
        return None


def set_conceptual_card(
    db: Session,
    federation_id: str,
    main_event_target: Optional[Dict[str, Any]] = None,
    title_matches_target: Optional[List[Dict[str, Any]]] = None,
    planned_storyline_payoffs: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Set or update conceptual/target card for federation. Creates Trapdoor when plan shifts."""
    if not federation_id:
        return False
    try:
        row = db.query(ConceptualCardDB).filter(ConceptualCardDB.federation_id == federation_id).first()
        old_main = row.main_event_target if row else None
        if row:
            if main_event_target is not None:
                if old_main != main_event_target:
                    from agent_service.temporals_crud import create_trapdoor
                    create_trapdoor(
                        db, federation_id,
                        from_branch=str(old_main)[:200] if old_main else None,
                        to_branch=str(main_event_target)[:200] if main_event_target else None,
                        reason="conceptual_card_update",
                    )
                row.main_event_target = main_event_target
            if title_matches_target is not None:
                row.title_matches_target = title_matches_target
            if planned_storyline_payoffs is not None:
                row.planned_storyline_payoffs = planned_storyline_payoffs
            if metadata is not None:
                row.metadata_json = metadata
        else:
            db.add(ConceptualCardDB(
                federation_id=federation_id,
                main_event_target=main_event_target,
                title_matches_target=title_matches_target or [],
                planned_storyline_payoffs=planned_storyline_payoffs or [],
                metadata_json=metadata or {},
            ))
        db.commit()
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Error setting conceptual card: %s", e)
        return False
