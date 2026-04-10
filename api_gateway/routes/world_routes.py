"""World routes: world creation, world state, player creation, world tick, narrative, news."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    WorldCreate, WorldResponse,
    PlayerCreate, PlayerResponse,
    PlayerActionSubmit, PlayerActionResponse,
    NarrativeLogResponse, WorldNewsResponse, WorldTickStatus,
    PromoRequest, PromoResponse,
)
from models.game_models import (
    PlayerActionDB, GameNarrativeLogDB, WorldNewsDB,
)
from game_service.world_service import (
    create_world, create_player, get_world, get_player_for_user,
)
from game_service.world_ticker import WorldTicker
from api_gateway.websocket_hub import manager as ws_manager
from game_service.promo_service import generate_promo as svc_generate_promo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-world"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


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
async def api_advance_world(
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

        events_today = result["day_results"][-1]["events"] if result["day_results"] else []

        # Broadcast tick to all connected WebSocket clients
        await ws_manager.broadcast_to_world(world_id, {
            "type": "tick",
            "world_id": world_id,
            "game_date": world.current_game_date,
            "tick": world.current_tick,
            "events": events_today,
            "auto": False,
        })

        # Broadcast individual notable events
        for day in result.get("day_results", []):
            for event in day.get("events", []):
                if "show" in event.lower() and "completed" in event.lower():
                    await ws_manager.broadcast_to_world(world_id, {
                        "type": "show_completed",
                        "world_id": world_id,
                        "description": event,
                    })

        return WorldTickStatus(
            world_id=world_id,
            current_game_date=world.current_game_date,
            current_tick=world.current_tick,
            events_today=events_today,
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
