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
    StorylineCreate, StorylineAdvance, StorylineResponse,
    ChampionshipCreate, ChampionshipResponse,
    NarrativeLogResponse, WorldNewsResponse, WorldTickStatus,
    MatchBooking, SegmentBooking,
    PromoRequest, PromoResponse,
    ManagerCreate, ManagerResponse, ManagerClientCreate, ManagerClientResponse,
    StableCreate, StableResponse, StableMemberResponse, StableAddMember, StableUpdate,
)
from models.game_models import (
    PlayerDB, GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ShowDB, ShowSegmentDB, MatchDB,
    StorylineDB, StorylineParticipantDB, ChampionshipDB,
    PlayerActionDB, GameNarrativeLogDB, WorldNewsDB, ContractDB,
    ManagerDB, ManagerClientDB, StableDB, StableMemberDB,
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
from game_service import stable_service, manager_service

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


@router.post("/shows/{show_id}/promos", response_model=ShowSegmentResponse, status_code=201)
def api_book_promo(
    show_id: str,
    wrestler_id: str,
    target_wrestler_id: Optional[str] = None,
    promo_type: str = "in_ring",
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Book a promo segment on a show."""
    show = db.query(ShowDB).filter(ShowDB.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    try:
        seg = svc_book_promo_segment(
            db, show_id, show.world_id,
            wrestler_id=wrestler_id,
            target_wrestler_id=target_wrestler_id,
            promo_type=promo_type,
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
        # Resolve wrestler names for each participant
        participant_data = []
        for p in parts:
            wrestler = db.query(GameWrestlerDB).filter_by(id=p.wrestler_id).first()
            participant_data.append({
                "wrestler_id": p.wrestler_id,
                "wrestler_name": wrestler.name if wrestler else "Unknown",
                "role": p.role,
            })
        sl_dict.participants = participant_data
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
        resp.participants = [
            {"wrestler_id": wid, "wrestler_name": (db.query(GameWrestlerDB).filter_by(id=wid).first() or type('', (), {'name': 'Unknown'})).name, "role": role}
            for wid, role in zip(data.wrestler_ids, ["protagonist", "antagonist"] + ["ally"] * max(0, len(data.wrestler_ids) - 2))
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
        {"wrestler_id": p.wrestler_id, "wrestler_name": (db.query(GameWrestlerDB).filter_by(id=p.wrestler_id).first() or type('', (), {'name': 'Unknown'})).name, "role": p.role}
        for p in parts
    ]
    return resp


# ---------------------------------------------------------------------------
# Managers & Valets
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/managers", response_model=List[ManagerResponse])
def api_list_managers(
    world_id: str,
    federation_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all managers in a world."""
    managers = manager_service.list_managers(db, world_id, federation_id)
    return [ManagerResponse.model_validate(m) for m in managers]


@router.post("/worlds/{world_id}/managers", response_model=ManagerResponse, status_code=201)
def api_create_manager(
    world_id: str,
    data: ManagerCreate,
    federation_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new manager character."""
    try:
        mgr = manager_service.create_manager(
            db, world_id, name=data.name, alignment=data.alignment,
            archetype=data.archetype, federation_id=federation_id,
            real_name=data.real_name, gender=data.gender,
            personality_traits=data.personality_traits,
            catchphrase=data.catchphrase,
        )
        return ManagerResponse.model_validate(mgr)
    except ValueError as e:
        _handle_value_error(e)


@router.get("/worlds/{world_id}/manager-bonds")
def api_list_manager_bonds(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all manager-client bonds in a world."""
    bonds = manager_service.list_manager_bonds(db, world_id)
    results = []
    for item in bonds:
        bond = item["bond"]
        resp = ManagerClientResponse.model_validate(bond)
        resp.manager_name = item["manager_name"]
        resp.client_name = item["client_name"]
        results.append(resp)
    return results


@router.post("/worlds/{world_id}/manager-bonds", response_model=ManagerClientResponse, status_code=201)
def api_assign_manager(
    world_id: str,
    data: ManagerClientCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign a manager to a wrestler client."""
    try:
        world = get_world(db, world_id)
        if not world:
            raise HTTPException(status_code=404, detail="World not found")
        bond = manager_service.assign_manager(
            db, world_id, manager_id=data.manager_id,
            client_wrestler_id=data.client_wrestler_id,
            role=data.role, specialization=data.specialization,
            game_date=world.current_game_date,
        )
        return ManagerClientResponse.model_validate(bond)
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/manager-bonds/{bond_id}", status_code=204)
def api_remove_manager_bond(
    bond_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End a manager-client relationship."""
    if not manager_service.remove_manager(db, bond_id):
        raise HTTPException(status_code=404, detail="Bond not found")


@router.get("/wrestlers/{wrestler_id}/manager")
def api_get_wrestler_manager(
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
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


@router.post("/managers/{manager_id}/promo")
def api_manager_promo(
    manager_id: str,
    client_wrestler_id: str,
    target_wrestler_id: Optional[str] = None,
    promo_type: str = "in_ring",
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a promo where a manager speaks on behalf of their client."""
    result = manager_service.generate_manager_promo(
        db, manager_id, client_wrestler_id, target_wrestler_id, promo_type
    )
    if not result["content"]:
        raise HTTPException(status_code=404, detail="Manager or client not found")
    return result


# ---------------------------------------------------------------------------
# Stables / Factions
# ---------------------------------------------------------------------------

@router.get("/worlds/{world_id}/stables", response_model=List[StableResponse])
def api_list_stables(
    world_id: str,
    federation_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active stables in a world."""
    stables = stable_service.list_stables(db, world_id, federation_id)
    results = []
    for s in stables:
        data = stable_service.get_stable_with_members(db, s.id)
        resp = StableResponse.model_validate(s)
        resp.manager_name = data.get("manager_name")
        resp.members = [StableMemberResponse(**m) for m in data.get("members", [])]
        results.append(resp)
    return results


@router.post("/worlds/{world_id}/stables", response_model=StableResponse, status_code=201)
def api_create_stable(
    world_id: str,
    data: StableCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new stable/faction."""
    try:
        # Determine federation from the leader wrestler's contract
        leader = db.query(GameWrestlerDB).filter_by(id=data.leader_id).first()
        if not leader:
            raise HTTPException(status_code=404, detail="Leader wrestler not found")
        contract = db.query(ContractDB).filter_by(
            wrestler_id=data.leader_id, status="active"
        ).first()
        fed_id = contract.federation_id if contract else None
        if not fed_id:
            raise HTTPException(status_code=400, detail="Leader has no active contract")

        world = get_world(db, world_id)
        stable = stable_service.create_stable(
            db, world_id, fed_id, name=data.name,
            leader_id=data.leader_id,
            founding_member_ids=data.founding_member_ids,
            alignment=data.alignment,
            short_name=data.short_name,
            catchphrase=data.catchphrase,
            group_finisher_name=data.group_finisher_name,
            manager_id=data.manager_id,
            game_date=world.current_game_date if world else None,
        )
        detail = stable_service.get_stable_with_members(db, stable.id)
        resp = StableResponse.model_validate(stable)
        resp.manager_name = detail.get("manager_name")
        resp.members = [StableMemberResponse(**m) for m in detail.get("members", [])]
        return resp
    except ValueError as e:
        _handle_value_error(e)


@router.get("/stables/{stable_id}", response_model=StableResponse)
def api_get_stable(
    stable_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a stable with its members."""
    data = stable_service.get_stable_with_members(db, stable_id)
    if not data:
        raise HTTPException(status_code=404, detail="Stable not found")
    stable = data["stable"]
    resp = StableResponse.model_validate(stable)
    resp.manager_name = data.get("manager_name")
    resp.members = [StableMemberResponse(**m) for m in data.get("members", [])]
    return resp


@router.post("/stables/{stable_id}/members", status_code=201)
def api_add_stable_member(
    stable_id: str,
    data: StableAddMember,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a wrestler to a stable."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        raise HTTPException(status_code=404, detail="Stable not found")
    world = get_world(db, stable.world_id)
    member = stable_service.add_member(
        db, stable_id, data.wrestler_id, data.role,
        game_date=world.current_game_date if world else None,
    )
    return {"id": member.id, "wrestler_id": member.wrestler_id, "role": member.role}


@router.delete("/stables/{stable_id}/members/{wrestler_id}", status_code=204)
def api_remove_stable_member(
    stable_id: str,
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a wrestler from a stable."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        raise HTTPException(status_code=404, detail="Stable not found")
    world = get_world(db, stable.world_id)
    if not stable_service.remove_member(
        db, stable_id, wrestler_id,
        game_date=world.current_game_date if world else None,
    ):
        raise HTTPException(status_code=404, detail="Member not found")


@router.patch("/stables/{stable_id}", response_model=StableResponse)
def api_update_stable(
    stable_id: str,
    data: StableUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a stable's details."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        raise HTTPException(status_code=404, detail="Stable not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(stable, field, value)
    db.commit()
    detail = stable_service.get_stable_with_members(db, stable.id)
    resp = StableResponse.model_validate(stable)
    resp.manager_name = detail.get("manager_name")
    resp.members = [StableMemberResponse(**m) for m in detail.get("members", [])]
    return resp


@router.get("/wrestlers/{wrestler_id}/stable")
def api_get_wrestler_stable(
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
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
