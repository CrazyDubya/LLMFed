"""
Show booking service - promoters build match cards for shows.

A promoter can:
 - Create a show on a future game date
 - Add match segments (pick competitors, stipulation, title on the line)
 - Add promo/backstage segments
 - Reorder the card
 - NPC federations auto-book via _npc_book_card()
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    ShowDB, ShowSegmentDB, MatchDB, MatchParticipantDB,
    GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ContractDB, ChampionshipDB, TagTeamDB,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Show management
# ---------------------------------------------------------------------------

def create_show(db: Session, world_id: str, federation_id: str,
                name: str, show_type: str = "weekly",
                venue: str = "Arena", capacity: int = 5000,
                game_date: str = None) -> ShowDB:
    """Create a new show for a federation."""
    show = ShowDB(
        world_id=world_id,
        federation_id=federation_id,
        name=name,
        show_type=show_type,
        venue=venue,
        capacity=capacity,
        game_date=game_date or "2026-01-01",
    )
    db.add(show)
    db.flush()
    return show


# ---------------------------------------------------------------------------
# Match booking
# ---------------------------------------------------------------------------

def book_match(db: Session, show_id: str, world_id: str,
               wrestler_ids: list, match_type: str = "singles",
               stipulation: str = None, is_title_match: bool = False,
               championship_id: str = None,
               planned_winner_id: str = None,
               planned_finish: str = "pinfall",
               position: int = None) -> ShowSegmentDB:
    """Book a match segment on a show."""
    show = db.query(ShowDB).filter(ShowDB.id == show_id).first()
    if not show:
        raise ValueError("Show not found")

    # Create match
    match = MatchDB(
        world_id=world_id,
        match_type=match_type,
        stipulation=stipulation,
        is_title_match=is_title_match,
        championship_id=championship_id,
        winner_id=planned_winner_id,
        finish_type=planned_finish,
    )
    db.add(match)
    db.flush()

    # Add participants
    for i, wid in enumerate(wrestler_ids):
        db.add(MatchParticipantDB(
            match_id=match.id,
            wrestler_id=wid,
            role="competitor",
            team=i if match_type in ("tag_team",) else None,
        ))

    # Determine position
    if position is None:
        existing = db.query(ShowSegmentDB).filter(
            ShowSegmentDB.show_id == show_id
        ).count()
        position = existing + 1

    segment = ShowSegmentDB(
        show_id=show_id,
        position=position,
        segment_type="match",
        match_id=match.id,
        planned_duration_minutes=15 if match_type == "singles" else 20,
    )
    db.add(segment)
    db.flush()
    return segment


def book_promo_segment(db: Session, show_id: str,
                       description: str = "Promo segment",
                       position: int = None) -> ShowSegmentDB:
    """Book a non-match segment (promo, backstage, angle)."""
    if position is None:
        existing = db.query(ShowSegmentDB).filter(
            ShowSegmentDB.show_id == show_id
        ).count()
        position = existing + 1

    segment = ShowSegmentDB(
        show_id=show_id,
        position=position,
        segment_type="promo",
        description=description,
        planned_duration_minutes=10,
    )
    db.add(segment)
    db.flush()
    return segment


def reorder_card(db: Session, show_id: str, segment_order: list):
    """Reorder segments on a show card.

    segment_order: list of segment IDs in desired order.
    """
    for i, seg_id in enumerate(segment_order):
        seg = db.query(ShowSegmentDB).filter(
            ShowSegmentDB.id == seg_id,
            ShowSegmentDB.show_id == show_id,
        ).first()
        if seg:
            seg.position = i + 1


def get_show_card(db: Session, show_id: str) -> list:
    """Get all segments for a show in order."""
    return db.query(ShowSegmentDB).filter(
        ShowSegmentDB.show_id == show_id,
    ).order_by(ShowSegmentDB.position).all()


# ---------------------------------------------------------------------------
# NPC auto-booking
# ---------------------------------------------------------------------------

CARD_POSITIONS = ["opener", "midcard", "midcard", "semifinal", "main_event"]


def _sort_roster_by_style(db: Session, wrestlers: list, booking_style: str) -> list:
    """Sort wrestlers for card placement based on federation booking style."""
    if booking_style == "workrate":
        # Prioritize technical skill and psychology
        def score(w):
            stats = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w.id).first()
            if not stats:
                return 50
            return stats.technical + stats.psychology + stats.selling
        return sorted(wrestlers, key=score, reverse=True)
    elif booking_style == "entertainment":
        # Prioritize charisma and popularity
        def score(w):
            stats = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w.id).first()
            charisma = stats.charisma if stats else 50
            return charisma + w.popularity
        return sorted(wrestlers, key=score, reverse=True)
    elif booking_style == "hardcore":
        # Prioritize brawlers and toughness
        def score(w):
            stats = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w.id).first()
            if not stats:
                return 50
            return stats.brawling + stats.toughness + stats.power
        return sorted(wrestlers, key=score, reverse=True)
    else:
        # Default/storyline: prioritize popular wrestlers for main event
        return sorted(wrestlers, key=lambda w: w.popularity, reverse=True)


def npc_book_card(db: Session, show: ShowDB) -> list:
    """Auto-generate a match card for an NPC federation show.

    Uses federation's booking style (ai_personality) to influence card composition.
    Returns list of created segments.
    """
    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == show.federation_id
    ).first()
    if not fed:
        return []

    # Get booking style from federation personality
    personality = getattr(fed, 'ai_personality', None) or {}
    booking_style = personality.get("booking_style", "default") if isinstance(personality, dict) else "default"

    # Get roster
    contracts = db.query(ContractDB).filter(
        ContractDB.federation_id == fed.id,
        ContractDB.status == "active",
    ).all()
    wrestler_ids = [c.wrestler_id for c in contracts]

    if len(wrestler_ids) < 2:
        return []

    # Get active, non-injured wrestlers
    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id.in_(wrestler_ids),
        GameWrestlerDB.is_active == True,
        GameWrestlerDB.is_injured == False,
    ).all()

    if len(wrestlers) < 2:
        return []

    # Sort by booking style for card placement (best wrestlers in main event)
    wrestlers = _sort_roster_by_style(db, wrestlers, booking_style)

    # Championships for potential title matches
    championships = db.query(ChampionshipDB).filter(
        ChampionshipDB.federation_id == fed.id,
        ChampionshipDB.is_active == True,
    ).all()

    segments = []
    used = set()

    # Check for tag teams — book a tag match if available (30% chance)
    tag_teams = db.query(TagTeamDB).filter(
        TagTeamDB.world_id == show.world_id,
        TagTeamDB.is_active == True,
        TagTeamDB.wrestler1_id.in_(wrestler_ids),
        TagTeamDB.wrestler2_id.in_(wrestler_ids),
    ).all()

    booked_tag = False
    if len(tag_teams) >= 2 and random.random() < 0.30:
        t1, t2 = random.sample(tag_teams, 2)
        tag_wrestlers = [t1.wrestler1_id, t1.wrestler2_id, t2.wrestler1_id, t2.wrestler2_id]
        # Ensure no overlap
        if len(set(tag_wrestlers)) == 4:
            # Winner is the team with higher combined chemistry + popularity
            t1_score = t1.team_chemistry + random.randint(-10, 10)
            t2_score = t2.team_chemistry + random.randint(-10, 10)
            if t1_score >= t2_score:
                planned_winner = t1.wrestler1_id  # One of the winning team
            else:
                planned_winner = t2.wrestler1_id

            seg = book_match(
                db, show.id, show.world_id,
                wrestler_ids=tag_wrestlers,
                match_type="tag_team",
                planned_winner_id=planned_winner,
                planned_finish="pinfall",
                position=2,  # Midcard
            )
            segments.append(seg)
            for wid in tag_wrestlers:
                used.add(wid)
            booked_tag = True

    num_matches = min(len(wrestlers) // 2, len(CARD_POSITIONS))
    if booked_tag:
        num_matches = max(1, num_matches - 1)  # Already booked one

    # Book singles matches — reverse order so best wrestlers get main event
    match_wrestlers = [w for w in wrestlers if w.id not in used]
    # Put lower-ranked first (they'll be openers), higher-ranked last (main event)
    match_wrestlers.reverse()

    for i in range(num_matches):
        available = [w for w in match_wrestlers if w.id not in used]
        if len(available) < 2:
            break

        w1, w2 = available[0], available[1]
        used.add(w1.id)
        used.add(w2.id)

        # Determine winner
        w1_score = w1.popularity + random.randint(-20, 20)
        w2_score = w2.popularity + random.randint(-20, 20)
        planned_winner = w1 if w1_score >= w2_score else w2

        # Title match for main event if champion is available
        is_title = False
        champ_id = None
        actual_pos = i + (1 if booked_tag else 0)
        if actual_pos == num_matches + (1 if booked_tag else 0) - 1 and championships:
            champ = championships[0]
            if champ.current_holder_id in (w1.id, w2.id):
                is_title = True
                champ_id = champ.id

        # Hardcore booking style adds stipulations
        stipulation = None
        if booking_style == "hardcore" and random.random() < 0.4:
            stipulation = random.choice([
                "No DQ", "Falls Count Anywhere", "Street Fight", "Extreme Rules"
            ])

        finish = random.choice(["pinfall", "pinfall", "pinfall", "submission"])
        position = actual_pos + 1

        seg = book_match(
            db, show.id, show.world_id,
            wrestler_ids=[w1.id, w2.id],
            match_type="singles",
            stipulation=stipulation,
            is_title_match=is_title,
            championship_id=champ_id,
            planned_winner_id=planned_winner.id,
            planned_finish=finish,
            position=position,
        )
        segments.append(seg)

    # Add a promo segment between matches
    total_segs = len(segments)
    if total_segs >= 3:
        promo_pos = total_segs // 2 + 1
        available = [w for w in wrestlers if w.id not in used]
        promo_wrestler = available[0].name if available else "a mystery guest"
        book_promo_segment(
            db, show.id,
            description=f"{promo_wrestler} addresses the crowd",
            position=promo_pos,
        )

    db.flush()
    return segments
