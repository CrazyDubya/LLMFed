"""Storyline routes: storyline CRUD, advancement."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    StorylineCreate, StorylineAdvance, StorylineResponse,
)
from models.game_models import (
    GameWrestlerDB, StorylineDB, StorylineParticipantDB, ContractDB,
)
from game_service.world_service import get_world, require_federation_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-storyline"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


def _require_storyline_federation_owner(db: Session, user_id: str, federation_id: Optional[str]):
    """Verify the current user controls the storyline's federation, if it has one."""
    if not federation_id:
        return
    try:
        require_federation_owner(db, user_id, federation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


def _wrestler_names(db: Session, wrestler_ids: List[str]) -> dict:
    """Batch-fetch wrestler names, avoiding a query per participant."""
    if not wrestler_ids:
        return {}
    rows = db.query(GameWrestlerDB).filter(GameWrestlerDB.id.in_(set(wrestler_ids))).all()
    return {w.id: w.name for w in rows}


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/storylines", response_model=List[StorylineResponse])
def api_list_storylines(
    world_id: str,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List storylines in a world."""
    query = db.query(StorylineDB).filter(StorylineDB.world_id == world_id)
    if status:
        query = query.filter(StorylineDB.status == status)
    storylines = query.order_by(StorylineDB.heat.desc()).limit(limit).all()

    storyline_ids = [sl.id for sl in storylines]
    parts_by_storyline: dict = {}
    if storyline_ids:
        all_parts = db.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.storyline_id.in_(storyline_ids)
        ).all()
        for p in all_parts:
            parts_by_storyline.setdefault(p.storyline_id, []).append(p)
        names = _wrestler_names(db, [p.wrestler_id for p in all_parts])
    else:
        names = {}

    results = []
    for sl in storylines:
        sl_dict = StorylineResponse.model_validate(sl)
        sl_dict.participants = [
            {
                "wrestler_id": p.wrestler_id,
                "wrestler_name": names.get(p.wrestler_id, "Unknown"),
                "role": p.role,
            }
            for p in parts_by_storyline.get(sl.id, [])
        ]
        results.append(sl_dict)
    return results


@router.post("/worlds/{world_id}/storylines", response_model=StorylineResponse, status_code=201)
def api_create_storyline(
    world_id: str,
    data: StorylineCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Promoter creates a storyline between wrestlers."""
    from game_service.storyline_service import create_storyline as sl_create
    world = get_world(db, world_id)

    federation_id = data.federation_id
    if not federation_id:
        contract = db.query(ContractDB).filter_by(
            wrestler_id=data.wrestler_ids[0], status="active"
        ).first()
        federation_id = contract.federation_id if contract else None

    _require_storyline_federation_owner(db, current_user.user_id, federation_id)

    try:
        storyline = sl_create(
            db, world_id, federation_id,
            wrestler_ids=data.wrestler_ids,
            storyline_type=data.storyline_type,
            name=data.name,
            description=data.description,
            game_date=world.current_game_date,
        )
        db.commit()
        resp = StorylineResponse.model_validate(storyline)
        names = _wrestler_names(db, data.wrestler_ids)
        roles = ["protagonist", "antagonist"] + ["ally"] * max(0, len(data.wrestler_ids) - 2)
        resp.participants = [
            {"wrestler_id": wid, "wrestler_name": names.get(wid, "Unknown"), "role": role}
            for wid, role in zip(data.wrestler_ids, roles)
        ]
        return resp
    except ValueError as e:
        _handle_value_error(e)


@router.patch("/storylines/{storyline_id}", response_model=StorylineResponse)
def api_advance_storyline(
    storyline_id: str,
    data: StorylineAdvance,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advance a storyline's status or boost its heat."""
    storyline = db.query(StorylineDB).filter_by(id=storyline_id).first()
    if not storyline:
        raise HTTPException(status_code=404, detail="Storyline not found")
    _require_storyline_federation_owner(db, current_user.user_id, storyline.federation_id)

    if data.status and data.status in ("brewing", "active", "climax", "resolved"):
        storyline.status = data.status
        if data.status == "resolved":
            world = get_world(db, storyline.world_id)
            storyline.end_date = world.current_game_date if world else None
    if data.heat_boost:
        storyline.heat = max(0, min(100, storyline.heat + data.heat_boost))

    db.commit()
    db.refresh(storyline)
    resp = StorylineResponse.model_validate(storyline)

    parts = db.query(StorylineParticipantDB).filter_by(storyline_id=storyline_id).all()
    names = _wrestler_names(db, [p.wrestler_id for p in parts])
    resp.participants = [
        {"wrestler_id": p.wrestler_id, "wrestler_name": names.get(p.wrestler_id, "Unknown"), "role": p.role}
        for p in parts
    ]
    return resp
