"""Booking routes: show creation, match booking, promo booking, show card, match details, play-by-play."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    ShowCreate, ShowResponse, ShowSegmentResponse, ShowCardResponse,
    MatchResultResponse,
    MatchBooking, CardReorderRequest,
)
from models.game_models import (
    GameFederationDB, ShowDB, MatchDB,
)
from game_service.world_service import require_federation_owner
from game_service.show_service import (
    create_show as svc_create_show, book_match as svc_book_match,
    book_promo_segment as svc_book_promo_segment, get_show_card,
    reorder_card as svc_reorder_card,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-booking"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


def _require_show_owner(db: Session, user_id: str, show: ShowDB):
    """Verify the current user controls the federation that owns this show."""
    try:
        require_federation_owner(db, user_id, show.federation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ---------------------------------------------------------------------------
# Show creation
# ---------------------------------------------------------------------------

@router.post("/federations/{federation_id}/shows", response_model=ShowResponse, status_code=201)
def api_create_show(
    federation_id: str,
    data: ShowCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new show for a federation (promoter action)."""
    try:
        require_federation_owner(db, current_user.user_id, federation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == federation_id
    ).first()

    show = svc_create_show(
        db, fed.world_id, federation_id,
        data.name, data.show_type, data.venue or "Arena",
        data.capacity, data.game_date,
    )
    db.commit()
    db.refresh(show)
    return ShowResponse.model_validate(show)


# ---------------------------------------------------------------------------
# Show card
# ---------------------------------------------------------------------------

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


@router.patch("/shows/{show_id}/card/order", response_model=ShowCardResponse)
def api_reorder_card(
    show_id: str,
    data: CardReorderRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reorder the segments on a show's card."""
    show = db.query(ShowDB).filter(ShowDB.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    _require_show_owner(db, current_user.user_id, show)

    svc_reorder_card(db, show_id, data.segment_order)
    db.commit()

    segments = get_show_card(db, show_id)
    return ShowCardResponse(
        show=ShowResponse.model_validate(show),
        segments=[ShowSegmentResponse.model_validate(s) for s in segments],
    )


# ---------------------------------------------------------------------------
# Match booking
# ---------------------------------------------------------------------------

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
    _require_show_owner(db, current_user.user_id, show)

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


# ---------------------------------------------------------------------------
# Promo booking
# ---------------------------------------------------------------------------

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
    _require_show_owner(db, current_user.user_id, show)
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


# ---------------------------------------------------------------------------
# Match details
# ---------------------------------------------------------------------------

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
