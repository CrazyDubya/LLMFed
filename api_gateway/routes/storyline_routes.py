"""Storyline routes: storyline CRUD, advancement."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    StorylineCreate,
    StorylineAdvance,
    StorylineResponse,
)
from models.game_models import (
    GameWrestlerDB,
    StorylineDB,
    StorylineParticipantDB,
    ContractDB,
)
from game_service.world_service import get_world

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-storyline"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------


@router.get("/worlds/{world_id}/storylines", response_model=List[StorylineResponse])
async def api_list_storylines(
    world_id: str,
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List storylines in a world."""
    query = db.query(StorylineDB).filter(StorylineDB.world_id == world_id)
    if status:
        query = query.filter(StorylineDB.status == status)
    storylines = query.order_by(StorylineDB.heat.desc()).all()

    results = []
    for sl in storylines:
        parts = (
            db.query(StorylineParticipantDB)
            .filter(StorylineParticipantDB.storyline_id == sl.id)
            .all()
        )
        sl_dict = StorylineResponse.model_validate(sl)
        # Resolve wrestler names for each participant
        participant_data = []
        for p in parts:
            wrestler = db.query(GameWrestlerDB).filter_by(id=p.wrestler_id).first()
            participant_data.append(
                {
                    "wrestler_id": p.wrestler_id,
                    "wrestler_name": wrestler.name if wrestler else "Unknown",
                    "role": p.role,
                }
            )
        sl_dict.participants = participant_data
        results.append(sl_dict)
    return results


@router.post(
    "/worlds/{world_id}/storylines", response_model=StorylineResponse, status_code=201
)
async def api_create_storyline(
    world_id: str,
    data: StorylineCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promoter creates a storyline between wrestlers."""
    from game_service.storyline_service import create_storyline as sl_create

    world = get_world(db, world_id)

    federation_id = data.federation_id
    if not federation_id:
        contract = (
            db.query(ContractDB)
            .filter_by(wrestler_id=data.wrestler_ids[0], status="active")
            .first()
        )
        federation_id = contract.federation_id if contract else None

    try:
        storyline = sl_create(
            db,
            world_id,
            federation_id,
            wrestler_ids=data.wrestler_ids,
            storyline_type=data.storyline_type,
            name=data.name,
            description=data.description,
            game_date=world.current_game_date,
        )
        db.commit()
        resp = StorylineResponse.model_validate(storyline)
        resp.participants = [
            {
                "wrestler_id": wid,
                "wrestler_name": (
                    db.query(GameWrestlerDB).filter_by(id=wid).first()
                    or type("", (), {"name": "Unknown"})
                ).name,
                "role": role,
            }
            for wid, role in zip(
                data.wrestler_ids,
                ["protagonist", "antagonist"]
                + ["ally"] * max(0, len(data.wrestler_ids) - 2),
            )
        ]
        return resp
    except ValueError as e:
        _handle_value_error(e)


@router.patch("/storylines/{storyline_id}", response_model=StorylineResponse)
async def api_advance_storyline(
    storyline_id: str,
    data: StorylineAdvance,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Advance a storyline's status or boost its heat."""
    storyline = db.query(StorylineDB).filter_by(id=storyline_id).first()
    if not storyline:
        raise HTTPException(status_code=404, detail="Storyline not found")

    if data.status and data.status in ("brewing", "active", "climax", "resolved"):
        storyline.status = data.status
        if data.status == "resolved":
            from game_service.world_service import get_world

            world = get_world(db, storyline.world_id)
            storyline.end_date = world.current_game_date if world else None
    if data.heat_boost:
        storyline.heat = max(0, min(100, storyline.heat + data.heat_boost))

    db.commit()
    db.refresh(storyline)
    resp = StorylineResponse.model_validate(storyline)

    parts = db.query(StorylineParticipantDB).filter_by(storyline_id=storyline_id).all()
    resp.participants = [
        {
            "wrestler_id": p.wrestler_id,
            "wrestler_name": (
                db.query(GameWrestlerDB).filter_by(id=p.wrestler_id).first()
                or type("", (), {"name": "Unknown"})
            ).name,
            "role": p.role,
        }
        for p in parts
    ]
    return resp
