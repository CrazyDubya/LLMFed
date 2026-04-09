"""
Storyline engine - creates and evolves feuds, alliances, and narrative arcs.

Storylines are created from triggers (match results, title changes, betrayals)
and evolve over time through shows and promos. Heat builds toward a blowoff
match at a PPV.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    StorylineDB, StorylineParticipantDB, GameWrestlerDB, GameFederationDB,
    ContractDB, MatchDB, MatchParticipantDB, ChampionshipDB,
    GameNarrativeLogDB, LifeEventDB, WrestlerRelationshipDB,
    WrestlerBackstoryDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storyline templates
# ---------------------------------------------------------------------------

FEUD_TRIGGERS = [
    "{w1} attacked {w2} after their match!",
    "{w1} cost {w2} the championship opportunity!",
    "{w1} called out {w2} in a scathing promo!",
    "Tensions between {w1} and {w2} finally boiled over!",
    "{w1} stole {w2}'s finishing move, leading to a heated confrontation!",
]

ALLIANCE_TRIGGERS = [
    "{w1} and {w2} joined forces to take on a common enemy!",
    "{w1} came to the rescue of {w2} during a beatdown!",
    "{w1} and {w2} formed a new tag team!",
]

BETRAYAL_TRIGGERS = [
    "{w1} turned on longtime partner {w2} with a devastating attack!",
    "{w1} revealed they were behind {w2}'s recent misfortunes!",
    "{w1} walked out on {w2} during a title match, costing them the gold!",
]

STORYLINE_NAMES = {
    "feud": [
        "War of Wills", "Bad Blood", "The Grudge", "No Mercy",
        "Unfinished Business", "Path of Destruction", "Personal Vendetta",
        "The Rivalry", "Collision Course", "Score to Settle",
    ],
    "alliance": [
        "The Alliance", "Brothers in Arms", "United Front", "Power Pact",
        "The Partnership", "Dynamic Duo",
    ],
    "betrayal": [
        "The Betrayal", "Backstabbed", "Trust No One", "Fallen Alliance",
        "Broken Bond", "The Turn",
    ],
    "championship_chase": [
        "Road to Gold", "Championship Pursuit", "Title or Bust",
        "The Contender", "Golden Opportunity",
    ],
    "faction_war": [
        "War Games", "Gang Warfare", "Hostile Takeover", "Turf War",
        "The Invasion", "All-Out War", "Blood & Gold",
    ],
    "power_struggle": [
        "Civil War", "The Coup", "Throne Games", "Crown or Nothing",
        "House Divided", "Internal Combustion",
    ],
    "manager_betrayal": [
        "The Snake Sheds Its Skin", "Business Decision", "Free Agent",
        "Behind My Back", "Sold Out", "New Management",
    ],
}

FACTION_WAR_TRIGGERS = [
    "{s1} and {s2} erupted into an all-out brawl to close the show!",
    "{s1} invaded {s2}'s locker room, leaving destruction in their wake!",
    "The rivalry between {s1} and {s2} has reached a boiling point!",
    "{s1} issued a challenge to {s2} — winner takes all!",
]

MANAGER_BETRAYAL_TRIGGERS = [
    "{mgr} turned on {client}, revealing a secret alliance with their opponent!",
    "{mgr} walked out on {client} mid-match, leaving them to lose the championship!",
    "{mgr} announced they're done with {client} — and introduced their NEW client!",
    "Shocking betrayal! {mgr} hit {client} with a low blow and sided with the enemy!",
]


# ---------------------------------------------------------------------------
# Create storylines
# ---------------------------------------------------------------------------

def create_storyline(db: Session, world_id: str, federation_id: str,
                     wrestler_ids: list, storyline_type: str = "feud",
                     name: str = None, description: str = None,
                     game_date: str = None,
                     kayfabe_level: int = 100) -> StorylineDB:
    """Create a new storyline between wrestlers."""
    if not name:
        names = STORYLINE_NAMES.get(storyline_type, STORYLINE_NAMES["feud"])
        name = random.choice(names)

    if not description:
        wrestlers = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id.in_(wrestler_ids)
        ).all()
        w_names = {w.id: w.name for w in wrestlers}

        if storyline_type == "feud" and len(wrestler_ids) >= 2:
            template = random.choice(FEUD_TRIGGERS)
            description = template.format(
                w1=w_names.get(wrestler_ids[0], "???"),
                w2=w_names.get(wrestler_ids[1], "???"),
            )
        elif storyline_type == "betrayal" and len(wrestler_ids) >= 2:
            template = random.choice(BETRAYAL_TRIGGERS)
            description = template.format(
                w1=w_names.get(wrestler_ids[0], "???"),
                w2=w_names.get(wrestler_ids[1], "???"),
            )
        elif storyline_type == "alliance" and len(wrestler_ids) >= 2:
            template = random.choice(ALLIANCE_TRIGGERS)
            description = template.format(
                w1=w_names.get(wrestler_ids[0], "???"),
                w2=w_names.get(wrestler_ids[1], "???"),
            )
        else:
            description = f"A new {storyline_type} storyline unfolds."

    # LLM-as-booker: the head booker AI crafts the storyline
    import os
    if os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes"):
        try:
            from game_service.character_agent import booker_decide_storyline
            names = [w_names.get(wid, "Unknown") for wid in wrestler_ids[:2]]
            booker_result = booker_decide_storyline(
                db, federation_id,
                names[0] if names else "Unknown",
                names[1] if len(names) > 1 else "Unknown",
                context=f"Creating a {storyline_type} storyline.",
            )
            if booker_result.get("name"):
                name = booker_result["name"]
            if booker_result.get("description"):
                description = booker_result["description"]
            if booker_result.get("storyline_type"):
                storyline_type = booker_result["storyline_type"]
        except Exception:
            pass  # Keep template values

    storyline = StorylineDB(
        world_id=world_id,
        federation_id=federation_id,
        name=name,
        storyline_type=storyline_type,
        status="brewing",
        description=description,
        heat=random.randint(30, 50),
        start_date=game_date,
        kayfabe_level=kayfabe_level,
    )
    db.add(storyline)
    db.flush()

    # Add participants
    roles = ["protagonist", "antagonist"] + ["ally"] * (len(wrestler_ids) - 2)
    for i, wid in enumerate(wrestler_ids):
        role = roles[i] if i < len(roles) else "ally"
        db.add(StorylineParticipantDB(
            storyline_id=storyline.id,
            wrestler_id=wid,
            role=role,
            joined_date=game_date,
        ))

    return storyline


# ---------------------------------------------------------------------------
# Storyline progression
# ---------------------------------------------------------------------------

def progress_storyline(db: Session, storyline: StorylineDB, event_type: str,
                       heat_delta: int = 5, description: str = None):
    """Advance a storyline based on an event."""
    storyline.heat = max(0, min(100, storyline.heat + heat_delta))

    # Auto-escalate based on heat
    if storyline.status == "brewing" and storyline.heat >= 55:
        storyline.status = "active"
    elif storyline.status == "active" and storyline.heat >= 80:
        storyline.status = "climax"

    if description:
        db.add(GameNarrativeLogDB(
            world_id=storyline.world_id,
            game_date="",  # Caller should set this
            tick=0,
            event_type="storyline",
            description=description,
            involved_entities=[storyline.id],
            importance=6,
        ))


def resolve_storyline(db: Session, storyline: StorylineDB, resolution: str = None):
    """Mark a storyline as resolved."""
    storyline.status = "resolved"
    if resolution:
        storyline.planned_blowoff = resolution


# ---------------------------------------------------------------------------
# Auto-generate storylines for NPC federations
# ---------------------------------------------------------------------------

def auto_generate_storylines(db: Session, world_id: str, game_date: str):
    """Generate new storylines for NPC federations that need them.

    Called periodically from the world ticker.
    """
    npc_feds = db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world_id,
        GameFederationDB.is_npc == True,
        GameFederationDB.is_active == True,
    ).all()

    new_storylines = []
    for fed in npc_feds:
        # Count active storylines
        active_count = db.query(StorylineDB).filter(
            StorylineDB.federation_id == fed.id,
            StorylineDB.status.in_(["brewing", "active", "climax"]),
        ).count()

        if active_count >= 3:
            continue  # Enough storylines already

        # Get roster
        contracts = db.query(ContractDB).filter(
            ContractDB.federation_id == fed.id,
            ContractDB.status == "active",
        ).all()
        wrestler_ids = [c.wrestler_id for c in contracts]

        if len(wrestler_ids) < 2:
            continue

        # Get wrestlers not already in active storylines
        in_storylines = set()
        active_sl = db.query(StorylineDB).filter(
            StorylineDB.federation_id == fed.id,
            StorylineDB.status.in_(["brewing", "active", "climax"]),
        ).all()
        for sl in active_sl:
            parts = db.query(StorylineParticipantDB).filter(
                StorylineParticipantDB.storyline_id == sl.id
            ).all()
            for p in parts:
                in_storylines.add(p.wrestler_id)

        available = [wid for wid in wrestler_ids if wid not in in_storylines]
        if len(available) < 2:
            continue

        # Pick two wrestlers for a new storyline
        pair = random.sample(available, 2)
        stype = random.choices(
            ["feud", "championship_chase", "alliance", "betrayal"],
            weights=[50, 25, 15, 10],
            k=1,
        )[0]

        sl = create_storyline(
            db, world_id, fed.id, pair,
            storyline_type=stype,
            game_date=game_date,
        )
        new_storylines.append(sl)

    return new_storylines


# ---------------------------------------------------------------------------
# Match result → storyline trigger
# ---------------------------------------------------------------------------

def check_match_storyline_triggers(db: Session, match: MatchDB, game_date: str):
    """After a match completes, check if it should spawn or progress storylines."""
    if not match.is_completed:
        return

    participants = db.query(MatchParticipantDB).filter(
        MatchParticipantDB.match_id == match.id,
        MatchParticipantDB.role == "competitor",
    ).all()

    if len(participants) < 2:
        return

    winner = next((p for p in participants if p.is_winner), None)
    loser = next((p for p in participants if not p.is_winner), None)

    if not winner or not loser:
        return

    # Check existing storyline between these wrestlers
    existing = _find_storyline_between(db, winner.wrestler_id, loser.wrestler_id)

    if existing:
        # Progress existing storyline — heat scales with match quality
        rating = match.match_rating or 3.0
        base_heat = 8 if match.is_title_match else 6
        quality_bonus = max(0, int((rating - 3.0) * 3))  # +3 per star above 3.0
        card_bonus = 3 if getattr(match, 'card_position', '') == 'main_event' else 0
        heat_delta = base_heat + quality_bonus + card_bonus

        # Seasonal heat multiplier: storylines get a boost during PPV build windows
        try:
            from game_service.ppv_calendar_service import get_next_ppv, is_build_window
            from models.game_models import ShowDB, ShowSegmentDB
            seg = match.segment
            if seg:
                show = db.query(ShowDB).filter(ShowDB.id == seg.show_id).first()
                if show:
                    next_ppv = get_next_ppv(db, show.federation_id, show.game_date)
                    if next_ppv and is_build_window(show.game_date, next_ppv.scheduled_date):
                        if getattr(next_ppv, 'is_crown_jewel', False):
                            heat_delta = int(heat_delta * 2.0)  # Crown Jewel build: +100%
                        else:
                            heat_delta = int(heat_delta * 1.5)  # Regular PPV build: +50%
        except Exception:
            pass  # PPV calendar system is optional

        progress_storyline(
            db, existing, "match_result", heat_delta,
            description=f"Their rivalry intensified after a {rating:.1f}-star match!",
        )
    else:
        # Small chance a competitive match spawns a new feud
        if match.match_rating and match.match_rating >= 3.5 and random.random() < 0.25:
            # Get federation from show segment
            segment = match.segment
            fed_id = None
            if segment and segment.show:
                fed_id = segment.show.federation_id

            if fed_id:
                create_storyline(
                    db, match.world_id, fed_id,
                    [winner.wrestler_id, loser.wrestler_id],
                    storyline_type="feud",
                    game_date=game_date,
                )


def _find_storyline_between(db: Session, w1_id: str, w2_id: str):
    """Find an active storyline involving both wrestlers."""
    sl_ids_1 = {sp.storyline_id for sp in db.query(StorylineParticipantDB).filter(
        StorylineParticipantDB.wrestler_id == w1_id
    ).all()}
    sl_ids_2 = {sp.storyline_id for sp in db.query(StorylineParticipantDB).filter(
        StorylineParticipantDB.wrestler_id == w2_id
    ).all()}

    common = sl_ids_1 & sl_ids_2
    if not common:
        return None

    return db.query(StorylineDB).filter(
        StorylineDB.id.in_(common),
        StorylineDB.status.in_(["brewing", "active", "climax"]),
    ).first()


# ---------------------------------------------------------------------------
# Kayfabe spectrum: worked-shoot storylines from real events
# ---------------------------------------------------------------------------

WORKED_SHOOT_NAMES = [
    "Breaking Point", "Shoot to Kill", "Off Script", "Real Talk",
    "Behind the Curtain", "No Character Required", "The Unscripted",
]

WORKED_SHOOT_DESCRIPTIONS = [
    "What started as a real backstage conflict has become the hottest angle in the company.",
    "The lines between real life and storyline have blurred beyond recognition.",
    "Nobody is sure what's real and what's a work anymore — and that's the point.",
    "A personal grievance has spilled over into the ring.",
]


def check_life_event_storylines(db: Session, world_id: str, game_date: str):
    """Check if any public life events should become worked-shoot storylines.

    Only fires for federations with low-to-medium kayfabe strictness.
    """
    new_storylines = []

    # Find public, storyline-potential life events not yet used
    events = db.query(LifeEventDB).filter(
        LifeEventDB.world_id == world_id,
        LifeEventDB.is_public == True,
        LifeEventDB.storyline_potential == True,
        LifeEventDB.was_used_in_storyline == False,
        LifeEventDB.is_active == True,
    ).all()

    for event in events:
        wrestler = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == event.wrestler_id,
        ).first()
        if not wrestler:
            continue

        # Find the wrestler's federation
        contract = db.query(ContractDB).filter(
            ContractDB.wrestler_id == wrestler.id,
            ContractDB.status == "active",
        ).first()
        if not contract:
            continue

        fed = db.query(GameFederationDB).filter(
            GameFederationDB.id == contract.federation_id,
        ).first()
        if not fed:
            continue

        # Only low-to-medium kayfabe federations use real events
        strictness = fed.kayfabe_strictness or 50
        if strictness > 60:
            continue

        # Probability based on severity and fed's openness
        probability = (event.severity / 10.0) * ((100 - strictness) / 100.0) * 0.3
        if random.random() > probability:
            continue

        # Find a foil — someone the wrestler has a relationship with
        rel = db.query(WrestlerRelationshipDB).filter(
            ((WrestlerRelationshipDB.wrestler1_id == wrestler.id) |
             (WrestlerRelationshipDB.wrestler2_id == wrestler.id)),
            WrestlerRelationshipDB.rivalry_heat > 30,
        ).first()

        if rel:
            foil_id = rel.wrestler2_id if rel.wrestler1_id == wrestler.id else rel.wrestler1_id
        else:
            # Pick a random roster member
            roster = db.query(ContractDB).filter(
                ContractDB.federation_id == fed.id,
                ContractDB.status == "active",
                ContractDB.wrestler_id != wrestler.id,
            ).all()
            if not roster:
                continue
            foil_id = random.choice(roster).wrestler_id

        # Determine kayfabe level based on how "real" the source material is
        kayfabe_level = max(10, 50 - event.severity * 4)

        sl = create_storyline(
            db, world_id, fed.id,
            [wrestler.id, foil_id],
            storyline_type="feud",
            name=random.choice(WORKED_SHOOT_NAMES),
            description=random.choice(WORKED_SHOOT_DESCRIPTIONS),
            game_date=game_date,
            kayfabe_level=kayfabe_level,
        )
        event.was_used_in_storyline = True
        new_storylines.append(sl)
        logger.info("Created worked-shoot storyline '%s' from life event for %s",
                     sl.name, wrestler.name)

    return new_storylines


def check_relationship_collision_storylines(db: Session, world_id: str, game_date: str):
    """Check for real-vs-kayfabe relationship collisions that could become storylines.

    Detects: real friends booked as rivals, real enemies booked as allies.
    """
    new_storylines = []

    # Find relationships where real and kayfabe are in tension
    rels = db.query(WrestlerRelationshipDB).filter(
        WrestlerRelationshipDB.world_id == world_id,
    ).all()

    for rel in rels:
        real = rel.real_relationship
        kayfabe = rel.kayfabe_alignment
        if not real or not kayfabe:
            continue

        # Real friends, kayfabe rivals — potential worked-shoot tension
        is_collision = (
            (real == "friends" and kayfabe == "rivals") or
            (real == "enemies" and kayfabe in ("allies", "tag_partners"))
        )
        if not is_collision:
            continue

        # Low probability per check — this is a slow-burn trigger
        if random.random() > 0.05:
            continue

        # Check if they already have an active storyline
        existing = _find_storyline_between(db, rel.wrestler1_id, rel.wrestler2_id)
        if existing:
            continue

        # Find federation
        contract = db.query(ContractDB).filter(
            ContractDB.wrestler_id == rel.wrestler1_id,
            ContractDB.status == "active",
        ).first()
        if not contract:
            continue

        fed = db.query(GameFederationDB).filter(
            GameFederationDB.id == contract.federation_id,
        ).first()
        if not fed or (fed.kayfabe_strictness or 50) > 70:
            continue

        collision_type = "feud" if real == "enemies" else "betrayal"
        sl = create_storyline(
            db, world_id, fed.id,
            [rel.wrestler1_id, rel.wrestler2_id],
            storyline_type=collision_type,
            name=random.choice(WORKED_SHOOT_NAMES),
            description="The tension between these two has become impossible to contain.",
            game_date=game_date,
            kayfabe_level=30,
        )
        new_storylines.append(sl)

    return new_storylines
