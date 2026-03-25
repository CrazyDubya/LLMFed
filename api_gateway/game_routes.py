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
    ShowCreate, ShowResponse, ShowSegmentResponse, ShowCardResponse,
    MatchResultResponse,
    PlayerActionSubmit, PlayerActionResponse,
    StorylineResponse, ChampionshipCreate, ChampionshipResponse,
    NarrativeLogResponse, WorldNewsResponse, WorldTickStatus,
    MatchBooking, SegmentBooking,
    PromoRequest, PromoResponse,
)
from models.game_models import (
    PlayerDB, GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ShowDB, ShowSegmentDB, MatchDB,
    StorylineDB, StorylineParticipantDB, ChampionshipDB,
    PlayerActionDB, GameNarrativeLogDB, WorldNewsDB, ContractDB,
)
from game_service.auth_service import register_user, authenticate_user, create_user_token
from game_service.world_service import (
    create_world, create_player, get_world, get_player_for_user,
    get_federation, get_roster, get_free_agents,
    get_world_federations, get_world_wrestlers, get_wrestler_with_stats,
)
from game_service.world_ticker import WorldTicker
from game_service.show_service import (
    create_show as svc_create_show, book_match as svc_book_match,
    book_promo_segment as svc_book_promo_segment, get_show_card,
)
from game_service.promo_service import generate_promo as svc_generate_promo

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


@router.post("/federations/{federation_id}/shows", response_model=ShowResponse, status_code=201)
def api_create_show(
    federation_id: str,
    data: ShowCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new show for a federation (promoter action)."""
    try:
        player = get_player_for_user(db, current_user.user_id, None)
    except ValueError:
        player = None

    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == federation_id
    ).first()
    if not fed:
        raise HTTPException(status_code=404, detail="Federation not found")

    show = svc_create_show(
        db, fed.world_id, federation_id,
        data.name, data.show_type, data.venue or "Arena",
        data.capacity, data.game_date,
    )
    db.commit()
    db.refresh(show)
    return ShowResponse.model_validate(show)


@router.get("/shows/{show_id}/card", response_model=ShowCardResponse)
def api_get_show_card(
    show_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the full card for a show."""
    show = db.query(ShowDB).filter(ShowDB.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    segments = get_show_card(db, show_id)
    return ShowCardResponse(
        show=ShowResponse.model_validate(show),
        segments=[ShowSegmentResponse.model_validate(s) for s in segments],
    )


@router.post("/shows/{show_id}/matches", response_model=ShowSegmentResponse, status_code=201)
def api_book_match(
    show_id: str,
    data: MatchBooking,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Book a match on a show."""
    show = db.query(ShowDB).filter(ShowDB.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    try:
        seg = svc_book_match(
            db, show_id, show.world_id,
            wrestler_ids=data.participant_ids,
            match_type=data.match_type,
            stipulation=data.stipulation,
            is_title_match=data.is_title_match,
            championship_id=data.championship_id,
            planned_winner_id=data.planned_winner_id,
            planned_finish=data.planned_finish or "pinfall",
            position=data.segment_position,
        )
        db.commit()
        db.refresh(seg)
        return ShowSegmentResponse.model_validate(seg)
    except ValueError as e:
        _handle_value_error(e)


@router.get("/matches/{match_id}", response_model=MatchResultResponse)
def api_get_match(
    match_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get match result details."""
    match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchResultResponse.model_validate(match)


# ---------------------------------------------------------------------------
# Match play-by-play
# ---------------------------------------------------------------------------

@router.get("/matches/{match_id}/play-by-play")
def api_get_play_by_play(
    match_id: str,
    highlights_only: bool = False,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get match play-by-play from simulation log."""
    match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if not match.is_completed:
        raise HTTPException(status_code=400, detail="Match not yet completed")

    log = match.simulation_log or []
    if highlights_only:
        log = [entry for entry in log if entry.get("highlight_tier", 1) >= 2]

    return {
        "match_id": match.id,
        "winner_id": match.winner_id,
        "finish_type": match.finish_type,
        "finish_description": match.finish_description,
        "match_rating": match.match_rating,
        "crowd_heat": match.crowd_heat,
        "duration_minutes": match.duration_minutes,
        "spots": log,
    }


# ---------------------------------------------------------------------------
# Promo endpoints
# ---------------------------------------------------------------------------

@router.post("/worlds/{world_id}/promos", response_model=PromoResponse, status_code=201)
def api_generate_promo(
    world_id: str,
    data: PromoRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate or submit a promo for a wrestler."""
    world = get_world(db, world_id)
    try:
        promo = svc_generate_promo(
            db, world_id, data.wrestler_id,
            target_wrestler_id=data.target_wrestler_id,
            promo_type=data.promo_type,
            player_direction=data.player_direction,
            game_date=world.current_game_date,
            is_player_written=bool(data.player_content),
            player_content=data.player_content,
        )
        db.commit()
        db.refresh(promo)
        return PromoResponse.model_validate(promo)
    except ValueError as e:
        _handle_value_error(e)


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
