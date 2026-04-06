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
    ContractDB, ChampionshipDB, TagTeamDB, PromoDB,
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
                       position: int = None,
                       wrestler_id: str = None,
                       target_wrestler_id: str = None,
                       world_id: str = None,
                       game_date: str = None) -> ShowSegmentDB:
    """Book a promo segment, creating a PromoDB record when a wrestler is identified."""
    if position is None:
        existing = db.query(ShowSegmentDB).filter(
            ShowSegmentDB.show_id == show_id
        ).count()
        position = existing + 1

    promo_id = None
    if wrestler_id:
        # Resolve world_id from show if not provided
        if not world_id:
            show = db.query(ShowDB).filter(ShowDB.id == show_id).first()
            if show:
                world_id = show.world_id
        promo = PromoDB(
            world_id=world_id,
            wrestler_id=wrestler_id,
            target_wrestler_id=target_wrestler_id,
            content=description,
            promo_type="in_ring",
            game_date=game_date,
        )
        db.add(promo)
        db.flush()
        promo_id = promo.id

    segment = ShowSegmentDB(
        show_id=show_id,
        position=position,
        segment_type="promo",
        promo_id=promo_id,
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
PUSH_TIERS = ["main_event", "upper_midcard", "midcard", "lower_card", "jobber"]


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


def npc_book_card(db: Session, show: ShowDB, ppv_event=None, next_ppv=None) -> list:
    """Auto-generate a match card for an NPC federation show.

    Uses federation's booking style (ai_personality) to influence card composition.
    When ppv_event is provided, books the PPV's planned card.
    When next_ppv is provided, weekly TV builds toward it.
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

    # Load push tiers for vision-aware booking
    from models.game_models import WrestlerPushDB
    push_map = {}
    pushes = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == fed.id,
    ).all()
    for p in pushes:
        push_map[p.wrestler_id] = p

    # If this is a PPV with planned matches, book those first
    if ppv_event and (ppv_event.planned_main_event or ppv_event.planned_matches):
        return _book_ppv_card(db, show, fed, ppv_event, wrestlers, championships, push_map, booking_style)

    segments = []
    used = set()

    # Storyline-aware booking: feuding wrestlers should face each other
    from models.game_models import StorylineDB, StorylineParticipantDB
    active_storylines = db.query(StorylineDB).filter(
        StorylineDB.federation_id == fed.id,
        StorylineDB.status.in_(["active", "climax"]),
    ).order_by(StorylineDB.heat.desc()).all()

    storyline_matches_booked = 0
    for sl in active_storylines:
        if storyline_matches_booked >= 2:
            break  # Max 2 storyline matches per weekly show
        parts = db.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.storyline_id == sl.id,
        ).all()
        sl_wrestler_ids = [p.wrestler_id for p in parts]
        # Find available pairs from the storyline
        available = [wid for wid in sl_wrestler_ids
                     if wid in wrestler_ids and wid not in used]
        if len(available) >= 2:
            w1_id, w2_id = available[0], available[1]
            w1 = next((w for w in wrestlers if w.id == w1_id), None)
            w2 = next((w for w in wrestlers if w.id == w2_id), None)
            if w1 and w2 and not w1.is_injured and not w2.is_injured:
                # Higher-heat storyline gets higher card position
                is_main = (storyline_matches_booked == 0 and sl.heat >= 70)
                w1_push = push_map.get(w1.id)
                w2_push = push_map.get(w2.id)
                w1_rank = PUSH_TIERS.index(w1_push.push_tier) if w1_push and w1_push.push_tier in PUSH_TIERS else 2
                w2_rank = PUSH_TIERS.index(w2_push.push_tier) if w2_push and w2_push.push_tier in PUSH_TIERS else 2
                planned_winner = w1 if w1_rank <= w2_rank else w2
                # Climax storylines get gimmick finishes
                finish = "pinfall"
                stipulation = None
                if sl.status == "climax" and random.random() < 0.4:
                    stipulation = random.choice(["No DQ", "Steel Cage", "Last Man Standing"])

                seg = book_match(
                    db, show.id, show.world_id,
                    wrestler_ids=[w1.id, w2.id],
                    match_type="singles",
                    stipulation=stipulation,
                    planned_winner_id=planned_winner.id,
                    planned_finish=finish,
                )
                segments.append(seg)
                used.add(w1.id)
                used.add(w2.id)
                storyline_matches_booked += 1

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

        # Determine winner (push-tier aware)
        w1_push = push_map.get(w1.id)
        w2_push = push_map.get(w2.id)
        w1_tier_rank = PUSH_TIERS.index(w1_push.push_tier) if w1_push and w1_push.push_tier in PUSH_TIERS else 2
        w2_tier_rank = PUSH_TIERS.index(w2_push.push_tier) if w2_push and w2_push.push_tier in PUSH_TIERS else 2
        # Lower index = higher tier. Higher-tier wrestlers should usually win.
        w1_score = (5 - w1_tier_rank) * 20 + w1.popularity + random.randint(-15, 15)
        w2_score = (5 - w2_tier_rank) * 20 + w2.popularity + random.randint(-15, 15)
        # Protected wrestlers get a big boost
        if w1_push and w1_push.protected:
            w1_score += 30
        if w2_push and w2_push.protected:
            w2_score += 30
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

        finish = random.choices(
            ["pinfall", "submission", "count_out", "disqualification"],
            weights=[60, 15, 10, 15],
            k=1,
        )[0]
        # Title matches almost always end clean
        if is_title and finish in ("count_out", "disqualification"):
            finish = "pinfall"
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
        if available:
            promo_wrestler = available[0]
            book_promo_segment(
                db, show.id,
                description=f"{promo_wrestler.name} addresses the crowd",
                position=promo_pos,
                wrestler_id=promo_wrestler.id,
                world_id=show.world_id,
                game_date=show.game_date,
            )
        else:
            # Fallback: pick the most popular wrestler on the card
            card_wrestlers = sorted(wrestlers, key=lambda w: w.popularity, reverse=True)
            if card_wrestlers:
                promo_wrestler = card_wrestlers[0]
                book_promo_segment(
                    db, show.id,
                    description=f"{promo_wrestler.name} addresses the crowd",
                    position=promo_pos,
                    wrestler_id=promo_wrestler.id,
                    world_id=show.world_id,
                    game_date=show.game_date,
                )

    db.flush()
    return segments


def _book_ppv_card(db, show, fed, ppv_event, wrestlers, championships, push_map, booking_style):
    """Book a PPV card from the PPV event's planned matches.

    Uses planned_main_event and planned_matches from the PPV calendar,
    falling back to the regular booking logic for unplanned slots.
    """
    segments = []
    used = set()
    wrestler_map = {w.id: w for w in wrestlers}
    position = 1

    # Book planned undercard matches first
    for planned in (ppv_event.planned_matches or []):
        wids = planned.get("wrestler_ids", [])
        available = [wid for wid in wids if wid in wrestler_map and wid not in used
                     and not wrestler_map[wid].is_injured]
        if len(available) < 2:
            continue

        w1, w2 = wrestler_map[available[0]], wrestler_map[available[1]]
        used.update(available[:2])

        # Winner: higher push tier wins (PPV wins matter more)
        w1_push = push_map.get(w1.id)
        w2_push = push_map.get(w2.id)
        w1_rank = PUSH_TIERS.index(w1_push.push_tier) if w1_push and w1_push.push_tier in PUSH_TIERS else 2
        w2_rank = PUSH_TIERS.index(w2_push.push_tier) if w2_push and w2_push.push_tier in PUSH_TIERS else 2
        planned_winner = w1 if w1_rank <= w2_rank else w2

        seg = book_match(
            db, show.id, show.world_id,
            wrestler_ids=[w1.id, w2.id],
            match_type=planned.get("match_type", "singles"),
            is_title_match=bool(planned.get("title_id")),
            championship_id=planned.get("title_id"),
            planned_winner_id=planned_winner.id,
            planned_finish="pinfall",
            position=position,
        )
        segments.append(seg)
        position += 1

    # Book the main event last (highest position)
    main_event = ppv_event.planned_main_event or {}
    me_wids = main_event.get("wrestler_ids", [])
    me_available = [wid for wid in me_wids if wid in wrestler_map and wid not in used
                    and not wrestler_map[wid].is_injured]

    if len(me_available) >= 2:
        w1, w2 = wrestler_map[me_available[0]], wrestler_map[me_available[1]]
        used.update(me_available[:2])

        # Main event: champion usually retains at non-crown-jewel, 40% title change at crown jewel
        title_id = main_event.get("title_id")
        champ = None
        if title_id:
            champ = db.query(ChampionshipDB).filter(ChampionshipDB.id == title_id).first()

        if champ and champ.current_holder_id in (w1.id, w2.id):
            holder = w1 if w1.id == champ.current_holder_id else w2
            challenger = w2 if holder == w1 else w1
            if ppv_event.is_crown_jewel and random.random() < 0.40:
                planned_winner = challenger  # Crown jewel title change!
            elif random.random() < 0.25:
                planned_winner = challenger  # Regular PPV title change
            else:
                planned_winner = holder  # Champion retains
        else:
            # Non-title main event
            w1_push = push_map.get(w1.id)
            w2_push = push_map.get(w2.id)
            w1_rank = PUSH_TIERS.index(w1_push.push_tier) if w1_push and w1_push.push_tier in PUSH_TIERS else 2
            w2_rank = PUSH_TIERS.index(w2_push.push_tier) if w2_push and w2_push.push_tier in PUSH_TIERS else 2
            planned_winner = w1 if w1_rank <= w2_rank else w2

        seg = book_match(
            db, show.id, show.world_id,
            wrestler_ids=[w1.id, w2.id],
            match_type="singles",
            is_title_match=bool(title_id),
            championship_id=title_id,
            planned_winner_id=planned_winner.id,
            planned_finish="pinfall",
            position=position,
        )
        segments.append(seg)
        position += 1

    # Fill remaining slots with available wrestlers
    remaining = [w for w in wrestlers if w.id not in used]
    for i in range(0, min(len(remaining) - 1, 4), 2):
        w1, w2 = remaining[i], remaining[i + 1]
        used.add(w1.id)
        used.add(w2.id)
        w1_score = w1.popularity + random.randint(-20, 20)
        w2_score = w2.popularity + random.randint(-20, 20)
        planned_winner = w1 if w1_score >= w2_score else w2

        seg = book_match(
            db, show.id, show.world_id,
            wrestler_ids=[w1.id, w2.id],
            match_type="singles",
            planned_winner_id=planned_winner.id,
            planned_finish="pinfall",
            position=position,
        )
        segments.append(seg)
        position += 1

    # Opening promo for PPV
    if wrestlers:
        top = sorted(wrestlers, key=lambda w: w.popularity, reverse=True)[0]
        book_promo_segment(
            db, show.id,
            description=f"{top.name} opens {ppv_event.name} with a championship address",
            position=0,
            wrestler_id=top.id,
            world_id=show.world_id,
            game_date=show.game_date,
        )

    db.flush()
    return segments
