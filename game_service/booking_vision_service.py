"""
Booking Vision Service — the promoter's master plan.

Generates and maintains the strategic booking vision for each federation:
- Push tiers (who's at what level on the card)
- Wrestler trajectories (who's rising, who's transitional)
- Title pipelines (who challenges next, planned reign lengths)
- Planned feuds/storylines penciled in for future PPVs
- Adaptation when plans get derailed (injuries, departures, hot/cold acts)

NPC feds get auto-generated visions at world creation.
Player feds get a suggested vision they can edit.
"""

import random
import logging
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models.game_models import (
    BookingVisionDB, WrestlerPushDB, PPVEventDB,
    GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ContractDB, ChampionshipDB, StorylineDB, StorylineParticipantDB,
    WrestlerRelationshipDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Push tier definitions
# ---------------------------------------------------------------------------

PUSH_TIERS = ["main_event", "upper_midcard", "midcard", "lower_card", "jobber"]

IDENTITY_TEMPLATES = {
    "workrate": [
        "A wrestling-first promotion where in-ring excellence matters most",
        "The home of technical wrestling — best matches on the planet",
        "Where athletes compete and the best wrestler wins",
    ],
    "entertainment": [
        "The biggest spectacle in sports entertainment",
        "Where characters are larger than life and every moment is an event",
        "A sports entertainment empire built on spectacle and star power",
    ],
    "hardcore": [
        "The most extreme promotion in the business — anything goes",
        "Where rules are suggestions and violence is the main attraction",
        "A no-holds-barred battleground for the toughest fighters alive",
    ],
    "storyline": [
        "A promotion built on compelling storylines and long-term booking",
        "Where every match tells a story and every show advances the narrative",
        "The thinking fan's promotion — psychology over spectacle",
    ],
}

LONG_TERM_GOALS = [
    "Become the #1 federation in the industry",
    "Develop the next generation of main event talent",
    "Build the most loyal fanbase in wrestling",
    "Create the most prestigious championship in the business",
    "Dominate the {region} market",
    "Produce the highest-rated TV show in wrestling",
]


# ---------------------------------------------------------------------------
# Vision generation
# ---------------------------------------------------------------------------

def generate_federation_vision(
    db: Session,
    federation: GameFederationDB,
    roster: List[GameWrestlerDB],
) -> BookingVisionDB:
    """Generate a complete booking vision for a federation based on its
    personality, roster, and championships.

    Called at world creation for NPC feds and as a suggestion for players.
    """
    booking_style = (federation.ai_personality or {}).get("booking_style", "entertainment")

    # Strategic identity
    identity = random.choice(IDENTITY_TEMPLATES.get(booking_style, IDENTITY_TEMPLATES["entertainment"]))
    goal = random.choice(LONG_TERM_GOALS).format(region=federation.home_region)

    # Sort roster by draw potential for tier assignment
    scored_roster = _score_roster_for_tiers(db, roster, booking_style)

    # Assign push tiers
    push_tiers = _assign_push_tiers(scored_roster)

    # Generate trajectories for top talent
    trajectories = _generate_trajectories(scored_roster, push_tiers)

    # Build title pipelines
    title_pipelines = _build_title_pipelines(db, federation, push_tiers)

    # Crown jewel vision
    main_eventers = push_tiers.get("main_event", [])
    crown_jewel = {
        "theme": "The biggest show of the year",
        "main_event_dream": f"Championship match between the top two stars",
        "ideal_wrestlers": main_eventers[:4] if main_eventers else [],
    }

    # Plan initial storylines
    planned_storylines = _generate_planned_storylines(
        db, federation, push_tiers, scored_roster
    )

    vision = BookingVisionDB(
        world_id=federation.world_id,
        federation_id=federation.id,
        identity=identity,
        long_term_goal=goal,
        crown_jewel_vision=crown_jewel,
        push_tiers=push_tiers,
        trajectories=trajectories,
        title_pipelines=title_pipelines,
        planned_storylines=planned_storylines,
        adaptation_log=[],
    )
    db.add(vision)
    db.flush()

    # Create WrestlerPushDB records for efficient querying
    _create_push_records(db, federation, push_tiers, trajectories)

    return vision


def _score_roster_for_tiers(
    db: Session,
    roster: List[GameWrestlerDB],
    booking_style: str,
) -> List[Dict]:
    """Score each wrestler for tier placement based on booking style."""
    scored = []
    for w in roster:
        stats = db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == w.id
        ).first()

        if not stats:
            scored.append({"wrestler": w, "score": w.popularity})
            continue

        if booking_style == "workrate":
            ring_score = (stats.technical + stats.psychology + stats.selling) / 3
            score = ring_score * 0.6 + w.popularity * 0.4
        elif booking_style == "entertainment":
            charisma_score = (stats.charisma + stats.mic_skill) / 2
            score = charisma_score * 0.4 + w.popularity * 0.6
        elif booking_style == "hardcore":
            tough_score = (stats.brawling + stats.toughness + stats.power) / 3
            score = tough_score * 0.5 + w.popularity * 0.5
        else:  # storyline
            psych_score = (stats.psychology + stats.charisma + stats.mic_skill) / 3
            score = psych_score * 0.5 + w.popularity * 0.5

        # Group 3: Backstage politics modifier
        politics_bonus = (stats.backstage_politics or 50) / 200  # 0 to 0.5
        score *= (1.0 + politics_bonus)

        scored.append({"wrestler": w, "score": score, "stats": stats})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _assign_push_tiers(scored_roster: List[Dict]) -> Dict[str, List[str]]:
    """Assign wrestlers to push tiers based on their scores."""
    total = len(scored_roster)
    if total == 0:
        return {t: [] for t in PUSH_TIERS}

    # Distribution: ~10% main event, ~20% upper mid, ~30% midcard, ~25% lower, ~15% jobber
    tiers = {
        "main_event": [],
        "upper_midcard": [],
        "midcard": [],
        "lower_card": [],
        "jobber": [],
    }

    for i, entry in enumerate(scored_roster):
        pct = i / max(total, 1)
        wid = entry["wrestler"].id

        if pct < 0.10 or i < 2:  # At least 2 main eventers
            tiers["main_event"].append(wid)
        elif pct < 0.30:
            tiers["upper_midcard"].append(wid)
        elif pct < 0.60:
            tiers["midcard"].append(wid)
        elif pct < 0.85:
            tiers["lower_card"].append(wid)
        else:
            tiers["jobber"].append(wid)

    return tiers


def _generate_trajectories(
    scored_roster: List[Dict],
    push_tiers: Dict[str, List[str]],
) -> Dict[str, Dict]:
    """Generate trajectory plans for wrestlers the booker wants to move."""
    trajectories = {}
    main_eventers = set(push_tiers.get("main_event", []))
    upper_mid = set(push_tiers.get("upper_midcard", []))

    for entry in scored_roster:
        w = entry["wrestler"]
        score = entry["score"]

        # Young, high-potential wrestlers get "rising" trajectories
        if w.id in upper_mid and w.age and w.age < 28 and score > 55:
            trajectories[w.id] = {
                "direction": "rising",
                "target_tier": "main_event",
                "notes": "Young talent with main event potential",
                "status": "penciled",
            }
        # Established main eventers
        elif w.id in main_eventers:
            trajectories[w.id] = {
                "direction": "established",
                "target_tier": "main_event",
                "notes": "Franchise player",
                "status": "ink",
            }
        # Older main eventers may be transitional
        elif w.id in main_eventers and w.age and w.age > 38:
            trajectories[w.id] = {
                "direction": "transitional",
                "target_tier": "upper_midcard",
                "notes": "Veteran to put over new talent",
                "status": "penciled",
            }

    return trajectories


def _build_title_pipelines(
    db: Session,
    federation: GameFederationDB,
    push_tiers: Dict[str, List[str]],
) -> Dict[str, Dict]:
    """Build title pipelines — who challenges next for each belt."""
    championships = db.query(ChampionshipDB).filter(
        ChampionshipDB.federation_id == federation.id,
        ChampionshipDB.is_active == True,
    ).all()

    pipelines = {}
    main_eventers = push_tiers.get("main_event", [])
    upper_mid = push_tiers.get("upper_midcard", [])

    for champ in championships:
        holder = champ.current_holder_id
        # Next challengers: main eventers who aren't the champion
        challengers = [wid for wid in main_eventers if wid != holder]
        # Pad with upper midcarders if needed
        if len(challengers) < 2:
            challengers.extend([wid for wid in upper_mid if wid != holder and wid not in challengers])

        pipelines[champ.id] = {
            "current_holder": holder,
            "planned_reign_weeks": random.randint(8, 30),
            "next_challengers": challengers[:3],
            "dream_match": {
                "wrestler_ids": challengers[:2] + ([holder] if holder else []),
            },
        }

    return pipelines


def _generate_planned_storylines(
    db: Session,
    federation: GameFederationDB,
    push_tiers: Dict[str, List[str]],
    scored_roster: List[Dict],
) -> List[Dict]:
    """Generate 2-4 planned future storylines."""
    planned = []
    main_eventers = push_tiers.get("main_event", [])
    upper_mid = push_tiers.get("upper_midcard", [])
    all_top = main_eventers + upper_mid

    if len(all_top) < 2:
        return planned

    # Plan 2-4 storylines
    used = set()
    for _ in range(min(4, len(all_top) // 2)):
        available = [wid for wid in all_top if wid not in used]
        if len(available) < 2:
            break

        pair = random.sample(available, 2)
        used.update(pair)

        stype = random.choices(
            ["feud", "championship_chase", "betrayal"],
            weights=[50, 30, 20], k=1
        )[0]

        planned.append({
            "wrestler_ids": pair,
            "type": stype,
            "status": "penciled",
            "notes": f"Planned {stype} between top talent",
        })

    return planned


def _create_push_records(
    db: Session,
    federation: GameFederationDB,
    push_tiers: Dict[str, List[str]],
    trajectories: Dict[str, Dict],
):
    """Create WrestlerPushDB records for each wrestler in the roster."""
    for tier, wrestler_ids in push_tiers.items():
        for wid in wrestler_ids:
            traj = trajectories.get(wid, {})
            direction = traj.get("direction", "established")
            protected = tier in ("main_event", "upper_midcard") and direction != "transitional"

            push = WrestlerPushDB(
                world_id=federation.world_id,
                federation_id=federation.id,
                wrestler_id=wid,
                push_tier=tier,
                direction=direction,
                confidence=70 if tier == "main_event" else 50,
                protected=protected,
            )
            db.add(push)

    db.flush()


# ---------------------------------------------------------------------------
# Vision adaptation — reacting to disruptions
# ---------------------------------------------------------------------------

def adapt_vision_for_injury(
    db: Session,
    vision: BookingVisionDB,
    wrestler_id: str,
    weeks_out: int,
    game_date: str,
):
    """Adapt booking plans when a wrestler gets injured."""
    risk_tolerance = (
        db.query(GameFederationDB)
        .filter(GameFederationDB.id == vision.federation_id)
        .first()
    )
    risk = (risk_tolerance.ai_personality or {}).get("risk_tolerance", 50) if risk_tolerance else 50

    changes = []

    # Check if injured wrestler is in title pipeline
    pipelines = dict(vision.title_pipelines or {})
    for champ_id, pipeline in pipelines.items():
        if pipeline.get("current_holder") == wrestler_id and weeks_out >= 4:
            # Champion injured — need to strip or hold
            if weeks_out >= 8 or risk < 40:
                # Strip the title, promote next challenger
                challengers = pipeline.get("next_challengers", [])
                if challengers:
                    pipeline["current_holder"] = None  # Vacant
                    changes.append(f"Title vacated due to {weeks_out}-week injury")
            else:
                changes.append(f"Champion injured {weeks_out} weeks — holding title")
        elif wrestler_id in pipeline.get("next_challengers", []):
            # Remove from challenger pipeline
            pipeline["next_challengers"] = [
                c for c in pipeline["next_challengers"] if c != wrestler_id
            ]
            changes.append(f"Removed from title challenger pipeline (injury)")

    vision.title_pipelines = pipelines
    flag_modified(vision, "title_pipelines")

    # Check planned storylines
    planned = list(vision.planned_storylines or [])
    for sl in planned:
        if wrestler_id in sl.get("wrestler_ids", []):
            if weeks_out >= 6:
                sl["status"] = "cancelled"
                changes.append(f"Planned storyline cancelled (injury)")
            else:
                sl["status"] = "delayed"
                changes.append(f"Planned storyline delayed (injury)")

    vision.planned_storylines = planned
    flag_modified(vision, "planned_storylines")

    # Log adaptation
    log = list(vision.adaptation_log or [])
    for change in changes:
        log.append({"date": game_date, "change": change, "reason": f"injury_{weeks_out}w"})
    vision.adaptation_log = log
    flag_modified(vision, "adaptation_log")

    db.add(vision)
    db.flush()
    logger.info("Vision adapted for injury: %s", changes)


def adapt_vision_for_departure(
    db: Session,
    vision: BookingVisionDB,
    wrestler_id: str,
    game_date: str,
):
    """Adapt booking plans when a wrestler leaves the federation."""
    changes = []

    # Remove from push tiers
    tiers = dict(vision.push_tiers or {})
    for tier, ids in tiers.items():
        if wrestler_id in ids:
            tiers[tier] = [wid for wid in ids if wid != wrestler_id]
            changes.append(f"Removed from {tier} tier")
    vision.push_tiers = tiers
    flag_modified(vision, "push_tiers")

    # Remove from trajectories
    trajs = dict(vision.trajectories or {})
    if wrestler_id in trajs:
        del trajs[wrestler_id]
        changes.append("Trajectory plan removed")
    vision.trajectories = trajs
    flag_modified(vision, "trajectories")

    # Remove from title pipelines
    pipelines = dict(vision.title_pipelines or {})
    for champ_id, pipeline in pipelines.items():
        if pipeline.get("current_holder") == wrestler_id:
            pipeline["current_holder"] = None
            changes.append("Title vacated (departure)")
        if wrestler_id in pipeline.get("next_challengers", []):
            pipeline["next_challengers"] = [
                c for c in pipeline["next_challengers"] if c != wrestler_id
            ]
            changes.append("Removed from title pipeline (departure)")
    vision.title_pipelines = pipelines
    flag_modified(vision, "title_pipelines")

    # Cancel planned storylines involving them
    planned = list(vision.planned_storylines or [])
    for sl in planned:
        if wrestler_id in sl.get("wrestler_ids", []):
            sl["status"] = "cancelled"
            changes.append("Planned storyline cancelled (departure)")
    vision.planned_storylines = planned
    flag_modified(vision, "planned_storylines")

    # Remove WrestlerPushDB record
    db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == vision.federation_id,
        WrestlerPushDB.wrestler_id == wrestler_id,
    ).delete()

    log = list(vision.adaptation_log or [])
    for change in changes:
        log.append({"date": game_date, "change": change, "reason": "departure"})
    vision.adaptation_log = log
    flag_modified(vision, "adaptation_log")

    db.add(vision)
    db.flush()
    logger.info("Vision adapted for departure: %s", changes)


def adapt_vision_for_hot_act(
    db: Session,
    vision: BookingVisionDB,
    wrestler_id: str,
    game_date: str,
):
    """Promote a wrestler who's getting unexpectedly over with the crowd."""
    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == vision.federation_id
    ).first()
    risk = (fed.ai_personality or {}).get("risk_tolerance", 50) if fed else 50

    # High-risk promoters push hot acts faster
    if risk < 30 and random.random() > 0.3:
        return  # Conservative booker waits to see if it's sustained

    tiers = dict(vision.push_tiers or {})
    current_tier = None
    for tier, ids in tiers.items():
        if wrestler_id in ids:
            current_tier = tier
            break

    if current_tier is None:
        return

    # Determine promotion target
    tier_order = PUSH_TIERS
    current_idx = tier_order.index(current_tier) if current_tier in tier_order else 2
    if current_idx <= 0:
        return  # Already at top

    new_tier = tier_order[current_idx - 1]

    # Move wrestler up
    tiers[current_tier] = [wid for wid in tiers[current_tier] if wid != wrestler_id]
    tiers.setdefault(new_tier, []).append(wrestler_id)
    vision.push_tiers = tiers
    flag_modified(vision, "push_tiers")

    # Update trajectory
    trajs = dict(vision.trajectories or {})
    trajs[wrestler_id] = {
        "direction": "rising",
        "target_tier": new_tier,
        "notes": "Organically getting over — riding the wave",
        "status": "penciled",
    }
    vision.trajectories = trajs
    flag_modified(vision, "trajectories")

    # Update WrestlerPushDB
    push = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == vision.federation_id,
        WrestlerPushDB.wrestler_id == wrestler_id,
    ).first()
    if push:
        push.push_tier = new_tier
        push.direction = "rising"
        push.confidence = min(100, push.confidence + 15)

    log = list(vision.adaptation_log or [])
    log.append({
        "date": game_date,
        "change": f"Promoted from {current_tier} to {new_tier} — hot act",
        "reason": "hot_act",
    })
    vision.adaptation_log = log
    flag_modified(vision, "adaptation_log")

    db.add(vision)
    db.flush()
    logger.info("Vision adapted for hot act: %s → %s", current_tier, new_tier)


def adapt_vision_for_cold_act(
    db: Session,
    vision: BookingVisionDB,
    wrestler_id: str,
    game_date: str,
):
    """Demote a wrestler whose push isn't connecting with the audience."""
    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == vision.federation_id
    ).first()
    risk = (fed.ai_personality or {}).get("risk_tolerance", 50) if fed else 50

    # Conservative bookers stick with their guy longer
    if risk < 40 and random.random() > 0.5:
        return  # Stubborn — give it more time

    tiers = dict(vision.push_tiers or {})
    current_tier = None
    for tier, ids in tiers.items():
        if wrestler_id in ids:
            current_tier = tier
            break

    if current_tier is None or current_tier == "jobber":
        return

    tier_order = PUSH_TIERS
    current_idx = tier_order.index(current_tier) if current_tier in tier_order else 2
    new_tier = tier_order[min(current_idx + 1, len(tier_order) - 1)]

    tiers[current_tier] = [wid for wid in tiers[current_tier] if wid != wrestler_id]
    tiers.setdefault(new_tier, []).append(wrestler_id)
    vision.push_tiers = tiers
    flag_modified(vision, "push_tiers")

    trajs = dict(vision.trajectories or {})
    trajs[wrestler_id] = {
        "direction": "cooling_off",
        "target_tier": new_tier,
        "notes": "Push not connecting — cooling off",
        "status": "penciled",
    }
    vision.trajectories = trajs
    flag_modified(vision, "trajectories")

    push = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == vision.federation_id,
        WrestlerPushDB.wrestler_id == wrestler_id,
    ).first()
    if push:
        push.push_tier = new_tier
        push.direction = "cooling_off"
        push.confidence = max(10, push.confidence - 15)

    log = list(vision.adaptation_log or [])
    log.append({
        "date": game_date,
        "change": f"Demoted from {current_tier} to {new_tier} — cold act",
        "reason": "cold_act",
    })
    vision.adaptation_log = log
    flag_modified(vision, "adaptation_log")
    db.add(vision)
    db.flush()


# ---------------------------------------------------------------------------
# Querying push status
# ---------------------------------------------------------------------------

def get_push_tier(db: Session, federation_id: str, wrestler_id: str) -> Optional[str]:
    """Get a wrestler's current push tier in a federation."""
    push = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == federation_id,
        WrestlerPushDB.wrestler_id == wrestler_id,
    ).first()
    return push.push_tier if push else "midcard"


def get_tier_roster(db: Session, federation_id: str, tier: str) -> List[str]:
    """Get all wrestler IDs at a specific push tier."""
    pushes = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == federation_id,
        WrestlerPushDB.push_tier == tier,
    ).all()
    return [p.wrestler_id for p in pushes]


def is_protected(db: Session, federation_id: str, wrestler_id: str) -> bool:
    """Check if a wrestler is 'protected' (shouldn't lose clean)."""
    push = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.federation_id == federation_id,
        WrestlerPushDB.wrestler_id == wrestler_id,
    ).first()
    return push.protected if push else False
