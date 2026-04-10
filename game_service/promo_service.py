"""
Promo service - generates and evaluates wrestler promos.

Uses the persona duality system: promos are shaped by the wrestler's gimmick
archetype, voice style, character depth, and real-life emotional state.
Falls back to alignment-based templates when persona data is unavailable.
"""

import os
import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    PromoDB, GameWrestlerDB, WrestlerStatsDB,
    GimmickHistoryDB, WrestlerBackstoryDB,
    LifeEventDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Promo constants
# ---------------------------------------------------------------------------

HIGH_CHARISMA_THRESHOLD = 70
LOW_CHARISMA_THRESHOLD = 30
QUALITY_MIN = 0.5
QUALITY_MAX = 5.0
HEAT_MIN = 0
HEAT_MAX = 50
HIGH_POPULARITY_THRESHOLD = 70
KAYFABE_BREAK_HEAT_CHANCE = 0.3
CATCHPHRASE_CHANCE = 0.4
WORKED_SHOOT_CHANCE = 0.15
LOW_KAYFABE_THRESHOLD = 30
EFFECTIVE_GIMMICK_THRESHOLD = 70
STALE_GIMMICK_THRESHOLD = 70
GOOD_CROWD_QUALITY = 3.0
STABLE_HEAT_PER_PROMO = 2
STAT_DEFAULT = 50


def _get_stat(stats, attr: str, default: int = STAT_DEFAULT) -> int:
    """Safely extract a stat value with default."""
    if not stats:
        return default
    return getattr(stats, attr, default)


def _get_target_wrestler(db, target_id):
    """Fetch target wrestler by ID, or None."""
    if not target_id:
        return None
    return db.query(GameWrestlerDB).filter(GameWrestlerDB.id == target_id).first()

# ---------------------------------------------------------------------------
# Legacy alignment-based templates (fallback)
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
# Archetype-specific promo templates
#
# ARCHETYPE_TEMPLATES consolidates openers/bodies/closers per archetype.
# Legacy accessors (ARCHETYPE_OPENERS, ARCHETYPE_BODIES, ARCHETYPE_CLOSERS)
# are derived from this single source of truth.
# ---------------------------------------------------------------------------

ARCHETYPE_TEMPLATES = {}  # populated below; maps archetype -> {openers, bodies, closers}

ARCHETYPE_OPENERS = {
    "monster_heel": [
        "...",
        "*stares silently at the crowd*",
        "You should be afraid.",
        "There is no escape.",
    ],
    "underdog_face": [
        "I know what everyone's thinking. 'There's no way.'",
        "I wasn't supposed to be here. Nobody gave me a chance.",
        "Every single person who told me I couldn't? They're watching right now.",
        "I've been knocked down more times than I can count.",
    ],
    "cocky_technician": [
        "Let me educate you people on something.",
        "I know more about wrestling in my little finger than this entire roster combined.",
        "This is a CLINIC, not a match.",
        "I'm not just better than you. I'm better than everyone who came before you.",
    ],
    "silent_assassin": [
        "*cold stare*",
        "...",
        "One word. Pain.",
    ],
    "cult_leader": [
        "My children... my flock... listen to me.",
        "The truth has been hidden from you. But I see it clearly.",
        "They want you blind. I want you awake.",
        "Follow me, and you will never walk in darkness again.",
    ],
    "comedy_act": [
        "So, funny story...",
        "Before I start — has anyone here ever tried to suplex a vending machine? No? Just me?",
        "I'm here, I'm weird, and I'm ready to party!",
        "Look, I know what you're thinking, and yes, I DID eat the catering.",
    ],
    "anti_hero": [
        "I'm not here to be your hero.",
        "You people want me to play nice? That's not how this works.",
        "I don't care about your rules. I don't care about your traditions.",
        "Here's the thing nobody wants to admit...",
    ],
    "legacy": [
        "My family built this business. And I'm not about to let it fall apart.",
        "I carry a name that means something in this industry.",
        "My father stood in this very ring. My grandfather built rings like this.",
        "This isn't just a career for me. This is my heritage.",
    ],
    "patriot": [
        "This one's for every single person watching at home!",
        "I fight for something bigger than myself!",
        "I represent every single one of you in this arena!",
        "There is NOTHING more powerful than fighting for what you believe in!",
    ],
    "daredevil": [
        "You know what I was doing before this match? Climbing the rafters. Just for fun.",
        "I don't have a plan. I never have a plan. That's what makes this FUN.",
        "They told me not to do it. So obviously, I'm gonna do it BIGGER.",
        "Pain? Pain's just the entrance fee for the best ride of your life.",
    ],
}

ARCHETYPE_BODIES = {
    "monster_heel": [
        "I don't wrestle. I destroy. There's a difference.",
        "Everyone who has stepped in this ring with me has learned the same lesson.",
        "Your heroes? I've broken them. Every. Single. One.",
    ],
    "underdog_face": [
        "I've worked harder than anyone in that locker room. And I'll do it again tonight.",
        "They can hit me with everything they've got. I'll still get back up.",
        "This isn't about talent. It's about heart. And nobody has more heart than me.",
    ],
    "cocky_technician": [
        "I've studied every counter, every reversal, every escape. There is no move I haven't mastered.",
        "While they were lifting weights, I was perfecting my craft.",
        "Wrestling is a science. And I have a PhD.",
    ],
    "silent_assassin": [
        "Actions speak.",
        "When I'm done, they don't get back up.",
    ],
    "cult_leader": [
        "The system is broken. The people in charge want you complacent. I offer... liberation.",
        "Every soul I've brought into my family has found purpose. Found meaning.",
        "They call me dangerous because the truth is always dangerous to liars.",
    ],
    "comedy_act": [
        "Look, I may not be the strongest, the fastest, or the smartest. But I am DEFINITELY the most entertaining.",
        "My finishing move is called 'The Surprise.' Because honestly, I'm as surprised as you are when I win.",
        "I've been training. I watched three whole YouTube tutorials this week.",
    ],
    "anti_hero": [
        "I'll fight anyone. Face. Heel. Management. The referee. I don't care.",
        "They want me to pick a side. I pick MY side.",
        "I'm not a good guy. I'm not a bad guy. I'm THE guy you don't want to cross.",
    ],
    "legacy": [
        "I've watched tapes of every match in my family's history. I carry that knowledge in this ring.",
        "The name I carry isn't just a name. It's a promise. A standard.",
        "I was born for this. Literally. This ring is my birthright.",
    ],
    "patriot": [
        "When I fight, I fight with the strength of everyone who believes in me!",
        "I've traveled the world, and I've never found anything stronger than the people here.",
        "They want to take what's ours? They'll have to go through ME first.",
    ],
    "daredevil": [
        "Last week I jumped off a twenty-foot ladder. Next week? Make it thirty.",
        "My body's held together with tape, dreams, and terrible decisions.",
        "They say I'm reckless. I say I'm LIVING.",
    ],
}

ARCHETYPE_CLOSERS = {
    "monster_heel": [
        "*drops the mic and walks away*",
        "Run.",
        "This is your only warning.",
    ],
    "underdog_face": [
        "And I will NEVER stop fighting!",
        "Tonight, we make history!",
        "For everyone who was ever told 'you can't' — watch me.",
    ],
    "cocky_technician": [
        "Class dismissed.",
        "You're welcome for the education.",
        "Take notes.",
    ],
    "silent_assassin": [
        "*exits in silence*",
        "Tick tock.",
    ],
    "cult_leader": [
        "Join us... or be consumed.",
        "The awakening is coming.",
        "Open your eyes.",
    ],
    "comedy_act": [
        "And THAT is why they pay me the medium bucks!",
        "Thank you, I'll be here all week! Literally, I live in the arena now.",
        "Goodnight everybody! ...Wait, the show's not over? Awkward.",
    ],
    "anti_hero": [
        "Deal with it.",
        "And if anyone has a problem with that, I'll be right here.",
        "Your move.",
    ],
    "legacy": [
        "For the family. For the legacy. Forever.",
        "The tradition continues.",
        "This chapter isn't over. It's just beginning.",
    ],
    "patriot": [
        "For all of you!",
        "Together, we are UNSTOPPABLE!",
        "God bless every one of you!",
    ],
    "daredevil": [
        "See you at the top... or the bottom. Either way, it'll be a RIDE!",
        "No fear. No limits. No regrets.",
        "Let's GO!",
    ],
}

# Build consolidated ARCHETYPE_TEMPLATES from the three separate dicts
for _arch in ARCHETYPE_OPENERS:
    ARCHETYPE_TEMPLATES[_arch] = {
        "openers": ARCHETYPE_OPENERS[_arch],
        "bodies": ARCHETYPE_BODIES.get(_arch, []),
        "closers": ARCHETYPE_CLOSERS.get(_arch, []),
    }

# Event type classifications for emotional state
NEGATIVE_LIFE_EVENT_TYPES = {
    "divorce", "death_in_family", "legal_trouble", "substance_issue",
    "financial_trouble", "mental_health", "public_controversy",
}
POSITIVE_LIFE_EVENT_TYPES = {
    "marriage", "child_born", "personal_achievement", "charity_work",
    "family_reconciliation",
}

# Emotional bleed thresholds
SEVERE_EVENT_THRESHOLD = 7
CATASTROPHIC_EVENT_THRESHOLD = 9
GRIEF_MORALE_IMPACT = -10
MIN_LLM_RESULT_LENGTH = 20
MIN_GOOD_PROMO_WORDS = 30
MAX_GOOD_PROMO_WORDS = 150

# Emotional modifiers when life events bleed into promos
EMOTIONAL_BLEED_LINES = {
    "grief": [
        "I've been going through something... something real. And it's given me a fire I didn't know I had.",
        "There are things happening outside this ring that put EVERYTHING in perspective.",
        "You think this match scares me? I've faced worse this week than anything you can throw at me.",
    ],
    "anger": [
        "I'm not in the mood for games tonight. Not tonight.",
        "Somebody backstage needs to hear this — I am DONE being patient.",
        "If you think I've been intense before, you haven't seen ANYTHING yet.",
    ],
    "joy": [
        "I'm on top of the world right now, and NOTHING is bringing me down!",
        "Life is good. And it's about to get even better.",
        "I've got something special waiting for me at home, and that makes me fight HARDER.",
    ],
    "desperation": [
        "I need this. I NEED this more than you'll ever understand.",
        "This isn't about titles or glory anymore. This is about survival.",
        "I've got nothing left to lose. And that makes me the most dangerous person in this building.",
    ],
}

# Faction/stable promo templates — delivered by the mouthpiece on behalf of the group
FACTION_PROMO_OPENERS = [
    "Let me tell you about {stable}.",
    "You're looking at the most dominant force in this company — {stable}.",
    "When {stable} walks into the building, everyone pays attention.",
    "The numbers don't lie, and {stable} has ALL the numbers.",
]

FACTION_PROMO_BODIES = [
    "We run this company. Every title, every main event, every decision — that's US.",
    "You want to challenge one of us? You challenge ALL of us. And there's no winning that fight.",
    "While the rest of the locker room fights over scraps, {stable} takes the whole feast.",
    "They call us a faction. We call ourselves a FAMILY. And family looks out for family.",
]

FACTION_PROMO_CLOSERS = [
    "So to anyone in the back thinking about stepping up — don't.",
    "This is OUR era. Accept it or get run over.",
    "4 life. *group pose*",
    "We're everywhere. We're everyone. And we're just getting started.",
]


# Worked-shoot promo fragments
WORKED_SHOOT_FRAGMENTS = [
    "You know what? I'm tired of reading scripts.",
    "This isn't a promo. This is ME talking.",
    "They told me not to say this, but I don't care anymore.",
    "You want real? HERE'S real.",
    "Forget the character. Forget the gimmick. I'm {real_name}, and I have something to say.",
    "Everyone in that locker room knows the truth. It's time the fans did too.",
    "I've been holding this in for months. Not anymore.",
]


# ---------------------------------------------------------------------------
# Promo generation (persona-aware, with legacy fallback)
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
    Otherwise, generate from archetype templates (with legacy fallback).
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
        content = _generate_persona_promo(wrestler, stats, target_wrestler_id, db, promo_type)

    # Evaluate promo quality
    gimmick = _get_current_gimmick(db, wrestler_id)
    quality = _evaluate_promo_quality(stats, content, is_player_written, gimmick)
    heat = _calculate_promo_heat(wrestler, quality, target_wrestler_id is not None)

    # Crowd reaction: persona-aware
    crowd = _determine_crowd_reaction(wrestler, quality, promo_type, gimmick)

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

    # Evolve gimmick effectiveness based on promo quality
    if gimmick:
        if quality >= 3.5:
            gimmick.effectiveness = min(100, gimmick.effectiveness + 1)
            gimmick.fan_investment = min(100, gimmick.fan_investment + 1)
        elif quality < 2.0:
            gimmick.effectiveness = max(0, gimmick.effectiveness - 1)

    return promo


def _get_current_gimmick(db, wrestler_id):
    """Get the wrestler's current active gimmick, if any."""
    return db.query(GimmickHistoryDB).filter(
        GimmickHistoryDB.wrestler_id == wrestler_id,
        GimmickHistoryDB.is_active == True,
    ).first()


def _get_active_life_events(db, wrestler_id):
    """Get active life events affecting the wrestler."""
    return db.query(LifeEventDB).filter(
        LifeEventDB.wrestler_id == wrestler_id,
        LifeEventDB.is_active == True,
    ).all()


def _determine_emotional_state(life_events, kayfabe_commitment):
    """Determine if real-life emotion bleeds into the promo."""
    if not life_events:
        return None

    # Higher kayfabe commitment = less bleed-through
    bleed_chance = max(0, (100 - kayfabe_commitment)) / 100.0

    severe_events = [e for e in life_events if e.severity >= SEVERE_EVENT_THRESHOLD]
    if not severe_events:
        return None

    if random.random() > bleed_chance:
        return None

    event = severe_events[0]

    if event.event_type in NEGATIVE_LIFE_EVENT_TYPES:
        if event.severity >= CATASTROPHIC_EVENT_THRESHOLD:
            return "desperation"
        elif event.morale_impact < GRIEF_MORALE_IMPACT:
            return "grief"
        else:
            return "anger"
    elif event.event_type in POSITIVE_LIFE_EVENT_TYPES:
        return "joy"
    return None


def _generate_persona_promo(wrestler, stats, target_id, db, promo_type):
    """Generate a promo using the persona duality system.

    Priority: LLM (if enabled) > archetype voice > emotional state > alignment fallback.
    """
    gimmick = _get_current_gimmick(db, wrestler.id)

    # LLM-as-character: the wrestler speaks for themselves
    if os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes"):
        try:
            from game_service.character_agent import character_speak
            target = _get_target_wrestler(db, target_id)
            target_name = target.name if target else ""

            # Build context that tells the character what the promo situation is
            context = f"You are cutting a {promo_type} promo in the ring."
            if target_name:
                context += f" You are calling out {target_name}."
            if wrestler.morale < 30:
                tone = "desperate"
            elif wrestler.popularity > 80:
                tone = "cocky"
            else:
                tone = "default"

            result = character_speak(db, wrestler.id, context, tone=tone)
            if result and len(result.strip()) > MIN_LLM_RESULT_LENGTH:
                return result
        except Exception:
            pass  # Fall through to template system

    # If no gimmick data, fall back to legacy system
    if not gimmick or gimmick.archetype not in ARCHETYPE_OPENERS:
        return _generate_template_promo(wrestler, stats, target_id, db)

    archetype = gimmick.archetype
    parts = []

    # Check for worked-shoot promo (low kayfabe commitment + high frustration/life events)
    if promo_type == "worked_shoot" or (
        wrestler.kayfabe_commitment < LOW_KAYFABE_THRESHOLD
        and random.random() < WORKED_SHOOT_CHANCE
    ):
        return _generate_worked_shoot_promo(wrestler, gimmick, target_id, db)

    # Check emotional bleed from life events
    life_events = _get_active_life_events(db, wrestler.id)
    emotional_state = _determine_emotional_state(
        life_events, wrestler.kayfabe_commitment
    )

    # Opener — archetype-specific
    parts.append(random.choice(ARCHETYPE_OPENERS[archetype]))

    # Emotional modifier if real life is bleeding through
    if emotional_state and emotional_state in EMOTIONAL_BLEED_LINES:
        parts.append(random.choice(EMOTIONAL_BLEED_LINES[emotional_state]))

    # Body — archetype-specific
    parts.append(random.choice(ARCHETYPE_BODIES[archetype]))

    # Catchphrase insertion if the gimmick has one
    voice = gimmick.voice_style or {}
    catchphrases = voice.get("catchphrases", [])
    if catchphrases and random.random() < CATCHPHRASE_CHANCE:
        parts.append(random.choice(catchphrases))

    # Target callout — still uses the universal challenge lines but flavored
    if target_id:
        target = _get_target_wrestler(db, target_id)
        if target:
            line = random.choice(CHALLENGE_LINES).format(target=target.name)
            parts.append(line)

    # Closer — archetype-specific
    parts.append(random.choice(ARCHETYPE_CLOSERS[archetype]))

    return " ".join(parts)


def _generate_worked_shoot_promo(wrestler, gimmick, target_id, db):
    """Generate a worked-shoot promo that blurs kayfabe lines."""
    parts = []

    real_name = wrestler.real_name or wrestler.name
    fragment = random.choice(WORKED_SHOOT_FRAGMENTS).format(real_name=real_name)
    parts.append(fragment)

    # Mix in real grievances
    life_events = _get_active_life_events(db, wrestler.id)
    if life_events:
        event = random.choice(life_events)
        if event.is_public:
            parts.append(f"Everyone knows what I've been dealing with. And instead of support, what do I get? More matches, more promos, more demands.")
    else:
        parts.append("I've given everything to this company. EVERYTHING. And what do I have to show for it?")

    if wrestler.morale < 40:
        parts.append("I'm tired. Not 'storyline tired.' Really, genuinely TIRED.")
    elif wrestler.popularity > 70:
        parts.append("I don't need this. I could walk out that door right now and every company in the world would be calling.")

    if target_id:
        target = _get_target_wrestler(db, target_id)
        if target:
            parts.append(f"And {target.name} — forget the storyline. You and I both know what this is really about.")

    parts.append("This is real. Whether you believe it or not.")

    # Track the kayfabe break
    wrestler.kayfabe_break_count = (wrestler.kayfabe_break_count or 0) + 1

    return " ".join(parts)


def _generate_template_promo(wrestler, stats, target_id, db):
    """Legacy: generate a promo from alignment-based templates."""
    parts = []

    if wrestler.alignment == "face":
        parts.append(random.choice(FACE_OPENERS))
    elif wrestler.alignment == "heel":
        parts.append(random.choice(HEEL_OPENERS))
    else:
        parts.append(random.choice(FACE_OPENERS + HEEL_OPENERS))

    charisma = _get_stat(stats, "charisma")
    if charisma > HIGH_CHARISMA_THRESHOLD:
        parts.append(random.choice(BOAST_LINES))
    elif charisma < LOW_CHARISMA_THRESHOLD:
        parts.append(random.choice(UNDERDOG_LINES))
    else:
        parts.append(random.choice(BOAST_LINES + UNDERDOG_LINES))

    if target_id:
        target = _get_target_wrestler(db, target_id)
        if target:
            line = random.choice(CHALLENGE_LINES).format(target=target.name)
            parts.append(line)

    parts.append(random.choice(CLOSING_LINES))

    return " ".join(parts)


def _evaluate_promo_quality(stats, content: str, is_player: bool,
                            gimmick=None) -> float:
    """Rate a promo 0.0 - 5.0 based on wrestler stats, content, and character depth."""
    mic = _get_stat(stats, "mic_skill")
    charisma = _get_stat(stats, "charisma")

    # Base quality from stats
    base = ((mic + charisma) / 2) / 100 * 3.5  # 0 - 3.5

    # Length bonus
    word_count = len(content.split())
    if MIN_GOOD_PROMO_WORDS <= word_count <= MAX_GOOD_PROMO_WORDS:
        base += 0.5
    elif word_count > MAX_GOOD_PROMO_WORDS:
        base += 0.3

    # Player promos get a small creativity bonus
    if is_player:
        base += 0.3

    # Gimmick depth bonus: deeper characters produce richer promos
    if gimmick:
        depth_bonus = (gimmick.depth_score or 0) / 100 * 0.5  # Up to +0.5
        base += depth_bonus

        # Effective gimmick bonus
        if (gimmick.effectiveness or 0) > EFFECTIVE_GIMMICK_THRESHOLD:
            base += 0.2

        # Stale gimmick penalty
        if (gimmick.staleness or 0) > STALE_GIMMICK_THRESHOLD:
            base -= 0.3

    # Randomness factor
    base += random.uniform(-0.3, 0.5)

    return round(max(QUALITY_MIN, min(QUALITY_MAX, base)), 1)


def _calculate_promo_heat(wrestler, quality: float, has_target: bool) -> int:
    """Calculate heat (crowd reaction intensity) from a promo."""
    base = int(quality * 8)

    if has_target:
        base += random.randint(3, 8)

    if wrestler.alignment == "heel":
        base += 3

    if wrestler.popularity > HIGH_POPULARITY_THRESHOLD:
        base += 5

    # Kayfabe breaks generate extra heat (pipe bomb effect)
    if (wrestler.kayfabe_break_count or 0) > 0 and random.random() < KAYFABE_BREAK_HEAT_CHANCE:
        base += random.randint(5, 15)

    return max(HEAT_MIN, min(HEAT_MAX, base + random.randint(-3, 3)))


def _determine_crowd_reaction(wrestler, quality, promo_type, gimmick):
    """Determine crowd reaction based on persona context."""
    # Worked shoots get special reactions
    if promo_type == "worked_shoot":
        if quality >= 3.5:
            return "stunned_silence_then_eruption"
        return "confused"

    # Anti-heroes always get mixed reactions
    if gimmick and gimmick.archetype == "anti_hero":
        return "mixed" if quality < GOOD_CROWD_QUALITY else "electric"

    # Comedy acts get unique reactions
    if gimmick and gimmick.archetype == "comedy_act":
        return "laughter" if quality >= 2.5 else "crickets"

    # Standard alignment-based reactions
    if wrestler.alignment == "face":
        return "pop" if quality >= GOOD_CROWD_QUALITY else "mild_pop"
    elif wrestler.alignment == "heel":
        return "heat" if quality >= GOOD_CROWD_QUALITY else "mild_heat"
    return "mixed"


# ---------------------------------------------------------------------------
# Faction / stable promos
# ---------------------------------------------------------------------------

def generate_faction_promo(
    db: Session,
    world_id: str,
    stable_id: str,
    speaker_wrestler_id: str,
    target_stable_name: str = None,
    game_date: str = None,
) -> dict:
    """Generate a promo on behalf of an entire faction.

    The speaker (usually the mouthpiece) delivers using stable identity.
    """
    from models.game_models import StableDB, StableMemberDB

    stable = db.query(StableDB).filter_by(id=stable_id).first()
    speaker = db.query(GameWrestlerDB).filter_by(id=speaker_wrestler_id).first()
    if not stable or not speaker:
        return {"content": "", "quality": 0, "heat": 0}

    stable_name = stable.name

    opener = random.choice(FACTION_PROMO_OPENERS).format(stable=stable_name)
    body = random.choice(FACTION_PROMO_BODIES).format(stable=stable_name)
    closer = random.choice(FACTION_PROMO_CLOSERS).format(stable=stable_name)

    # Add target stable reference
    target_line = ""
    if target_stable_name:
        target_lines = [
            f"And to {target_stable_name} — your days are numbered.",
            f"{target_stable_name} thinks they run this place? They're about to find out who REALLY runs things.",
            f"We've been watching {target_stable_name}. And we're not impressed.",
        ]
        target_line = " " + random.choice(target_lines)

    content = f"{opener} {body}{target_line} {closer}"

    # Quality from speaker's stats
    stats = db.query(WrestlerStatsDB).filter_by(wrestler_id=speaker_wrestler_id).first()
    mic = _get_stat(stats, "mic_skill")
    charisma = _get_stat(stats, "charisma")
    quality = round(((mic + charisma) / 2) / 100 * 4.0 + random.uniform(-0.3, 0.5), 1)
    quality = max(QUALITY_MIN, min(QUALITY_MAX, quality))

    heat = int(quality * 8 + stable.heat * 0.2 + random.randint(0, 10))
    heat = min(HEAT_MAX, heat)

    # Boost stable heat
    stable.heat = min(100, stable.heat + STABLE_HEAT_PER_PROMO)

    return {
        "content": content,
        "speaker_name": speaker.name,
        "stable_name": stable_name,
        "target_stable": target_stable_name,
        "quality_rating": quality,
        "heat_generated": heat,
    }
