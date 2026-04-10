"""
Show simulation service — extracted from WorldTicker._simulate_show.

Contains all logic for simulating a single show: match simulation,
promo evaluation, card psychology, viewership, and news generation.
"""

import logging
import os
import random
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from models.game_models import (
    GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ShowDB, ShowSegmentDB, MatchDB, MatchParticipantDB,
    PromoDB, WorldDB,
)

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes")

# ------------------------------------------------------------------
# Lazy imports (same pattern as world_ticker)
# ------------------------------------------------------------------

_match_engine = None
_show_service = None
_storyline_service = None
_match_aftermath = None
_news_service = None
_viewership_service = None
_stable_service = None


def _get_match_engine():
    global _match_engine
    if _match_engine is None:
        from core_engine import match_engine as _me
        _match_engine = _me
    return _match_engine


def _get_show_service():
    global _show_service
    if _show_service is None:
        from game_service import show_service as _ss
        _show_service = _ss
    return _show_service


def _get_storyline_service():
    global _storyline_service
    if _storyline_service is None:
        from game_service import storyline_service as _sls
        _storyline_service = _sls
    return _storyline_service


def _get_match_aftermath():
    global _match_aftermath
    if _match_aftermath is None:
        from core_engine import match_aftermath as _ma
        _match_aftermath = _ma
    return _match_aftermath


def _get_news_service():
    global _news_service
    if _news_service is None:
        from game_service import news_service as _ns
        _news_service = _ns
    return _news_service


def _get_viewership_service():
    global _viewership_service
    if _viewership_service is None:
        from game_service import viewership_service as _vs
        _viewership_service = _vs
    return _viewership_service


def _get_stable_service():
    global _stable_service
    if _stable_service is None:
        from game_service import stable_service as _stbs
        _stable_service = _stbs
    return _stable_service


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def simulate_show(
    db: Session,
    show: ShowDB,
    world: WorldDB,
    log_event: Callable,
) -> dict:
    """Simulate a single show, running each match through the match engine.

    Parameters
    ----------
    db : Session
        Active database session.
    show : ShowDB
        The show to simulate (must not yet be completed).
    world : WorldDB
        The current world (used for game date, tick, world id).
    log_event : callable
        ``log_event(event_type, description, involved, importance)`` callback
        for recording narrative events.

    Returns
    -------
    dict with ``attendance``, ``overall_rating``, ``events`` list.
    """
    me = _get_match_engine()
    sl_svc = _get_storyline_service()
    aftermath = _get_match_aftermath()

    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == show.federation_id
    ).first()

    prestige_factor = (fed.prestige if fed else 50) / 100

    # Simulate each match segment through the engine
    segments = db.query(ShowSegmentDB).filter(
        ShowSegmentDB.show_id == show.id,
    ).order_by(ShowSegmentDB.position).all()

    match_segments = [s for s in segments if s.segment_type == "match" and s.match_id]
    total_segments = len(match_segments)

    match_ratings: List[float] = []
    events: List[str] = []
    # Show momentum flows between segments — hot crowd carries forward
    show_momentum = 50  # Neutral start

    for idx, seg in enumerate(segments):
        if seg.segment_type == "match" and seg.match_id:
            show_momentum, seg_events = _simulate_match_segment(
                db, seg, show, world, match_segments, total_segments,
                match_ratings, show_momentum, me, sl_svc, aftermath, log_event,
            )
            events.extend(seg_events)
        elif seg.segment_type == "promo":
            seg.is_completed = True
            promo_rating = _evaluate_promo_segment(db, seg, show)
            seg.rating = promo_rating
            # Good promos build show momentum
            if promo_rating >= 3.5:
                show_momentum = min(80, show_momentum + 4)
            elif promo_rating < 2.0:
                show_momentum = max(30, show_momentum - 3)

    # Calculate show overall rating
    show.is_completed = True
    card_bonus = _calculate_card_psychology_bonus(match_ratings)

    if match_ratings:
        show.overall_rating = round(
            sum(match_ratings) / len(match_ratings) + card_bonus, 1
        )
    else:
        show.overall_rating = round(2.5 * prestige_factor, 1)

    # --- Viewership model ---
    vs = _get_viewership_service()
    card_draw = vs.calculate_card_draw(db, show)

    # Attendance & gate revenue
    attendance, ticket_price, gate = vs.calculate_attendance(
        db, show, fed, card_draw,
    )
    show.attendance = attendance
    show.gate_revenue = gate

    # TV rating (weekly shows only)
    if show.show_type == "weekly" and fed:
        show.tv_rating = vs.calculate_tv_rating(db, show, fed)

    # PPV buys
    if fed:
        fed.weekly_revenue += gate
        if show.show_type == "ppv":
            ppv_buys = vs.calculate_ppv_buys(db, show, fed, card_draw)
            show.ppv_buys = ppv_buys
            fed.weekly_revenue += ppv_buys * 49.99

    # Dynamic prestige adjustment based on show performance
    if fed:
        vs.update_federation_fanbase(db, fed, show)

    # Update wrestler draw ratings for everyone on the card
    for seg in segments:
        if seg.segment_type == "match" and seg.match_id:
            participants = db.query(MatchParticipantDB).filter(
                MatchParticipantDB.match_id == seg.match_id
            ).all()
            for p in participants:
                new_draw = vs.calculate_wrestler_draw(db, p.wrestler_id)
                wrestler = db.query(GameWrestlerDB).filter(
                    GameWrestlerDB.id == p.wrestler_id
                ).first()
                if wrestler:
                    wrestler.draw_rating = round(new_draw, 1)

    # Generate news from show results
    try:
        news_svc = _get_news_service()
        news_svc.generate_show_news(db, show, match_ratings, fed)
    except Exception as e:
        logger.error("News generation failed for show %s: %s", show.id, e, exc_info=True)

    log_event(
        "show",
        f"{show.name} drew {attendance} fans, TV: {show.tv_rating} (Rating: {show.overall_rating})",
        [show.federation_id],
        importance=6,
    )
    events.append(f"Show completed: {show.name} ({attendance} attendance, TV: {show.tv_rating})")

    return {
        "attendance": attendance,
        "overall_rating": show.overall_rating,
        "events": events,
    }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _simulate_match_segment(
    db, seg, show, world, match_segments, total_segments,
    match_ratings, show_momentum, me, sl_svc, aftermath, log_event,
):
    """Simulate a single match segment. Returns (updated_momentum, events)."""
    events: List[str] = []
    match = db.query(MatchDB).filter(
        MatchDB.id == seg.match_id
    ).first()
    if not match or match.is_completed:
        return show_momentum, events

    # Determine card position from segment index
    match_idx = match_segments.index(seg)
    if match_idx == 0:
        card_position = "opener"
    elif match_idx == total_segments - 1:
        card_position = "main_event"
    elif match_idx == total_segments - 2 and total_segments > 2:
        card_position = "semifinal"
    else:
        card_position = "midcard"
    match.card_position = card_position
    match.game_date = show.game_date

    # Pass show momentum to match engine
    match._show_momentum = show_momentum

    try:
        result = me.simulate_match_from_db(db, match, game_date=show.game_date)
        seg.is_completed = True
        seg.rating = result.match_rating
        seg.crowd_reaction = "pop" if result.crowd_heat > 60 else "mixed"
        seg.actual_duration_minutes = result.duration_ticks
        match_ratings.append(result.match_rating)

        # Update show momentum from this match's crowd heat
        # Good matches lift the crowd, bad ones cool them
        if result.crowd_heat > 60:
            show_momentum = min(80, show_momentum + 5)
        elif result.crowd_heat < 35:
            show_momentum = max(30, show_momentum - 5)

        # Process post-match consequences
        aftermath.process_match_aftermath(
            db, match, world.current_game_date
        )

        # Character reactions — LLM-driven wrestlers react to match results
        if USE_LLM:
            try:
                from game_service.character_agent import character_react
                winner = db.query(GameWrestlerDB).filter(
                    GameWrestlerDB.id == result.winner_id
                ).first()
                if winner:
                    event_type = "title_win" if match.is_title_match else "win"
                    reaction = character_react(
                        db, winner.id, event_type,
                        f"Defeated opponent via {result.finish_type}. "
                        f"Match rating: {result.match_rating:.1f} stars.",
                    )
                    if reaction:
                        log_event(
                            "character_reaction", reaction,
                            [winner.id], importance=4,
                        )
            except Exception:
                pass  # Character reactions are optional

        # Process stable effects from match result
        try:
            stable_svc = _get_stable_service()
            losers = [p.wrestler_id for p in db.query(MatchParticipantDB).filter(
                MatchParticipantDB.match_id == match.id,
                MatchParticipantDB.is_winner == False,
            ).all()]
            for loser_id in losers:
                stable_svc.process_match_result_for_stables(
                    db, result.winner_id, loser_id,
                    world.id, world.current_game_date,
                )
        except (ValueError, AttributeError) as e:
            logger.debug("Stable match processing skipped: %s", e)

        # Log post-match angle if one occurred
        if result.post_match_angle:
            angle = result.post_match_angle
            log_event(
                angle["type"],
                angle["description"],
                angle.get("attacker_ids", []) + [angle.get("victim_id") or angle.get("saved_id", "")],
                importance=7,
            )
            show_momentum = min(85, show_momentum + 8)  # Angles are hot

        # Check for storyline triggers from match result
        sl_svc.check_match_storyline_triggers(
            db, match, world.current_game_date
        )
    except Exception as e:
        logger.error(
            "Match simulation failed for match %s: %s",
            match.id, e, exc_info=True,
        )
        seg.is_completed = True
        seg.rating = round(random.uniform(2.0, 4.0), 1)
        match_ratings.append(seg.rating)

    return show_momentum, events


def _evaluate_promo_segment(db: Session, seg: ShowSegmentDB, show: ShowDB) -> float:
    """Evaluate a promo segment rating using promo_service when a wrestler is identifiable."""
    from game_service.promo_service import _evaluate_promo_quality

    wrestler_id = None

    # Try to get wrestler from linked promo
    if seg.promo_id:
        promo = db.query(PromoDB).filter(PromoDB.id == seg.promo_id).first()
        if promo:
            # If the promo already has a quality rating, use it
            if promo.quality_rating is not None:
                return round(promo.quality_rating, 1)
            wrestler_id = promo.wrestler_id

    if wrestler_id:
        stats = db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == wrestler_id
        ).first()
        # Use a placeholder content string for template promos
        content = seg.description or "Generic promo segment"
        return _evaluate_promo_quality(stats, content, is_player=False)

    # No identifiable wrestler — fall back to random
    return round(random.uniform(2.0, 4.5), 1)


def _calculate_card_psychology_bonus(ratings: list) -> float:
    """Calculate show rating bonus based on card flow."""
    if len(ratings) < 2:
        return 0.0

    bonus = 0.0

    # Good opener bonus
    if ratings[0] > 3.0:
        bonus += 0.2

    # Main event is highest rated
    if ratings[-1] == max(ratings):
        bonus += 0.3

    # Build: ratings generally increase toward main event
    if len(ratings) >= 3:
        mid_avg = sum(ratings[1:-1]) / len(ratings[1:-1])
        if ratings[-1] > mid_avg > ratings[0]:
            bonus += 0.2

    # Monotony penalty: all ratings within 0.5 of each other
    if max(ratings) - min(ratings) < 0.5 and len(ratings) >= 3:
        bonus -= 0.2

    return round(bonus, 1)
