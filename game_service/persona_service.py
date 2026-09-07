"""
Persona service — manages the duality between the real person and the wrestling character.

Handles: backstory generation, gimmick creation/evolution, life events,
persona collision detection, and migration of existing wrestlers.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB,
    WrestlerBackstoryDB,
    GimmickHistoryDB,
    LifeEventDB,
    WrestlerRelationshipDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCHETYPES = [
    "monster_heel",
    "underdog_face",
    "cocky_technician",
    "silent_assassin",
    "cult_leader",
    "comedy_act",
    "anti_hero",
    "legacy",
    "patriot",
    "daredevil",
]

FAMILY_SITUATIONS = [
    "single",
    "married",
    "married_with_kids",
    "divorced",
    "divorced_with_kids",
    "long_term_relationship",
    "estranged_family",
    "close_family",
]

PRE_WRESTLING_CAREERS = [
    "bouncer",
    "amateur_wrestler",
    "football_player",
    "military",
    "teacher",
    "construction_worker",
    "personal_trainer",
    "martial_artist",
    "actor",
    "nothing_went_straight_to_wrestling",
    "college_athlete",
    "firefighter",
    "security_guard",
    "stunt_performer",
]

MOTIVATIONS = [
    "passion",
    "money",
    "legacy",
    "escape",
    "family_tradition",
    "prove_doubters_wrong",
    "artistic_expression",
    "fame",
    "competition",
]

TEMPERAMENTS = ["calm", "volatile", "anxious", "steady", "brooding", "cheerful"]

ORIGIN_TEMPLATES = [
    "Grew up in {hometown}, the {child_pos} of {family_size} siblings. {motivation_story}",
    "A {pre_career} from {hometown} who found wrestling after {turning_point}.",
    "Born into a wrestling family in {hometown}. The business is in their blood.",
    "Came from nothing in {hometown}. Wrestling was the only way out.",
    "{pre_career} turned wrestler. Left everything behind in {hometown} to chase the dream.",
    "Trained in a barn in {hometown}. Nobody gave them a chance. They took it anyway.",
]

TURNING_POINTS = [
    "a chance encounter at a local show",
    "losing everything in their previous career",
    "being told they'd never amount to anything",
    "watching wrestling as a kid and never letting go of the dream",
    "a friend dared them to try out at a local school",
    "recovering from a serious injury and needing a new purpose",
]

MOTIVATION_STORIES = {
    "passion": "Fell in love with wrestling watching late-night TV and never looked back.",
    "money": "Saw the paychecks and knew this was the ticket to a better life.",
    "legacy": "Determined to carry on the family name in the business.",
    "escape": "Wrestling was the way out of a life that was going nowhere.",
    "family_tradition": "Third generation. There was never really another option.",
    "prove_doubters_wrong": "Everyone said they couldn't. That was all the motivation they needed.",
    "artistic_expression": "Saw wrestling as storytelling with the body. An art form.",
    "fame": "Wanted to be known. Wanted the crowd. Wanted the spotlight.",
    "competition": "Needed to compete. Needed to win. Needed to be the best.",
}

ARCHETYPE_DESCRIPTIONS = {
    "monster_heel": "An unstoppable force of destruction who dominates opponents through sheer power and intimidation.",
    "underdog_face": "The scrappy fighter who never gives up, always finding a way back when all seems lost.",
    "cocky_technician": "A supremely skilled wrestler who knows exactly how good they are and makes sure everyone else does too.",
    "silent_assassin": "Says nothing, but their actions in the ring speak volumes. Clinical, efficient, terrifying.",
    "cult_leader": "A charismatic manipulator who draws followers with ideology and fear.",
    "comedy_act": "Entertainment incarnate. They might not win every match, but they always win the crowd.",
    "anti_hero": "Rejects labels. Fights for themselves. The crowd loves them anyway.",
    "legacy": "Carries the weight of a family name and the expectations that come with it.",
    "patriot": "Fights for something bigger than themselves. The people's champion.",
    "daredevil": "No fear, no limits. Will do anything to deliver the most spectacular moments.",
}

ARCHETYPE_VOICE_STYLES = {
    "monster_heel": {
        "vocabulary": "simple",
        "cadence": "slow_burn",
        "speech_patterns": ["growling", "short_sentences"],
        "promo_tempo": "menacing",
    },
    "underdog_face": {
        "vocabulary": "simple",
        "cadence": "emotional",
        "speech_patterns": ["passionate", "rising_intensity"],
        "promo_tempo": "building",
    },
    "cocky_technician": {
        "vocabulary": "elaborate",
        "cadence": "precise",
        "speech_patterns": ["condescending", "technical_references"],
        "promo_tempo": "controlled",
    },
    "silent_assassin": {
        "vocabulary": "minimal",
        "cadence": "staccato",
        "speech_patterns": ["whisper", "one_liners"],
        "promo_tempo": "sparse",
    },
    "cult_leader": {
        "vocabulary": "academic",
        "cadence": "hypnotic",
        "speech_patterns": ["preaching", "third_person"],
        "promo_tempo": "methodical",
    },
    "comedy_act": {
        "vocabulary": "street",
        "cadence": "rapid_fire",
        "speech_patterns": ["self_deprecating", "pop_culture"],
        "promo_tempo": "erratic",
    },
    "anti_hero": {
        "vocabulary": "street",
        "cadence": "conversational",
        "speech_patterns": ["profane", "honest"],
        "promo_tempo": "aggressive",
    },
    "legacy": {
        "vocabulary": "elaborate",
        "cadence": "measured",
        "speech_patterns": ["respectful", "tradition_invoking"],
        "promo_tempo": "dignified",
    },
    "patriot": {
        "vocabulary": "simple",
        "cadence": "rallying",
        "speech_patterns": ["inclusive", "motivational"],
        "promo_tempo": "aggressive",
    },
    "daredevil": {
        "vocabulary": "street",
        "cadence": "rapid_fire",
        "speech_patterns": ["excited", "cavalier"],
        "promo_tempo": "erratic",
    },
}

LIFE_EVENT_POOL = {
    "marriage": {
        "description": "{name} got married in a private ceremony.",
        "severity": 4,
        "morale": 15,
        "performance": 0,
        "public_chance": 0.6,
        "storyline_pot": False,
    },
    "divorce": {
        "description": "{name} is going through a divorce.",
        "severity": 7,
        "morale": -20,
        "performance": -5,
        "public_chance": 0.4,
        "storyline_pot": True,
    },
    "child_born": {
        "description": "{name} welcomed a new baby.",
        "severity": 5,
        "morale": 20,
        "performance": 0,
        "public_chance": 0.7,
        "storyline_pot": False,
    },
    "death_in_family": {
        "description": "{name} lost a close family member.",
        "severity": 9,
        "morale": -25,
        "performance": -10,
        "public_chance": 0.5,
        "storyline_pot": True,
    },
    "legal_trouble": {
        "description": "{name} is dealing with legal issues.",
        "severity": 6,
        "morale": -15,
        "performance": -3,
        "public_chance": 0.7,
        "storyline_pot": True,
    },
    "personal_achievement": {
        "description": "{name} achieved a personal milestone outside of wrestling.",
        "severity": 3,
        "morale": 10,
        "performance": 2,
        "public_chance": 0.8,
        "storyline_pot": False,
    },
    "substance_issue": {
        "description": "{name} has been struggling with substance abuse issues.",
        "severity": 8,
        "morale": -20,
        "performance": -15,
        "public_chance": 0.3,
        "storyline_pot": True,
    },
    "public_controversy": {
        "description": "{name} is at the center of a public controversy.",
        "severity": 6,
        "morale": -10,
        "performance": -2,
        "public_chance": 1.0,
        "storyline_pot": True,
    },
    "charity_work": {
        "description": "{name} made headlines for charitable work in their community.",
        "severity": 2,
        "morale": 10,
        "performance": 0,
        "public_chance": 0.9,
        "storyline_pot": False,
    },
    "outside_media": {
        "description": "{name} appeared on a mainstream media program.",
        "severity": 3,
        "morale": 5,
        "performance": 0,
        "public_chance": 1.0,
        "storyline_pot": False,
    },
    "financial_trouble": {
        "description": "{name} is reportedly dealing with financial difficulties.",
        "severity": 6,
        "morale": -15,
        "performance": -3,
        "public_chance": 0.3,
        "storyline_pot": True,
    },
    "mental_health": {
        "description": "{name} has been open about mental health challenges.",
        "severity": 7,
        "morale": -10,
        "performance": -5,
        "public_chance": 0.4,
        "storyline_pot": True,
    },
    "relationship_start": {
        "description": "{name} has entered a new relationship.",
        "severity": 3,
        "morale": 10,
        "performance": 0,
        "public_chance": 0.5,
        "storyline_pot": False,
    },
    "relationship_end": {
        "description": "{name} recently went through a breakup.",
        "severity": 5,
        "morale": -10,
        "performance": -2,
        "public_chance": 0.3,
        "storyline_pot": False,
    },
    "family_reconciliation": {
        "description": "{name} has reconnected with estranged family members.",
        "severity": 4,
        "morale": 15,
        "performance": 2,
        "public_chance": 0.4,
        "storyline_pot": False,
    },
}


# ---------------------------------------------------------------------------
# Backstory generation
# ---------------------------------------------------------------------------


def generate_backstory(db: Session, wrestler: GameWrestlerDB) -> WrestlerBackstoryDB:
    """Create a WrestlerBackstoryDB with randomized but coherent origin."""
    hometown = wrestler.hometown or "parts unknown"
    motivation = random.choice(MOTIVATIONS)
    pre_career = random.choice(PRE_WRESTLING_CAREERS)
    family_sit = random.choice(FAMILY_SITUATIONS)
    age = wrestler.age or 25

    # Adjust family situation by age
    if age < 23:
        family_sit = random.choice(["single", "close_family", "estranged_family"])

    template = random.choice(ORIGIN_TEMPLATES)
    origin_story = template.format(
        hometown=hometown,
        child_pos=random.choice(["oldest", "youngest", "middle", "only child"]),
        family_size=random.randint(1, 5),
        motivation_story=MOTIVATION_STORIES.get(motivation, ""),
        pre_career=pre_career.replace("_", " "),
        turning_point=random.choice(TURNING_POINTS),
    )

    # Generate real personality (distinct from character traits)
    real_personality = {
        "temperament": random.choice(TEMPERAMENTS),
        "introversion": random.randint(10, 90),
        "ambition": random.randint(30, 100),
        "ego": random.randint(10, 90),
        "substance_risk": random.randint(0, 50),
        "media_savvy": random.randint(10, 90),
    }

    backstory = WrestlerBackstoryDB(
        wrestler_id=wrestler.id,
        origin_story=origin_story,
        family_situation=family_sit,
        pre_wrestling_career=pre_career,
        wrestling_motivation=motivation,
        real_personality=real_personality,
        personal_struggles=[],
        personal_life_stability=random.randint(50, 85),
    )
    db.add(backstory)
    db.flush()
    return backstory


# ---------------------------------------------------------------------------
# Gimmick generation
# ---------------------------------------------------------------------------


def _pick_archetype(wrestler):
    """Pick an archetype based on existing wrestler attributes."""
    alignment = wrestler.alignment or "face"

    # Weighted selection based on alignment
    if alignment == "heel":
        weights = {
            "monster_heel": 25,
            "cocky_technician": 25,
            "silent_assassin": 15,
            "cult_leader": 15,
            "anti_hero": 10,
            "comedy_act": 5,
            "legacy": 3,
            "patriot": 1,
            "daredevil": 5,
            "underdog_face": 1,
        }
    elif alignment == "face":
        weights = {
            "underdog_face": 25,
            "patriot": 15,
            "legacy": 15,
            "daredevil": 15,
            "anti_hero": 10,
            "comedy_act": 10,
            "cocky_technician": 5,
            "monster_heel": 2,
            "silent_assassin": 2,
            "cult_leader": 1,
        }
    else:
        weights = {a: 10 for a in ARCHETYPES}
        weights["anti_hero"] = 30

    archetypes = list(weights.keys())
    w = [weights[a] for a in archetypes]
    return random.choices(archetypes, weights=w, k=1)[0]


def generate_initial_gimmick(
    db: Session, wrestler: GameWrestlerDB, game_date: str
) -> GimmickHistoryDB:
    """Create the initial GimmickHistoryDB from existing wrestler data."""
    archetype = _pick_archetype(wrestler)

    description = wrestler.gimmick or ARCHETYPE_DESCRIPTIONS.get(archetype, "")
    voice_style = ARCHETYPE_VOICE_STYLES.get(archetype, {}).copy()

    # Add wrestler's catchphrase to voice style
    if wrestler.catchphrase:
        voice_style["catchphrases"] = [wrestler.catchphrase]

    gimmick = GimmickHistoryDB(
        wrestler_id=wrestler.id,
        gimmick_name=wrestler.name,
        archetype=archetype,
        description=description,
        origin_narrative=f"Debuted as a {archetype.replace('_', ' ')}.",
        alignment=wrestler.alignment or "face",
        voice_style=voice_style,
        visual_identity={},
        start_date=game_date,
        depth_score=random.randint(20, 60),
        effectiveness=random.randint(30, 70),
        staleness=0,
        fan_investment=max(10, wrestler.popularity // 2),
        is_active=True,
    )
    db.add(gimmick)

    # Update wrestler's character depth
    wrestler.character_depth = gimmick.depth_score
    db.flush()
    return gimmick


# ---------------------------------------------------------------------------
# Life events
# ---------------------------------------------------------------------------


def generate_life_event(
    db: Session, wrestler_id: str, world_id: str, game_date: str
) -> LifeEventDB:
    """Randomly generate a life event (~3% chance per call).

    Event probability is weighted by persona traits.
    """
    if random.random() > 0.03:
        return None

    wrestler = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.id == wrestler_id,
        )
        .first()
    )
    if not wrestler:
        return None

    backstory = (
        db.query(WrestlerBackstoryDB)
        .filter(
            WrestlerBackstoryDB.wrestler_id == wrestler_id,
        )
        .first()
    )

    # Weight event types by persona
    real_personality = (backstory.real_personality if backstory else {}) or {}
    substance_risk = real_personality.get("substance_risk", 20)
    ambition = real_personality.get("ambition", 50)
    stability = (backstory.personal_life_stability if backstory else 70) or 70

    weights = {}
    for event_type, data in LIFE_EVENT_POOL.items():
        base_weight = 10
        if event_type == "substance_issue":
            base_weight = substance_risk // 5
        elif event_type == "personal_achievement":
            base_weight = ambition // 10
        elif event_type in ("divorce", "relationship_end"):
            base_weight = max(1, (100 - stability) // 10)
        elif event_type in ("marriage", "child_born", "relationship_start"):
            base_weight = stability // 10
        elif event_type == "financial_trouble":
            base_weight = max(1, (100 - stability) // 8)
        weights[event_type] = max(1, base_weight)

    event_type = random.choices(
        list(weights.keys()), weights=list(weights.values()), k=1
    )[0]
    template = LIFE_EVENT_POOL[event_type]

    is_public = random.random() < template["public_chance"]

    event = LifeEventDB(
        wrestler_id=wrestler_id,
        world_id=world_id,
        game_date=game_date,
        event_type=event_type,
        description=template["description"].format(name=wrestler.name),
        severity=template["severity"],
        is_public=is_public,
        morale_impact=template["morale"],
        performance_impact=template["performance"],
        storyline_potential=template["storyline_pot"],
        was_used_in_storyline=False,
        is_active=True,
    )
    db.add(event)
    db.flush()

    logger.info(
        "Life event '%s' for %s (public=%s)", event_type, wrestler.name, is_public
    )
    return event


def process_life_event_effects(db: Session, event: LifeEventDB):
    """Apply morale/performance deltas from a life event to the wrestler."""
    wrestler = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.id == event.wrestler_id,
        )
        .first()
    )
    if not wrestler:
        return

    # Apply morale impact (diminishing over time — event gets less fresh)
    if event.morale_impact:
        # Apply a fraction of the impact each tick (event is already active)
        delta = event.morale_impact // 4  # Spread over ~4 ticks
        wrestler.morale = max(0, min(100, wrestler.morale + delta))

    # Update backstory stability
    backstory = (
        db.query(WrestlerBackstoryDB)
        .filter(
            WrestlerBackstoryDB.wrestler_id == wrestler.id,
        )
        .first()
    )
    if backstory:
        if event.severity >= 7:
            backstory.personal_life_stability = max(
                0, backstory.personal_life_stability - event.severity
            )
        elif event.morale_impact > 0:
            backstory.personal_life_stability = min(
                100, backstory.personal_life_stability + 2
            )

    # Auto-resolve low-severity events after creation
    if event.severity <= 3:
        event.is_active = False


# ---------------------------------------------------------------------------
# Gimmick staleness & evolution
# ---------------------------------------------------------------------------


def tick_gimmick_staleness(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Increase gimmick staleness over time."""
    gimmick = (
        db.query(GimmickHistoryDB)
        .filter(
            GimmickHistoryDB.wrestler_id == wrestler.id,
            GimmickHistoryDB.is_active == True,
        )
        .first()
    )
    if not gimmick:
        return

    # Base staleness increase per week
    increment = 1

    # High popularity slows staleness
    if wrestler.popularity > 70:
        increment = max(0, increment - 1)

    # Low effectiveness accelerates it
    if gimmick.effectiveness < 30:
        increment += 1

    # High depth slows staleness (complex characters have more to explore)
    if gimmick.depth_score > 70:
        increment = max(0, increment - 1)

    gimmick.staleness = min(100, (gimmick.staleness or 0) + increment)

    # Staleness erodes effectiveness
    if gimmick.staleness > 60:
        gimmick.effectiveness = max(0, (gimmick.effectiveness or 50) - 1)


def check_repackaging_pressure(db: Session, wrestler: GameWrestlerDB) -> dict:
    """Check if a wrestler needs a gimmick change. Returns pressure score and reason."""
    gimmick = (
        db.query(GimmickHistoryDB)
        .filter(
            GimmickHistoryDB.wrestler_id == wrestler.id,
            GimmickHistoryDB.is_active == True,
        )
        .first()
    )
    if not gimmick:
        return {"pressure": 0, "reason": "no_gimmick"}

    pressure = 0
    reasons = []

    staleness = gimmick.staleness or 0
    effectiveness = gimmick.effectiveness or 50
    fan_investment = gimmick.fan_investment or 30

    if staleness > 70:
        pressure += 30
        reasons.append("stale_gimmick")
    if effectiveness < 25:
        pressure += 30
        reasons.append("ineffective_character")
    if fan_investment < 15:
        pressure += 20
        reasons.append("fans_lost_interest")
    if wrestler.popularity < 20:
        pressure += 20
        reasons.append("low_popularity")
    if wrestler.morale < 25:
        pressure += 10
        reasons.append("low_morale")

    reason = reasons[0] if reasons else "none"
    return {"pressure": min(100, pressure), "reason": reason}


def execute_gimmick_change(
    db: Session, wrestler: GameWrestlerDB, game_date: str, reason: str = None
) -> GimmickHistoryDB:
    """Retire current gimmick and create a new one."""
    # Retire current gimmick
    current = (
        db.query(GimmickHistoryDB)
        .filter(
            GimmickHistoryDB.wrestler_id == wrestler.id,
            GimmickHistoryDB.is_active == True,
        )
        .first()
    )

    old_name = None
    old_archetype = None
    if current:
        current.is_active = False
        current.end_date = game_date
        current.reason_for_change = reason or "repackaging"
        old_name = current.gimmick_name
        old_archetype = current.archetype

    # Pick a different archetype
    available = [a for a in ARCHETYPES if a != old_archetype]
    new_archetype = random.choice(available)

    voice_style = ARCHETYPE_VOICE_STYLES.get(new_archetype, {}).copy()

    new_gimmick = GimmickHistoryDB(
        wrestler_id=wrestler.id,
        gimmick_name=wrestler.name,  # Keep same ring name usually
        archetype=new_archetype,
        description=ARCHETYPE_DESCRIPTIONS.get(new_archetype, ""),
        origin_narrative=f"Reinvented as a {new_archetype.replace('_', ' ')} after {reason or 'creative direction'}.",
        alignment=wrestler.alignment,
        voice_style=voice_style,
        visual_identity={},
        start_date=game_date,
        depth_score=random.randint(20, 45),  # New gimmicks start less deep
        effectiveness=random.randint(40, 60),
        staleness=0,
        fan_investment=random.randint(20, 40),
        is_active=True,
    )
    db.add(new_gimmick)

    wrestler.gimmick_changes = (wrestler.gimmick_changes or 0) + 1
    wrestler.character_depth = new_gimmick.depth_score
    wrestler.gimmick = new_gimmick.description

    db.flush()

    # Generate news about the change
    try:
        from game_service.news_service import generate_gimmick_change_news

        generate_gimmick_change_news(
            db,
            wrestler.world_id,
            wrestler,
            old_name or "unknown",
            new_gimmick.gimmick_name,
            game_date,
        )
    except Exception as e:
        logger.warning("Failed to generate gimmick change news: %s", e)

    logger.info(
        "Gimmick change for %s: %s -> %s (%s)",
        wrestler.name,
        old_archetype,
        new_archetype,
        reason,
    )
    return new_gimmick


def evolve_gimmick(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Subtle gimmick evolution: adjust depth and fan investment based on activity."""
    gimmick = (
        db.query(GimmickHistoryDB)
        .filter(
            GimmickHistoryDB.wrestler_id == wrestler.id,
            GimmickHistoryDB.is_active == True,
        )
        .first()
    )
    if not gimmick:
        return

    # Depth grows slowly with matches and promos
    if wrestler.last_booked_date == game_date:
        gimmick.depth_score = min(100, (gimmick.depth_score or 40) + 1)

    # Fan investment follows popularity trends
    if wrestler.popularity > 60:
        gimmick.fan_investment = min(100, (gimmick.fan_investment or 30) + 1)
    elif wrestler.popularity < 30:
        gimmick.fan_investment = max(0, (gimmick.fan_investment or 30) - 1)

    # Update wrestler's character depth to match
    wrestler.character_depth = gimmick.depth_score


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------


def detect_collision_events(
    db: Session, wrestler: GameWrestlerDB, game_date: str
) -> list:
    """Detect when real life and kayfabe conflict for a wrestler.

    Returns list of collision dicts: {type, description, severity}.
    """
    collisions = []

    backstory = (
        db.query(WrestlerBackstoryDB)
        .filter(
            WrestlerBackstoryDB.wrestler_id == wrestler.id,
        )
        .first()
    )

    # 1. Personal crisis during active push
    active_events = (
        db.query(LifeEventDB)
        .filter(
            LifeEventDB.wrestler_id == wrestler.id,
            LifeEventDB.is_active == True,
            LifeEventDB.severity >= 7,
        )
        .all()
    )

    if active_events and wrestler.popularity > 60:
        collisions.append(
            {
                "type": "crisis_during_push",
                "description": f"{wrestler.name} is dealing with personal issues while in a top spot",
                "severity": max(e.severity for e in active_events),
            }
        )

    # 2. Real friends as kayfabe rivals
    rels = (
        db.query(WrestlerRelationshipDB)
        .filter(
            (
                (WrestlerRelationshipDB.wrestler1_id == wrestler.id)
                | (WrestlerRelationshipDB.wrestler2_id == wrestler.id)
            ),
        )
        .all()
    )

    for rel in rels:
        real = rel.real_relationship
        kayfabe = rel.kayfabe_alignment
        if real == "friends" and kayfabe == "rivals":
            other_id = (
                rel.wrestler2_id
                if rel.wrestler1_id == wrestler.id
                else rel.wrestler1_id
            )
            other = (
                db.query(GameWrestlerDB).filter(GameWrestlerDB.id == other_id).first()
            )
            if other:
                collisions.append(
                    {
                        "type": "friends_as_rivals",
                        "description": f"{wrestler.name} and {other.name} are real friends booked as enemies",
                        "severity": 5,
                    }
                )
        elif real == "enemies" and kayfabe in ("allies", "tag_partners"):
            other_id = (
                rel.wrestler2_id
                if rel.wrestler1_id == wrestler.id
                else rel.wrestler1_id
            )
            other = (
                db.query(GameWrestlerDB).filter(GameWrestlerDB.id == other_id).first()
            )
            if other:
                collisions.append(
                    {
                        "type": "enemies_as_allies",
                        "description": f"{wrestler.name} and {other.name} actually dislike each other but are booked as allies",
                        "severity": 7,
                    }
                )

    # 3. Low personal stability + high kayfabe commitment = strain
    if backstory:
        stability = backstory.personal_life_stability or 70
        commitment = wrestler.kayfabe_commitment or 50
        if stability < 30 and commitment > 70:
            collisions.append(
                {
                    "type": "facade_cracking",
                    "description": f"{wrestler.name}'s real life is falling apart but they're maintaining character",
                    "severity": 8,
                }
            )

    return collisions


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def migrate_existing_wrestlers(db: Session, world_id: str):
    """Populate backstory and gimmick for wrestlers that don't have them."""
    wrestlers = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.world_id == world_id,
            GameWrestlerDB.is_active == True,
        )
        .all()
    )

    count = 0
    for wrestler in wrestlers:
        backstory = (
            db.query(WrestlerBackstoryDB)
            .filter(
                WrestlerBackstoryDB.wrestler_id == wrestler.id,
            )
            .first()
        )
        if not backstory:
            generate_backstory(db, wrestler)
            count += 1

        gimmick = (
            db.query(GimmickHistoryDB)
            .filter(
                GimmickHistoryDB.wrestler_id == wrestler.id,
                GimmickHistoryDB.is_active == True,
            )
            .first()
        )
        if not gimmick:
            generate_initial_gimmick(db, wrestler, "migration")

    db.flush()
    logger.info("Migrated %d wrestlers with persona data in world %s", count, world_id)
    return count
