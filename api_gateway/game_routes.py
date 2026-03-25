"""
Game API routes for LLMFed wrestling world.

Provides endpoints for authentication, world management, player actions,
and game state queries.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    WorldCreate, WorldResponse,
    PlayerCreate, PlayerResponse,
    FederationResponse, FederationUpdate,
    WrestlerResponse, WrestlerStatsResponse, WrestlerDetailResponse,
    ShowCreate, ShowResponse,
    PlayerActionSubmit, PlayerActionResponse,
    StorylineResponse, ChampionshipCreate, ChampionshipResponse,
    NarrativeLogResponse, WorldNewsResponse, WorldTickStatus,
    MatchBooking, SegmentBooking,
)
from models.game_models import (
    PlayerDB, GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ShowDB, StorylineDB, StorylineParticipantDB, ChampionshipDB,
    PlayerActionDB, GameNarrativeLogDB, WorldNewsDB, ContractDB,
)
from game_service.auth_service import register_user, authenticate_user, create_user_token
from game_service.world_service import (
    create_world, create_player, get_world, get_player_for_user,
    get_federation, get_roster, get_free_agents,
    get_world_federations, get_world_wrestlers, get_wrestler_with_stats,
)
from game_service.world_ticker import WorldTicker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/game", tags=["game"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def api_register(data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        user = register_user(db, data.email, data.username, data.password, data.display_name)
        token = create_user_token(user)
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/auth/login", response_model=TokenResponse)
def api_login(data: UserLogin, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    try:
        user = authenticate_user(db, data.username, data.password)
        token = create_user_token(user)
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/auth/me", response_model=UserResponse)
def api_get_me(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user info."""
    from game_service.auth_service import get_user_by_id
    try:
        user = get_user_by_id(db, current_user.user_id)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# World endpoints
# ---------------------------------------------------------------------------

@router.post("/worlds", response_model=WorldResponse, status_code=201)
def api_create_world(
    data: WorldCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new game world."""
    world = create_world(
        db, data.name, data.description, data.is_multiplayer,
        data.max_players, data.world_config,
    )
    return WorldResponse.model_validate(world)


@router.get("/worlds/{world_id}", response_model=WorldResponse)
def api_get_world(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get world details."""
    try:
        world = get_world(db, world_id)
        return WorldResponse.model_validate(world)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/worlds/{world_id}/my-player", response_model=PlayerResponse)
def api_get_my_player(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's player in a world."""
    try:
        player = get_player_for_user(db, current_user.user_id, world_id)
        return PlayerResponse.model_validate(player)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Player endpoints
# ---------------------------------------------------------------------------

@router.post("/players", response_model=PlayerResponse, status_code=201)
def api_create_player(
    data: PlayerCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a player in a world (choose promoter or wrestler)."""
    try:
        player = create_player(
            db, current_user.user_id, data.world_id, data.player_type,
            federation_name=data.federation_name,
            federation_description=data.federation_description,
            wrestler_name=data.wrestler_name,
            wrestler_gimmick=data.wrestler_gimmick,
            wrestler_alignment=data.wrestler_alignment,
            wrestler_style=data.wrestler_style,
        )
        return PlayerResponse.model_validate(player)
    except ValueError as e:
        _handle_value_error(e)


# ---------------------------------------------------------------------------
# Federation endpoints
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/federations", response_model=List[FederationResponse])
def api_list_federations(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all federations in a world."""
    feds = get_world_federations(db, world_id)
    return [FederationResponse.model_validate(f) for f in feds]


@router.get("/federations/{federation_id}", response_model=FederationResponse)
def api_get_federation(
    federation_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get federation details."""
    try:
        fed = get_federation(db, federation_id)
        return FederationResponse.model_validate(fed)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/federations/{federation_id}/roster", response_model=List[WrestlerResponse])
def api_get_roster(
    federation_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a federation's roster."""
    wrestlers = get_roster(db, federation_id)
    return [WrestlerResponse.model_validate(w) for w in wrestlers]


# ---------------------------------------------------------------------------
# Wrestler endpoints
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/wrestlers", response_model=List[WrestlerResponse])
def api_list_wrestlers(
    world_id: str,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List wrestlers in a world."""
    wrestlers = get_world_wrestlers(db, world_id, limit=limit)
    return [WrestlerResponse.model_validate(w) for w in wrestlers]


@router.get("/worlds/{world_id}/free-agents", response_model=List[WrestlerResponse])
def api_list_free_agents(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List free agent wrestlers in a world."""
    wrestlers = get_free_agents(db, world_id)
    return [WrestlerResponse.model_validate(w) for w in wrestlers]


@router.get("/wrestlers/{wrestler_id}", response_model=WrestlerDetailResponse)
def api_get_wrestler(
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get wrestler details with stats."""
    try:
        wrestler, stats = get_wrestler_with_stats(db, wrestler_id)
        # Get current federation
        contract = db.query(ContractDB).filter(
            ContractDB.wrestler_id == wrestler_id,
            ContractDB.status == "active",
        ).first()

        # Get championships
        champs = db.query(ChampionshipDB).filter(
            ChampionshipDB.current_holder_id == wrestler_id,
        ).all()

        # Get active storylines
        storyline_parts = db.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.wrestler_id == wrestler_id,
            StorylineParticipantDB.left_date == None,
        ).all()

        return WrestlerDetailResponse(
            wrestler=WrestlerResponse.model_validate(wrestler),
            stats=WrestlerStatsResponse.model_validate(stats) if stats else None,
            current_federation=contract.federation_id if contract else None,
            current_championships=[c.name for c in champs],
            active_storylines=[sp.storyline_id for sp in storyline_parts],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Show endpoints
# ---------------------------------------------------------------------------

@router.get("/federations/{federation_id}/shows", response_model=List[ShowResponse])
def api_list_shows(
    federation_id: str,
    limit: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List shows for a federation."""
    shows = db.query(ShowDB).filter(
        ShowDB.federation_id == federation_id,
    ).order_by(ShowDB.game_date.desc()).limit(limit).all()
    return [ShowResponse.model_validate(s) for s in shows]


# ---------------------------------------------------------------------------
# Player action endpoints
# ---------------------------------------------------------------------------

@router.post("/worlds/{world_id}/actions", response_model=PlayerActionResponse, status_code=202)
def api_submit_action(
    world_id: str,
    data: PlayerActionSubmit,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a player action to the world's action queue."""
    try:
        player = get_player_for_user(db, current_user.user_id, world_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="No player in this world")

    action = PlayerActionDB(
        world_id=world_id,
        player_id=player.id,
        action_type=data.action_type,
        action_data=data.action_data,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return PlayerActionResponse.model_validate(action)


@router.get("/worlds/{world_id}/actions", response_model=List[PlayerActionResponse])
def api_list_actions(
    world_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List player actions in a world."""
    try:
        player = get_player_for_user(db, current_user.user_id, world_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="No player in this world")

    query = db.query(PlayerActionDB).filter(
        PlayerActionDB.player_id == player.id,
    )
    if status:
        query = query.filter(PlayerActionDB.status == status)
    actions = query.order_by(PlayerActionDB.submitted_at.desc()).limit(limit).all()
    return [PlayerActionResponse.model_validate(a) for a in actions]


# ---------------------------------------------------------------------------
# World tick (advance game)
# ---------------------------------------------------------------------------

@router.post("/worlds/{world_id}/tick", response_model=WorldTickStatus)
def api_advance_world(
    world_id: str,
    days: int = 1,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advance the world by N game days."""
    if days < 1 or days > 30:
        raise HTTPException(status_code=400, detail="days must be 1-30")

    try:
        ticker = WorldTicker(db, world_id)
        result = ticker.tick(days)

        world = get_world(db, world_id)
        pending = db.query(PlayerActionDB).filter(
            PlayerActionDB.world_id == world_id,
            PlayerActionDB.status == "pending",
        ).count()

        return WorldTickStatus(
            world_id=world_id,
            current_game_date=world.current_game_date,
            current_tick=world.current_tick,
            events_today=result["day_results"][-1]["events"] if result["day_results"] else [],
            pending_actions=pending,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Narrative & News
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/narrative", response_model=List[NarrativeLogResponse])
def api_get_narrative(
    world_id: str,
    limit: int = 50,
    min_importance: int = 1,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recent narrative events for a world."""
    logs = db.query(GameNarrativeLogDB).filter(
        GameNarrativeLogDB.world_id == world_id,
        GameNarrativeLogDB.importance >= min_importance,
    ).order_by(GameNarrativeLogDB.created_at.desc()).limit(limit).all()
    return [NarrativeLogResponse.model_validate(l) for l in logs]


@router.get("/worlds/{world_id}/news", response_model=List[WorldNewsResponse])
def api_get_news(
    world_id: str,
    limit: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get world news articles."""
    news = db.query(WorldNewsDB).filter(
        WorldNewsDB.world_id == world_id,
    ).order_by(WorldNewsDB.created_at.desc()).limit(limit).all()
    return [WorldNewsResponse.model_validate(n) for n in news]


# ---------------------------------------------------------------------------
# Championships
# ---------------------------------------------------------------------------

@router.get("/federations/{federation_id}/championships", response_model=List[ChampionshipResponse])
def api_list_championships(
    federation_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List championships for a federation."""
    champs = db.query(ChampionshipDB).filter(
        ChampionshipDB.federation_id == federation_id,
        ChampionshipDB.is_active == True,
    ).all()
    return [ChampionshipResponse.model_validate(c) for c in champs]


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/storylines", response_model=List[StorylineResponse])
def api_list_storylines(
    world_id: str,
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List storylines in a world."""
    query = db.query(StorylineDB).filter(StorylineDB.world_id == world_id)
    if status:
        query = query.filter(StorylineDB.status == status)
    storylines = query.order_by(StorylineDB.heat.desc()).all()

    results = []
    for sl in storylines:
        parts = db.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.storyline_id == sl.id
        ).all()
        sl_dict = StorylineResponse.model_validate(sl)
        sl_dict.participants = [
            {"wrestler_id": p.wrestler_id, "role": p.role}
            for p in parts
        ]
        results.append(sl_dict)
    return results
