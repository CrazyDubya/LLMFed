"""Federation routes: federation details, roster, free agents, shows list, championships."""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    FederationResponse,
    WrestlerResponse,
    ShowResponse,
    ChampionshipResponse,
)
from models.game_models import (
    ShowDB, ChampionshipDB,
)
from game_service.world_service import (
    get_federation, get_roster, get_free_agents, get_world_federations,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-federation"])


# ---------------------------------------------------------------------------
# Federation endpoints
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/federations", response_model=List[FederationResponse])
async def api_list_federations(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all federations in a world."""
    feds = get_world_federations(db, world_id)
    return [FederationResponse.model_validate(f) for f in feds]


@router.get("/federations/{federation_id}", response_model=FederationResponse)
async def api_get_federation(
    federation_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get federation details."""
    try:
        fed = get_federation(db, federation_id)
        return FederationResponse.model_validate(fed)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/federations/{federation_id}/roster", response_model=List[WrestlerResponse])
async def api_get_roster(
    federation_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a federation's roster."""
    wrestlers = get_roster(db, federation_id)
    return [WrestlerResponse.model_validate(w) for w in wrestlers]


@router.get("/worlds/{world_id}/free-agents", response_model=List[WrestlerResponse])
async def api_list_free_agents(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List free agent wrestlers in a world."""
    wrestlers = get_free_agents(db, world_id)
    return [WrestlerResponse.model_validate(w) for w in wrestlers]


# ---------------------------------------------------------------------------
# Federation shows listing
# ---------------------------------------------------------------------------

@router.get("/federations/{federation_id}/shows", response_model=List[ShowResponse])
async def api_list_shows(
    federation_id: str,
    limit: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List shows for a federation."""
    shows = db.query(ShowDB).filter(
        ShowDB.federation_id == federation_id,
    ).order_by(ShowDB.game_date.desc()).limit(limit).all()
    return [ShowResponse.model_validate(s) for s in shows]


# ---------------------------------------------------------------------------
# Championships
# ---------------------------------------------------------------------------

@router.get("/federations/{federation_id}/championships", response_model=List[ChampionshipResponse])
async def api_list_championships(
    federation_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List championships for a federation."""
    champs = db.query(ChampionshipDB).filter(
        ChampionshipDB.federation_id == federation_id,
        ChampionshipDB.is_active == True,
    ).all()
    return [ChampionshipResponse.model_validate(c) for c in champs]
