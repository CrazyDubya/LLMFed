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
    ShowDB,
    ShowSegmentDB,
    MatchDB,
    MatchParticipantDB,
    GameFederationDB,
    GameWrestlerDB,
    WrestlerStatsDB,
    ContractDB,
    ChampionshipDB,
    TagTeamDB,
    PromoDB,
    WorldDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Booking constants
# ---------------------------------------------------------------------------

MAX_STORYLINE_MATCHES_PER_SHOW = 2
TAG_TEAM_BOOKING_RATE = 0.30
CLIMAX_GIMMICK_RATE = 0.50
TRIPLE_THREAT_RATE = 0.15
HARDCORE_STIPULATION_RATE = 0.40
CROWN_JEWEL_TITLE_CHANGE_RATE = 0.40
REGULAR_PPV_TITLE_CHANGE_RATE = 0.25
FATAL_FOUR_WAY_RATE = 0.60
PLAYER_MATCH_WIN_RATE = 0.50
DARK_MATCH_WIN_RATE = 0.55
PROTECTION_BONUS = 30
FINISH_TYPE_WEIGHTS = [60, 15, 10, 15]  # pinfall, submission, count_out, DQ
FINISH_TYPES = ["pinfall", "submission", "count_out", "disqualification"]

# Data-driven gimmick match configuration
GIMMICK_MATCH_CONFIG = {
    "Steel Cage": {"match_type": "cage", "finish": "pinfall"},
    "Ladder": {"match_type": "ladder", "finish": "stipulation"},
    "Tables": {"match_type": "tables", "finish": "stipulation"},
    "Hell in a Cell": {"match_type": "hell_in_a_cell", "finish": "pinfall"},
    "No DQ": {"match_type": "singles", "finish": "pinfall"},
    "Last Man Standing": {"match_type": "singles", "finish": "pinfall"},
    "Iron Man": {"match_type": "iron_man", "finish": "pinfall"},
}


def _get_next_segment_position(db: Session, show_id: str) -> int:
    """Get the next available segment position for a show."""
    return db.query(ShowSegmentDB).filter(ShowSegmentDB.show_id == show_id).count() + 1


def _calculate_wrestler_score(wrestler, push_map, push_tiers, randomness=15):
    """Calculate a wrestler's booking score from push tier and popularity."""
    push = push_map.get(wrestler.id)
    tier_rank = (
        push_tiers.index(push.push_tier) if push and push.push_tier in push_tiers else 2
    )
    score = (
        (5 - tier_rank) * 20
        + wrestler.popularity
        + random.randint(-randomness, randomness)
    )
    if push and push.protected:
        score += PROTECTION_BONUS
    return score


def _get_available_wrestlers(db: Session, wrestler_ids: list):
    """Get active, non-injured wrestlers from a list of IDs."""
    return (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.id.in_(wrestler_ids),
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.is_injured == False,
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Show management
# ---------------------------------------------------------------------------


def create_show(
    db: Session,
    world_id: str,
    federation_id: str,
    name: str,
    show_type: str = "weekly",
    venue: str = "Arena",
    capacity: int = 5000,
    game_date: str = None,
) -> ShowDB:
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


def book_match(
    db: Session,
    show_id: str,
    world_id: str,
    wrestler_ids: list,
    match_type: str = "singles",
    stipulation: str = None,
    is_title_match: bool = False,
    championship_id: str = None,
    planned_winner_id: str = None,
    planned_finish: str = "pinfall",
    position: int = None,
) -> ShowSegmentDB:
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
        db.add(
            MatchParticipantDB(
                match_id=match.id,
                wrestler_id=wid,
                role="competitor",
                team=i if match_type in ("tag_team",) else None,
            )
        )

    # Determine position
    if position is None:
        position = _get_next_segment_position(db, show_id)

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


def book_promo_segment(
    db: Session,
    show_id: str,
    description: str = "Promo segment",
    position: int = None,
    wrestler_id: str = None,
    target_wrestler_id: str = None,
    world_id: str = None,
    game_date: str = None,
) -> ShowSegmentDB:
    """Book a promo segment, creating a PromoDB record when a wrestler is identified."""
    if position is None:
        position = _get_next_segment_position(db, show_id)

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
        seg = (
            db.query(ShowSegmentDB)
            .filter(
                ShowSegmentDB.id == seg_id,
                ShowSegmentDB.show_id == show_id,
            )
            .first()
        )
        if seg:
            seg.position = i + 1


def get_show_card(db: Session, show_id: str) -> list:
    """Get all segments for a show in order."""
    return (
        db.query(ShowSegmentDB)
        .filter(
            ShowSegmentDB.show_id == show_id,
        )
        .order_by(ShowSegmentDB.position)
        .all()
    )


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
            stats = (
                db.query(WrestlerStatsDB)
                .filter(WrestlerStatsDB.wrestler_id == w.id)
                .first()
            )
            if not stats:
                return 50
            return stats.technical + stats.psychology + stats.selling

        return sorted(wrestlers, key=score, reverse=True)
    elif booking_style == "entertainment":
        # Prioritize charisma and popularity
        def score(w):
            stats = (
                db.query(WrestlerStatsDB)
                .filter(WrestlerStatsDB.wrestler_id == w.id)
                .first()
            )
            charisma = stats.charisma if stats else 50
            return charisma + w.popularity

        return sorted(wrestlers, key=score, reverse=True)
    elif booking_style == "hardcore":
        # Prioritize brawlers and toughness
        def score(w):
            stats = (
                db.query(WrestlerStatsDB)
                .filter(WrestlerStatsDB.wrestler_id == w.id)
                .first()
            )
            if not stats:
                return 50
            return stats.brawling + stats.toughness + stats.power

        return sorted(wrestlers, key=score, reverse=True)
    else:
        # Default/storyline: prioritize popular wrestlers for main event
        return sorted(wrestlers, key=lambda w: w.popularity, reverse=True)


def npc_book_card(db: Session, show: ShowDB, ppv_event=None, **_kwargs) -> list:
    """Auto-generate a match card for an NPC federation show.

    Uses federation's booking style (ai_personality) to influence card composition.
    When ppv_event is provided, books the PPV's planned card.
    When next_ppv is provided, weekly TV builds toward it.
    Returns list of created segments.
    """
    fed = (
        db.query(GameFederationDB)
        .filter(GameFederationDB.id == show.federation_id)
        .first()
    )
    if not fed:
        return []

    # Get booking style from federation personality
    personality = getattr(fed, "ai_personality", None) or {}
    booking_style = (
        personality.get("booking_style", "default")
        if isinstance(personality, dict)
        else "default"
    )

    # Get roster
    contracts = (
        db.query(ContractDB)
        .filter(
            ContractDB.federation_id == fed.id,
            ContractDB.status == "active",
        )
        .all()
    )
    wrestler_ids = [c.wrestler_id for c in contracts]

    if len(wrestler_ids) < 2:
        return []

    # Get active, non-injured wrestlers
    wrestlers = _get_available_wrestlers(db, wrestler_ids)

    if len(wrestlers) < 2:
        return []

    # Sort by booking style for card placement (best wrestlers in main event)
    wrestlers = _sort_roster_by_style(db, wrestlers, booking_style)

    # Championships for potential title matches
    championships = (
        db.query(ChampionshipDB)
        .filter(
            ChampionshipDB.federation_id == fed.id,
            ChampionshipDB.is_active == True,
        )
        .all()
    )

    # Load push tiers for vision-aware booking
    from models.game_models import WrestlerPushDB

    push_map = {}
    pushes = (
        db.query(WrestlerPushDB)
        .filter(
            WrestlerPushDB.federation_id == fed.id,
        )
        .all()
    )
    for p in pushes:
        push_map[p.wrestler_id] = p

    # If this is a PPV with planned matches, book those first
    if ppv_event and (ppv_event.planned_main_event or ppv_event.planned_matches):
        return _book_ppv_card(
            db, show, fed, ppv_event, wrestlers, championships, push_map, booking_style
        )

    segments = []
    used = set()

    # Storyline-aware booking: feuding wrestlers should face each other
    from models.game_models import StorylineDB, StorylineParticipantDB

    active_storylines = (
        db.query(StorylineDB)
        .filter(
            StorylineDB.federation_id == fed.id,
            StorylineDB.status.in_(["active", "climax"]),
        )
        .order_by(StorylineDB.heat.desc())
        .all()
    )

    storyline_matches_booked = 0
    for sl in active_storylines:
        if storyline_matches_booked >= MAX_STORYLINE_MATCHES_PER_SHOW:
            break  # Max 2 storyline matches per weekly show
        parts = (
            db.query(StorylineParticipantDB)
            .filter(
                StorylineParticipantDB.storyline_id == sl.id,
            )
            .all()
        )
        sl_wrestler_ids = [p.wrestler_id for p in parts]
        # Find available pairs from the storyline
        available = [
            wid for wid in sl_wrestler_ids if wid in wrestler_ids and wid not in used
        ]
        if len(available) >= 2:
            w1_id, w2_id = available[0], available[1]
            w1 = next((w for w in wrestlers if w.id == w1_id), None)
            w2 = next((w for w in wrestlers if w.id == w2_id), None)
            if w1 and w2 and not w1.is_injured and not w2.is_injured:
                # Higher-heat storyline gets higher card position
                is_main = storyline_matches_booked == 0 and sl.heat >= 70
                planned_winner = (
                    w1
                    if _calculate_wrestler_score(w1, push_map, PUSH_TIERS)
                    >= _calculate_wrestler_score(w2, push_map, PUSH_TIERS)
                    else w2
                )
                # Climax storylines get gimmick finishes — more variety
                finish = "pinfall"
                stipulation = None
                match_type = "singles"
                if sl.status == "climax" and random.random() < CLIMAX_GIMMICK_RATE:
                    gimmick_choice = random.choices(
                        list(GIMMICK_MATCH_CONFIG.keys()),
                        weights=[20, 15, 15, 10, 20, 15, 5],
                        k=1,
                    )[0]
                    stipulation = gimmick_choice
                    config = GIMMICK_MATCH_CONFIG[gimmick_choice]
                    match_type = config["match_type"]
                    finish = config["finish"]

                seg = book_match(
                    db,
                    show.id,
                    show.world_id,
                    wrestler_ids=[w1.id, w2.id],
                    match_type=match_type,
                    stipulation=stipulation,
                    planned_winner_id=planned_winner.id,
                    planned_finish=finish,
                )
                segments.append(seg)
                used.add(w1.id)
                used.add(w2.id)
                storyline_matches_booked += 1

    # Check for tag teams — book a tag match if available (30% chance)
    tag_teams = (
        db.query(TagTeamDB)
        .filter(
            TagTeamDB.world_id == show.world_id,
            TagTeamDB.is_active == True,
            TagTeamDB.wrestler1_id.in_(wrestler_ids),
            TagTeamDB.wrestler2_id.in_(wrestler_ids),
        )
        .all()
    )

    booked_tag = False
    if len(tag_teams) >= 2 and random.random() < TAG_TEAM_BOOKING_RATE:
        t1, t2 = random.sample(tag_teams, 2)
        tag_wrestlers = [
            t1.wrestler1_id,
            t1.wrestler2_id,
            t2.wrestler1_id,
            t2.wrestler2_id,
        ]
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
                db,
                show.id,
                show.world_id,
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

    # --- Player match requests and dark matches ---
    # Check if any player wrestler on this roster has a pending match request
    world = db.query(WorldDB).filter(WorldDB.id == show.world_id).first()
    player_match_booked = False
    if world and world.world_config:
        pending_requests = (world.world_config or {}).get("pending_match_requests", [])
        for req in list(pending_requests):
            if req.get("federation_id") != fed.id:
                continue
            pw_id = req.get("wrestler_id")
            pw = next(
                (w for w in wrestlers if w.id == pw_id and w.id not in used), None
            )
            if not pw:
                continue

            if req.get("type") == "open_challenge" and req.get("opponent_id"):
                opp = next(
                    (
                        w
                        for w in wrestlers
                        if w.id == req["opponent_id"] and w.id not in used
                    ),
                    None,
                )
            else:
                # Pick a random opponent close in popularity
                candidates = [
                    w
                    for w in wrestlers
                    if w.id not in used and w.id != pw_id and not w.is_injured
                ]
                opp = random.choice(candidates) if candidates else None

            if opp:
                seg = book_match(
                    db,
                    show.id,
                    show.world_id,
                    wrestler_ids=[pw.id, opp.id],
                    match_type="singles",
                    planned_winner_id=pw.id
                    if random.random() < PLAYER_MATCH_WIN_RATE
                    else opp.id,
                    planned_finish="pinfall",
                    position=1,  # Opening match — gets the player on TV
                )
                segments.append(seg)
                used.add(pw.id)
                used.add(opp.id)
                player_match_booked = True

            # Remove fulfilled request
            pending_requests = [
                r for r in pending_requests if r.get("wrestler_id") != pw_id
            ]
            break  # One player match per show

        # Update metadata
        meta = world.world_config or {}
        meta["pending_match_requests"] = pending_requests
        world.world_config = meta

    # Dark match: if any player wrestler (is_npc=False) is on the roster
    # and hasn't been booked this show, give them a dark match for exposure
    if not player_match_booked:
        for w in wrestlers:
            if not w.is_npc and w.id not in used and not w.is_injured:
                candidates = [
                    o
                    for o in wrestlers
                    if o.id not in used and o.id != w.id and not o.is_injured
                ]
                if candidates:
                    opp = random.choice(candidates)
                    seg = book_match(
                        db,
                        show.id,
                        show.world_id,
                        wrestler_ids=[w.id, opp.id],
                        match_type="singles",
                        planned_winner_id=w.id
                        if random.random() < DARK_MATCH_WIN_RATE
                        else opp.id,
                        planned_finish="pinfall",
                        position=0,  # Dark match — position 0, before the card
                    )
                    segments.append(seg)
                    used.add(w.id)
                    used.add(opp.id)
                break  # One dark match max

    num_matches = min(len(wrestlers) // 2, len(CARD_POSITIONS))
    if booked_tag:
        num_matches = max(1, num_matches - 1)  # Already booked one

    # Book singles matches — reverse order so best wrestlers get main event
    match_wrestlers = [w for w in wrestlers if w.id not in used]
    # Put lower-ranked first (they'll be openers), higher-ranked last (main event)
    match_wrestlers.reverse()

    triple_threat_booked = False
    for i in range(num_matches):
        available = [w for w in match_wrestlers if w.id not in used]
        if len(available) < 2:
            break

        # 15% chance for a triple threat on weekly TV (once per show, not main event)
        actual_pos = i + (1 if booked_tag else 0)
        is_main_event_slot = actual_pos == num_matches + (1 if booked_tag else 0) - 1
        match_type = "singles"
        if (
            not triple_threat_booked
            and not is_main_event_slot
            and len(available) >= 3
            and random.random() < TRIPLE_THREAT_RATE
        ):
            w1, w2, w3 = available[0], available[1], available[2]
            used.add(w1.id)
            used.add(w2.id)
            used.add(w3.id)
            match_type = "triple_threat"
            triple_threat_booked = True
            # Winner is the highest-pushed of the three
            all_w = [w1, w2, w3]
            planned_winner = max(
                all_w, key=lambda w: _calculate_wrestler_score(w, push_map, PUSH_TIERS)
            )
            position = actual_pos + 1
            seg = book_match(
                db,
                show.id,
                show.world_id,
                wrestler_ids=[w1.id, w2.id, w3.id],
                match_type=match_type,
                planned_winner_id=planned_winner.id,
                planned_finish="pinfall",
                position=position,
            )
            segments.append(seg)
            continue

        w1, w2 = available[0], available[1]
        used.add(w1.id)
        used.add(w2.id)

        # Determine winner (push-tier aware)
        planned_winner = (
            w1
            if _calculate_wrestler_score(w1, push_map, PUSH_TIERS)
            >= _calculate_wrestler_score(w2, push_map, PUSH_TIERS)
            else w2
        )

        # Title match for main event if champion is available
        is_title = False
        champ_id = None
        if is_main_event_slot and championships:
            champ = championships[0]
            if champ.current_holder_id in (w1.id, w2.id):
                is_title = True
                champ_id = champ.id

        # Hardcore booking style adds stipulations and gimmick matches
        stipulation = None
        if booking_style == "hardcore" and random.random() < HARDCORE_STIPULATION_RATE:
            stipulation = random.choice(
                [
                    "No DQ",
                    "Falls Count Anywhere",
                    "Street Fight",
                    "Extreme Rules",
                    "Tables",
                    "Steel Cage",
                    "Ladder",
                ]
            )

        finish = random.choices(FINISH_TYPES, weights=FINISH_TYPE_WEIGHTS, k=1)[0]
        # Title matches almost always end clean
        if is_title and finish in ("count_out", "disqualification"):
            finish = "pinfall"
        position = actual_pos + 1

        seg = book_match(
            db,
            show.id,
            show.world_id,
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
        promo_wrestler = (
            available[0]
            if available
            else max(wrestlers, key=lambda w: w.popularity, default=None)
        )
        if promo_wrestler:
            book_promo_segment(
                db,
                show.id,
                description=f"{promo_wrestler.name} addresses the crowd",
                position=promo_pos,
                wrestler_id=promo_wrestler.id,
                world_id=show.world_id,
                game_date=show.game_date,
            )

    db.flush()
    return segments


def _book_ppv_card(
    db, show, fed, ppv_event, wrestlers, championships, push_map, booking_style
):
    """Book a PPV card from the PPV event's planned matches.

    Uses planned_main_event and planned_matches from the PPV calendar,
    falling back to the regular booking logic for unplanned slots.
    """
    segments = []
    used = set()
    wrestler_map = {w.id: w for w in wrestlers}
    position = 1

    # Book planned undercard matches first
    for planned in ppv_event.planned_matches or []:
        wids = planned.get("wrestler_ids", [])
        available = [
            wid
            for wid in wids
            if wid in wrestler_map
            and wid not in used
            and not wrestler_map[wid].is_injured
        ]
        if len(available) < 2:
            continue

        w1, w2 = wrestler_map[available[0]], wrestler_map[available[1]]
        used.update(available[:2])

        # Winner: higher push tier wins (PPV wins matter more)
        planned_winner = (
            w1
            if _calculate_wrestler_score(w1, push_map, PUSH_TIERS)
            >= _calculate_wrestler_score(w2, push_map, PUSH_TIERS)
            else w2
        )

        seg = book_match(
            db,
            show.id,
            show.world_id,
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
    me_available = [
        wid
        for wid in me_wids
        if wid in wrestler_map and wid not in used and not wrestler_map[wid].is_injured
    ]

    if len(me_available) >= 2:
        w1, w2 = wrestler_map[me_available[0]], wrestler_map[me_available[1]]
        used.update(me_available[:2])

        # Main event: champion usually retains at non-crown-jewel, 40% title change at crown jewel
        title_id = main_event.get("title_id")
        champ = None
        if title_id:
            champ = (
                db.query(ChampionshipDB).filter(ChampionshipDB.id == title_id).first()
            )

        if champ and champ.current_holder_id in (w1.id, w2.id):
            holder = w1 if w1.id == champ.current_holder_id else w2
            challenger = w2 if holder == w1 else w1
            if (
                ppv_event.is_crown_jewel
                and random.random() < CROWN_JEWEL_TITLE_CHANGE_RATE
            ):
                planned_winner = challenger  # Crown jewel title change!
            elif random.random() < REGULAR_PPV_TITLE_CHANGE_RATE:
                planned_winner = challenger  # Regular PPV title change
            else:
                planned_winner = holder  # Champion retains
        else:
            # Non-title main event
            planned_winner = (
                w1
                if _calculate_wrestler_score(w1, push_map, PUSH_TIERS)
                >= _calculate_wrestler_score(w2, push_map, PUSH_TIERS)
                else w2
            )

        seg = book_match(
            db,
            show.id,
            show.world_id,
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

    # Multi-person match for PPVs — fatal four way or battle royal
    remaining = [w for w in wrestlers if w.id not in used and not w.is_injured]

    is_crown_jewel = getattr(ppv_event, "is_crown_jewel", False)
    if is_crown_jewel and len(remaining) >= 6:
        # Crown Jewel battle royal with 6-10 participants
        br_count = min(len(remaining), 10)
        br_wrestlers = remaining[:br_count]
        br_ids = [w.id for w in br_wrestlers]
        for wid in br_ids:
            used.add(wid)
        # Winner is most popular
        winner = max(br_wrestlers, key=lambda w: w.popularity + random.randint(-10, 10))
        seg = book_match(
            db,
            show.id,
            show.world_id,
            wrestler_ids=br_ids,
            match_type="battle_royal",
            planned_winner_id=winner.id,
            planned_finish="last_person_standing",
            position=position,
        )
        segments.append(seg)
        position += 1
        remaining = [w for w in remaining if w.id not in used]
    elif len(remaining) >= 4:
        # Fatal four way on non-crown-jewel PPVs (60% chance)
        if random.random() < FATAL_FOUR_WAY_RATE:
            ffw = remaining[:4]
            ffw_ids = [w.id for w in ffw]
            for wid in ffw_ids:
                used.add(wid)
            winner = max(ffw, key=lambda w: w.popularity + random.randint(-10, 10))
            seg = book_match(
                db,
                show.id,
                show.world_id,
                wrestler_ids=ffw_ids,
                match_type="fatal_four_way",
                planned_winner_id=winner.id,
                planned_finish="pinfall",
                position=position,
            )
            segments.append(seg)
            position += 1
            remaining = [w for w in remaining if w.id not in used]

    # Fill remaining slots with singles matches
    for i in range(0, min(len(remaining) - 1, 4), 2):
        w1, w2 = remaining[i], remaining[i + 1]
        used.add(w1.id)
        used.add(w2.id)
        w1_score = w1.popularity + random.randint(-20, 20)
        w2_score = w2.popularity + random.randint(-20, 20)
        planned_winner = w1 if w1_score >= w2_score else w2

        seg = book_match(
            db,
            show.id,
            show.world_id,
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
            db,
            show.id,
            description=f"{top.name} opens {ppv_event.name} with a championship address",
            position=0,
            wrestler_id=top.id,
            world_id=show.world_id,
            game_date=show.game_date,
        )

    db.flush()
    return segments
