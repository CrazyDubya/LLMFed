"""
Viewership and fan engagement service for the wrestling simulator.

Replaces random.uniform() placeholders with a real model that derives
TV ratings, attendance, gate revenue, and PPV buys from federation prestige,
wrestler popularity, card quality, rivalries, and momentum.
"""

import logging
import random
from typing import List, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.game_models import (
    GameFederationDB,
    GameWrestlerDB,
    ShowDB,
    ShowSegmentDB,
    MatchDB,
    MatchParticipantDB,
    ChampionshipDB,
    WrestlerRelationshipDB,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Wrestler draw rating
# ---------------------------------------------------------------------------


def calculate_wrestler_draw(db: Session, wrestler_id: str) -> float:
    """Return a draw rating (0-100) representing how many fans a wrestler brings.

    Factors:
      - Base popularity
      - Active title holdings (+10 each)
      - Win streak bonus (capped at +10)
      - Loss streak penalty (capped at -15)
      - High rivalry heat bonus (+5)
    """
    wrestler = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.id == wrestler_id,
        )
        .first()
    )
    if wrestler is None:
        logger.warning("calculate_wrestler_draw: wrestler %s not found", wrestler_id)
        return 0.0

    draw = float(wrestler.popularity)

    # Title bonus: +10 per active championship held
    titles_held = (
        db.query(ChampionshipDB)
        .filter(
            ChampionshipDB.current_holder_id == wrestler_id,
            ChampionshipDB.is_active.is_(True),
        )
        .count()
    )
    draw += titles_held * 10

    # Win/loss streak
    streak = wrestler.win_streak or 0
    if streak > 0:
        draw += min(streak * 2, 10)
    elif streak < 0:
        draw += max(streak * 3, -15)  # streak is negative, so this subtracts

    # Rivalry heat bonus: +5 if any relationship has rivalry_heat > 50
    high_rivalry = (
        db.query(WrestlerRelationshipDB)
        .filter(
            or_(
                WrestlerRelationshipDB.wrestler1_id == wrestler_id,
                WrestlerRelationshipDB.wrestler2_id == wrestler_id,
            ),
            WrestlerRelationshipDB.rivalry_heat > 50,
        )
        .first()
    )
    if high_rivalry is not None:
        draw += 5

    draw = max(0.0, min(100.0, draw))
    return draw


# ---------------------------------------------------------------------------
# 2. Card drawing power
# ---------------------------------------------------------------------------


def calculate_card_draw(db: Session, show: ShowDB) -> float:
    """Return overall card drawing power on a 0-100 scale.

    - Main event (last match) wrestlers are weighted 2x.
    - Title matches apply a 1.3x multiplier on participant draw ratings.
    - A +5 bonus is added if any match features opponents with rivalry_heat > 30.
    """
    match_segments: List[ShowSegmentDB] = (
        db.query(ShowSegmentDB)
        .filter(
            ShowSegmentDB.show_id == show.id,
            ShowSegmentDB.segment_type == "match",
            ShowSegmentDB.match_id.isnot(None),
        )
        .order_by(ShowSegmentDB.position)
        .all()
    )

    if not match_segments:
        logger.debug("calculate_card_draw: no match segments for show %s", show.id)
        return 0.0

    last_segment = match_segments[-1]
    weighted_draws: List[float] = []
    rivalry_bonus = False

    for seg in match_segments:
        match = db.query(MatchDB).filter(MatchDB.id == seg.match_id).first()
        if match is None:
            continue

        participants = (
            db.query(MatchParticipantDB)
            .filter(MatchParticipantDB.match_id == match.id)
            .all()
        )

        is_main_event = seg.id == last_segment.id
        is_title = bool(match.is_title_match)
        weight = 2.0 if is_main_event else 1.0
        title_mult = 1.3 if is_title else 1.0

        participant_ids = [p.wrestler_id for p in participants]

        for p in participants:
            draw = calculate_wrestler_draw(db, p.wrestler_id)
            weighted_draws.append(draw * weight * title_mult)

        # Check rivalry heat between any pair of participants in this match
        if len(participant_ids) >= 2 and not rivalry_bonus:
            for i in range(len(participant_ids)):
                for j in range(i + 1, len(participant_ids)):
                    rel = (
                        db.query(WrestlerRelationshipDB)
                        .filter(
                            or_(
                                (
                                    WrestlerRelationshipDB.wrestler1_id
                                    == participant_ids[i]
                                )
                                & (
                                    WrestlerRelationshipDB.wrestler2_id
                                    == participant_ids[j]
                                ),
                                (
                                    WrestlerRelationshipDB.wrestler1_id
                                    == participant_ids[j]
                                )
                                & (
                                    WrestlerRelationshipDB.wrestler2_id
                                    == participant_ids[i]
                                ),
                            ),
                            WrestlerRelationshipDB.rivalry_heat > 30,
                        )
                        .first()
                    )
                    if rel is not None:
                        rivalry_bonus = True
                        break
                if rivalry_bonus:
                    break

    if not weighted_draws:
        return 0.0

    card_draw = sum(weighted_draws) / len(weighted_draws)
    if rivalry_bonus:
        card_draw += 5

    # Viral social media buzz bonus
    try:
        from game_service.social_media_service import get_viral_buzz_bonus

        all_wrestler_ids = []
        for seg in match_segments:
            match = db.query(MatchDB).filter(MatchDB.id == seg.match_id).first()
            if match:
                pids = [
                    p.wrestler_id
                    for p in db.query(MatchParticipantDB)
                    .filter(MatchParticipantDB.match_id == match.id)
                    .all()
                ]
                all_wrestler_ids.extend(pids)
        if all_wrestler_ids:
            buzz = get_viral_buzz_bonus(
                db, show.world_id, show.game_date, all_wrestler_ids
            )
            card_draw *= 1.0 + buzz
    except Exception:
        pass  # Social media system is optional

    return max(0.0, min(100.0, card_draw))


# ---------------------------------------------------------------------------
# 3. TV rating
# ---------------------------------------------------------------------------


def calculate_tv_rating(db: Session, show: ShowDB, fed: GameFederationDB) -> float:
    """Calculate a realistic TV rating (roughly 0.3 - 5.0+).

    Components:
      - Base from federation prestige
      - Card quality factor
      - Momentum factor (hot/cold streak)
      - Recent show quality trend (last 4 shows)
      - Small random variance
    """
    card_draw = calculate_card_draw(db, show)

    base = fed.prestige / 35.0
    card_factor = (card_draw / 100.0) * 0.6
    momentum_factor = ((fed.momentum - 50) / 100.0) * 0.5

    # Recent trend: average overall_rating of last 4 completed shows
    recent_shows = (
        db.query(ShowDB)
        .filter(
            ShowDB.federation_id == fed.id,
            ShowDB.is_completed.is_(True),
            ShowDB.overall_rating.isnot(None),
            ShowDB.id != show.id,
        )
        .order_by(ShowDB.game_date.desc())
        .limit(4)
        .all()
    )
    if recent_shows:
        avg_rating = sum(s.overall_rating for s in recent_shows) / len(recent_shows)
        recent_trend = (avg_rating / 5.0) * 0.3
    else:
        recent_trend = 0.15  # neutral default when no history

    variance = random.uniform(-0.1, 0.1)
    tv_rating = base + card_factor + momentum_factor + recent_trend + variance
    tv_rating = max(0.1, tv_rating)
    return round(tv_rating, 2)


# ---------------------------------------------------------------------------
# 4. Attendance, ticket price, gate revenue
# ---------------------------------------------------------------------------


def calculate_attendance(
    db: Session,
    show: ShowDB,
    fed: GameFederationDB,
    card_draw: float,
) -> Tuple[int, float, float]:
    """Return (attendance, ticket_price, gate_revenue).

    Fill rate is derived from prestige, card draw, momentum, and show type.
    Ticket price scales with demand and prestige; PPVs carry a premium.
    """
    base_fill = fed.prestige / 120.0
    card_bonus = card_draw / 400.0
    momentum_bonus = max(0.0, (fed.momentum - 50)) / 250.0
    event_bonus = 0.15 if show.show_type == "ppv" else 0.0
    noise = random.uniform(-0.05, 0.05)

    fill_rate = base_fill + card_bonus + momentum_bonus + event_bonus + noise
    fill_rate = min(1.0, max(0.15, fill_rate))

    capacity = show.capacity or 5000
    attendance = int(capacity * fill_rate)

    # Ticket pricing
    base_ticket = 15.0 + (fed.prestige / 100.0) * 60.0
    demand_multiplier = 0.8 + fill_rate * 0.4
    ppv_premium = 1.5 if show.show_type == "ppv" else 1.0
    ticket_price = round(base_ticket * demand_multiplier * ppv_premium, 2)

    gate_revenue = round(attendance * ticket_price, 2)
    return attendance, ticket_price, gate_revenue


# ---------------------------------------------------------------------------
# 5. PPV buys
# ---------------------------------------------------------------------------


def calculate_ppv_buys(
    db: Session,
    show: ShowDB,
    fed: GameFederationDB,
    card_draw: float,
) -> int:
    """Estimate PPV buy count based on brand strength, card quality, momentum,
    and main-event rivalry heat."""
    base = fed.prestige * 1500
    card_mult = 0.5 + (card_draw / 100.0) * 1.0
    momentum_mult = 0.7 + (fed.momentum / 100.0) * 0.6

    # Main-event rivalry heat bonus
    main_event_heat_bonus = 1.0
    last_match_seg = (
        db.query(ShowSegmentDB)
        .filter(
            ShowSegmentDB.show_id == show.id,
            ShowSegmentDB.segment_type == "match",
            ShowSegmentDB.match_id.isnot(None),
        )
        .order_by(ShowSegmentDB.position.desc())
        .first()
    )
    if last_match_seg is not None:
        participants = (
            db.query(MatchParticipantDB)
            .filter(MatchParticipantDB.match_id == last_match_seg.match_id)
            .all()
        )
        wrestler_ids = [p.wrestler_id for p in participants]
        max_heat = 0
        for i in range(len(wrestler_ids)):
            for j in range(i + 1, len(wrestler_ids)):
                rel = (
                    db.query(WrestlerRelationshipDB)
                    .filter(
                        or_(
                            (WrestlerRelationshipDB.wrestler1_id == wrestler_ids[i])
                            & (WrestlerRelationshipDB.wrestler2_id == wrestler_ids[j]),
                            (WrestlerRelationshipDB.wrestler1_id == wrestler_ids[j])
                            & (WrestlerRelationshipDB.wrestler2_id == wrestler_ids[i]),
                        ),
                    )
                    .first()
                )
                if rel is not None and rel.rivalry_heat > max_heat:
                    max_heat = rel.rivalry_heat

        if max_heat > 60:
            main_event_heat_bonus = 1.2
        elif max_heat > 30:
            main_event_heat_bonus = 1.1

    buys = int(base * card_mult * momentum_mult * main_event_heat_bonus)
    buys += random.randint(-5000, 5000)
    return max(1000, buys)


# ---------------------------------------------------------------------------
# 6. Post-show federation fanbase update
# ---------------------------------------------------------------------------


def update_federation_fanbase(db: Session, fed: GameFederationDB, show: ShowDB) -> None:
    """Adjust federation prestige based on show performance.

    Called after every completed show to make prestige dynamic.
    """
    prestige_delta = 0.0
    capacity = show.capacity or 1

    # Great show with strong attendance
    if (show.overall_rating or 0) >= 4.0 and (show.attendance or 0) > capacity * 0.8:
        prestige_delta += 1
        logger.info(
            "Fed %s gains +1 prestige: strong show (%.1f stars, %d/%d attendance)",
            fed.short_name or fed.name,
            show.overall_rating,
            show.attendance,
            capacity,
        )

    # Poor show
    if (show.overall_rating or 0) < 2.0:
        prestige_delta -= 1
        logger.info(
            "Fed %s loses -1 prestige: weak show (%.1f stars)",
            fed.short_name or fed.name,
            show.overall_rating,
        )

    # TV rating vs recent average
    if show.tv_rating is not None:
        recent_shows = (
            db.query(ShowDB)
            .filter(
                ShowDB.federation_id == fed.id,
                ShowDB.is_completed.is_(True),
                ShowDB.tv_rating.isnot(None),
                ShowDB.id != show.id,
            )
            .order_by(ShowDB.game_date.desc())
            .limit(4)
            .all()
        )
        if recent_shows:
            avg_tv = sum(s.tv_rating for s in recent_shows) / len(recent_shows)
            if show.tv_rating > avg_tv:
                prestige_delta += 0.5
                logger.info(
                    "Fed %s gains +0.5 prestige: TV rating %.2f above avg %.2f",
                    fed.short_name or fed.name,
                    show.tv_rating,
                    avg_tv,
                )

    if prestige_delta != 0:
        new_prestige = int(round(max(1, min(100, fed.prestige + prestige_delta))))
        if new_prestige != fed.prestige:
            logger.info(
                "Fed %s prestige: %d -> %d",
                fed.short_name or fed.name,
                fed.prestige,
                new_prestige,
            )
            fed.prestige = new_prestige
            db.add(fed)
