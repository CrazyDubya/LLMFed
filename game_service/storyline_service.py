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
    GameNarrativeLogDB,
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
}


# ---------------------------------------------------------------------------
# Create storylines
# ---------------------------------------------------------------------------

def create_storyline(db: Session, world_id: str, federation_id: str,
                     wrestler_ids: list, storyline_type: str = "feud",
                     name: str = None, description: str = None,
                     game_date: str = None) -> StorylineDB:
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

    storyline = StorylineDB(
        world_id=world_id,
        federation_id=federation_id,
        name=name,
        storyline_type=storyline_type,
        status="brewing",
        description=description,
        heat=random.randint(30, 50),
        start_date=game_date,
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
        # Progress existing storyline
        heat_delta = 8 if match.is_title_match else 5
        progress_storyline(
            db, existing, "match_result", heat_delta,
            description=f"Their rivalry intensified after a {match.match_rating or 0:.1f}-star match!",
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
