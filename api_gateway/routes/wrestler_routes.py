"""Wrestler routes: wrestler details, wrestler stats, wrestler stable/manager info."""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    WrestlerResponse,
    WrestlerStatsResponse,
    WrestlerDetailResponse,
)
from models.game_models import (
    ContractDB,
    ChampionshipDB,
    StorylineParticipantDB,
)
from game_service.world_service import (
    get_world_wrestlers,
    get_wrestler_with_stats,
)
from game_service import stable_service, manager_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-wrestler"])


# ---------------------------------------------------------------------------
# Wrestler endpoints
# ---------------------------------------------------------------------------


@router.get("/worlds/{world_id}/wrestlers", response_model=List[WrestlerResponse])
async def api_list_wrestlers(
    world_id: str,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List wrestlers in a world."""
    wrestlers = get_world_wrestlers(db, world_id, limit=limit)
    return [WrestlerResponse.model_validate(w) for w in wrestlers]


@router.get("/wrestlers/{wrestler_id}", response_model=WrestlerDetailResponse)
async def api_get_wrestler(
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get wrestler details with stats."""
    try:
        wrestler, stats = get_wrestler_with_stats(db, wrestler_id)
        # Get current federation
        contract = (
            db.query(ContractDB)
            .filter(
                ContractDB.wrestler_id == wrestler_id,
                ContractDB.status == "active",
            )
            .first()
        )

        # Get championships
        champs = (
            db.query(ChampionshipDB)
            .filter(
                ChampionshipDB.current_holder_id == wrestler_id,
            )
            .all()
        )

        # Get active storylines
        storyline_parts = (
            db.query(StorylineParticipantDB)
            .filter(
                StorylineParticipantDB.wrestler_id == wrestler_id,
                StorylineParticipantDB.left_date == None,
            )
            .all()
        )

        # Compute win/loss record
        from core_engine.match_aftermath import compute_win_loss

        win_loss = compute_win_loss(db, wrestler_id)

        return WrestlerDetailResponse(
            wrestler=WrestlerResponse.model_validate(wrestler),
            stats=WrestlerStatsResponse.model_validate(stats) if stats else None,
            current_federation=contract.federation_id if contract else None,
            current_championships=[c.name for c in champs],
            active_storylines=[sp.storyline_id for sp in storyline_parts],
            win_loss=win_loss,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/wrestlers/{wrestler_id}/manager")
async def api_get_wrestler_manager(
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a wrestler's active manager."""
    result = manager_service.get_wrestler_manager(db, wrestler_id)
    if not result:
        return {"has_manager": False}
    bond = result["bond"]
    return {
        "has_manager": True,
        "manager_id": bond.manager_id,
        "manager_name": result["manager_name"],
        "role": bond.role,
        "effectiveness": bond.effectiveness,
        "specialization": bond.specialization,
        "charisma_bonus": bond.charisma_bonus,
        "heat_bonus": bond.heat_bonus,
    }


@router.get("/wrestlers/{wrestler_id}/stable")
async def api_get_wrestler_stable(
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the stable a wrestler belongs to, if any."""
    result = stable_service.get_wrestler_stable(db, wrestler_id)
    if not result:
        return {"in_stable": False}
    stable = result["stable"]
    member = result["member"]
    return {
        "in_stable": True,
        "stable_id": stable.id,
        "stable_name": stable.name,
        "role": member.role,
        "loyalty": member.loyalty,
        "influence": member.influence,
    }
