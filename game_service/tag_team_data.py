"""
Tag team name pools, finisher templates, and name-generation logic.

Extracted from WorldTicker to keep creative data separate from tick logic.
"""

import random

from sqlalchemy.orm import Session

from models.game_models import GameWrestlerDB, WrestlerStatsDB, TagTeamDB


TAG_TEAM_NAMES = {
    "power": [
        "The Wrecking Crew", "Heavy Artillery", "The Demolition Squad",
        "Iron Curtain", "The Juggernaut Express", "Total Destruction",
        "The War Machine", "Brute Force", "The Colossus Connection",
    ],
    "highflyer": [
        "Air Raid", "Terminal Velocity", "Sky High",
        "The Shooting Stars", "Double Vision", "The Aerials",
        "Freefall", "Altitude Sickness", "The High Wire",
    ],
    "technical": [
        "The Submission Squad", "Chain Reaction", "The Technicians",
        "Master Class", "Precision Strike", "The Chess Club",
        "Clinical Finish", "The Hold Exchange", "Mat Generals",
    ],
    "brawler": [
        "Street Justice", "The Pitfighters", "Knuckle Up",
        "Bar Room Blitz", "The Enforcers", "Concrete Justice",
        "The Roughnecks", "Violent Tendencies", "The Brawl Brothers",
    ],
    "mixed": [
        "Brains & Brawn", "The Odd Couple", "Chaos Theory",
        "Yin & Yang", "The Contrast", "Unlikely Alliance",
        "Controlled Chaos", "Thunder & Lightning", "The Paradox",
    ],
    "generic": [
        "The Alliance", "Double Trouble", "The Partnership",
        "Tandem", "The Foundation", "The Coalition",
        "Second Wind", "The Union", "Full Circle",
    ],
}

TEAM_FINISHER_TEMPLATES = [
    "Double {move}", "The {adj} Bomb", "{adj} Annihilation",
    "Total {move}", "The Grand Finale", "Doomsday {move}",
    "Double Down", "The Crescendo", "Curtain Call",
]
FINISHER_MOVES = ["Powerbomb", "Suplex", "Slam", "Piledriver", "Cutter", "DDT"]
FINISHER_ADJS = ["Midnight", "Thunderous", "Final", "Atomic", "Devastating", "Crimson"]


def _classify_style(stats: WrestlerStatsDB) -> str:
    """Classify a wrestler's dominant ring style from their stats."""
    if not stats:
        return "generic"
    top = max(
        ("power", stats.power), ("highflyer", stats.aerial + stats.speed),
        ("technical", stats.technical + stats.submission),
        ("brawler", stats.brawling + stats.toughness),
        key=lambda x: x[1],
    )
    return top[0]


def generate_tag_team_name(
    db: Session,
    world_id: str,
    w1: GameWrestlerDB,
    w2: GameWrestlerDB,
) -> tuple:
    """Generate a creative tag team name and finisher based on wrestler styles.

    Returns (team_name, finisher_name).
    """
    stats1 = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w1.id).first()
    stats2 = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w2.id).first()

    cat1, cat2 = _classify_style(stats1), _classify_style(stats2)
    pool_key = cat1 if cat1 == cat2 else "mixed"

    # Pick from pool, avoiding names already used in this world
    existing_names = {
        t.name for t in db.query(TagTeamDB).filter(
            TagTeamDB.world_id == world_id
        ).all()
    }
    pool = [n for n in TAG_TEAM_NAMES.get(pool_key, []) if n not in existing_names]
    if not pool:
        pool = [n for n in TAG_TEAM_NAMES["generic"] if n not in existing_names]
    if not pool:
        # Absolute fallback
        team_name = f"{w1.name} & {w2.name}"
    else:
        team_name = random.choice(pool)

    # Generate team finisher name
    template = random.choice(TEAM_FINISHER_TEMPLATES)
    finisher_name = template.format(
        move=random.choice(FINISHER_MOVES),
        adj=random.choice(FINISHER_ADJS),
    )

    return team_name, finisher_name
