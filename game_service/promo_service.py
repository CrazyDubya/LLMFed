"""
Promo service - generates and evaluates wrestler promos.

In the full implementation, this will call an LLM to generate in-character
promos based on wrestler personality, storyline context, and player direction.
For now, it uses templates that produce varied promos based on stats.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    PromoDB, GameWrestlerDB, WrestlerStatsDB, StorylineDB,
    StorylineParticipantDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Promo templates
# ---------------------------------------------------------------------------

FACE_OPENERS = [
    "Let me tell you something, brother!",
    "I came here tonight for one reason and one reason only!",
    "The people in this arena deserve better!",
    "I've worked my entire life for this moment!",
    "You can knock me down, but you'll NEVER keep me down!",
]

HEEL_OPENERS = [
    "Shut your mouths, every single one of you!",
    "I am SICK and TIRED of carrying this company on my back!",
    "None of you deserve to be in the same ring as me!",
    "You people make me sick!",
    "I didn't come here to make friends!",
]

CHALLENGE_LINES = [
    "So {target}, if you've got any guts at all, get out here and face me!",
    "I'm calling you out, {target}! No more running!",
    "{target}, at the next show, I'm going to prove once and for all who the better wrestler is!",
    "You want this title, {target}? Come and take it... if you can!",
]

BOAST_LINES = [
    "I am the greatest competitor to ever step foot in this ring!",
    "Nobody in that locker room can lace my boots!",
    "I've beaten everyone there is to beat!",
    "I am a living, breathing LEGEND!",
]

UNDERDOG_LINES = [
    "They said I'd never make it. They said I wasn't good enough.",
    "I've been counted out my whole career, but I keep coming back!",
    "I don't care about the odds. I never have.",
    "Every scar on my body tells a story of survival!",
]

CLOSING_LINES = [
    "And that's the bottom line!",
    "Believe that!",
    "And there's nothing you can do about it!",
    "If you don't like it, too bad!",
    "Remember this moment!",
]


# ---------------------------------------------------------------------------
# Promo generation (template-based, LLM-ready)
# ---------------------------------------------------------------------------

def generate_promo(db: Session, world_id: str, wrestler_id: str,
                   target_wrestler_id: str = None,
                   promo_type: str = "in_ring",
                   player_direction: str = None,
                   game_date: str = None,
                   is_player_written: bool = False,
                   player_content: str = None) -> PromoDB:
    """Generate a promo for a wrestler.

    If player_content is provided, use that directly.
    Otherwise, generate from templates based on wrestler personality.
    """
    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        raise ValueError("Wrestler not found")

    stats = db.query(WrestlerStatsDB).filter(
        WrestlerStatsDB.wrestler_id == wrestler_id
    ).first()

    if player_content:
        content = player_content
    else:
        content = _generate_template_promo(wrestler, stats, target_wrestler_id, db)

    # Evaluate promo quality
    quality = _evaluate_promo_quality(stats, content, is_player_written)
    heat = _calculate_promo_heat(wrestler, quality, target_wrestler_id is not None)

    # Crowd reaction based on alignment
    if wrestler.alignment == "face":
        crowd = "pop" if quality >= 3.0 else "mild_pop"
    elif wrestler.alignment == "heel":
        crowd = "heat" if quality >= 3.0 else "mild_heat"
    else:
        crowd = "mixed"

    promo = PromoDB(
        world_id=world_id,
        wrestler_id=wrestler_id,
        content=content,
        target_wrestler_id=target_wrestler_id,
        promo_type=promo_type,
        crowd_reaction=crowd,
        heat_generated=heat,
        quality_rating=quality,
        game_date=game_date,
        is_player_written=is_player_written,
        player_direction=player_direction,
    )
    db.add(promo)
    db.flush()

    # Update wrestler popularity based on promo performance
    pop_change = int((quality - 2.5) * 2)
    wrestler.popularity = max(0, min(100, wrestler.popularity + pop_change))

    return promo


def _generate_template_promo(wrestler, stats, target_id, db):
    """Generate a promo from templates based on wrestler personality."""
    parts = []

    # Opener based on alignment
    if wrestler.alignment == "face":
        parts.append(random.choice(FACE_OPENERS))
    elif wrestler.alignment == "heel":
        parts.append(random.choice(HEEL_OPENERS))
    else:
        parts.append(random.choice(FACE_OPENERS + HEEL_OPENERS))

    # Middle section based on personality/stats
    charisma = stats.charisma if stats else 50
    if charisma > 70:
        parts.append(random.choice(BOAST_LINES))
    elif charisma < 30:
        parts.append(random.choice(UNDERDOG_LINES))
    else:
        parts.append(random.choice(BOAST_LINES + UNDERDOG_LINES))

    # Target callout
    if target_id:
        target = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == target_id
        ).first()
        if target:
            line = random.choice(CHALLENGE_LINES).format(target=target.name)
            parts.append(line)

    # Closer
    parts.append(random.choice(CLOSING_LINES))

    return " ".join(parts)


def _evaluate_promo_quality(stats, content: str, is_player: bool) -> float:
    """Rate a promo 0.0 - 5.0 based on wrestler stats and content."""
    mic = stats.mic_skill if stats else 50
    charisma = stats.charisma if stats else 50

    # Base quality from stats
    base = ((mic + charisma) / 2) / 100 * 3.5  # 0 - 3.5

    # Length bonus (longer promos that aren't too long)
    word_count = len(content.split())
    if 30 <= word_count <= 150:
        base += 0.5
    elif word_count > 150:
        base += 0.3

    # Player promos get a small creativity bonus
    if is_player:
        base += 0.3

    # Randomness factor
    base += random.uniform(-0.3, 0.5)

    return round(max(0.5, min(5.0, base)), 1)


def _calculate_promo_heat(wrestler, quality: float, has_target: bool) -> int:
    """Calculate heat (crowd reaction intensity) from a promo."""
    base = int(quality * 8)

    if has_target:
        base += random.randint(3, 8)

    if wrestler.alignment == "heel":
        base += 3  # Heels generate more heat

    if wrestler.popularity > 70:
        base += 5  # Popular wrestlers get bigger reactions

    return max(0, min(50, base + random.randint(-3, 3)))
