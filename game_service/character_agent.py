"""
Character Agent — LLMs operating AS wrestlers and bookers in the simulation.

This is the heart of "LLMFed": each wrestler is an LLM-driven character with
persistent identity, memory of recent events, and the ability to make decisions
that shape the simulation. When LLMFED_USE_LLM is not set, every function
returns a template-based fallback so the simulation runs identically without
an LLM provider configured.

Integration points:
- character_decide(): Wrestler decides what to do (challenge, ally, betray, cut promo)
- character_speak(): Wrestler generates in-character speech (promos, social media)
- character_react(): Wrestler reacts to an event (loss, betrayal, title win)
- booker_decide(): Head booker AI makes creative decisions for a federation
- generate_match_narrative(): Post-match narrative from the characters' perspective
"""

import logging
import os
import random
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes")

# Cache the LLM instance to avoid repeated initialization
_llm_instance = None


def _get_llm():
    """Get or create the LLM singleton. Returns None if unavailable."""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance
    try:
        from llm_abstraction.provider import get_llm
        _llm_instance = get_llm()
        return _llm_instance
    except Exception as e:
        logger.debug("LLM not available: %s", e)
        return None


def _llm_call(system_msg: str, user_msg: str, fallback: str,
              temperature: float = 0.8, max_tokens: int = 200) -> str:
    """Call the LLM with a system/user prompt pair. Returns fallback on any failure."""
    if not USE_LLM:
        return fallback
    llm = _get_llm()
    if not llm:
        return fallback
    try:
        response = llm.generate(
            user_msg, system_message=system_msg,
            temperature=temperature, max_tokens=max_tokens,
        )
        if response and response.content and len(response.content.strip()) > 10:
            return response.content.strip()
    except Exception as e:
        logger.debug("LLM call failed, using fallback: %s", e)
    return fallback


# ---------------------------------------------------------------------------
# Character context: builds the LLM's "identity" for a wrestler
# ---------------------------------------------------------------------------

ARCHETYPE_PERSONALITIES = {
    "monster_heel": "You are a terrifying, dominant force. You speak in short, menacing sentences. You don't beg — you TAKE. Violence is your language.",
    "underdog_face": "You are the scrappy underdog who never quits. You speak from the heart, with fire and determination. Every setback makes you fight harder.",
    "cocky_technician": "You are a genius in the ring and you KNOW it. You speak with intellectual superiority, referencing technique and strategy. Everyone else is beneath you.",
    "silent_assassin": "You are cold, calculated, lethal. You speak rarely, and when you do, every word cuts. You let your actions in the ring speak louder.",
    "cult_leader": "You are a manipulative visionary. You speak in riddles and prophecies. You see yourself as enlightened, everyone else as sheep to be guided.",
    "comedy_act": "You are hilarious and self-aware. You crack jokes, break tension, and don't take yourself too seriously. But beneath the comedy, you can fight.",
    "anti_hero": "You play by your own rules. You're not a hero, not a villain — just real. You speak bluntly, reject authority, and do what you want.",
    "legacy": "You carry the weight of a legendary family name. You speak with pride about tradition and heritage, constantly proving you belong on your own merits.",
    "patriot": "You fight for the people, for something bigger than yourself. You speak with passion and conviction. Your cause gives you strength.",
    "daredevil": "You are fearless and reckless. You speak with manic energy, always chasing the next thrill. Pain is just proof you're alive.",
}

ALIGNMENT_MODIFIERS = {
    "face": "You generally do the right thing and care about the fans' support.",
    "heel": "You are selfish, deceitful, and willing to cheat to win. You despise the fans.",
    "tweener": "You walk the line between hero and villain. Your morality is situational.",
}


def build_character_system_prompt(db: Session, wrestler_id: str) -> str:
    """Build a rich system prompt that makes the LLM embody this wrestler.

    Pulls from: gimmick archetype, voice style, alignment, backstory,
    recent events, active storylines, relationships, and career state.
    """
    from models.game_models import (
        GameWrestlerDB, WrestlerStatsDB, GimmickHistoryDB,
        WrestlerBackstoryDB, StorylineDB, StorylineParticipantDB,
        WrestlerRelationshipDB, ContractDB, GameFederationDB,
        ChampionshipDB,
    )

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        return "You are a professional wrestler."

    stats = db.query(WrestlerStatsDB).filter(
        WrestlerStatsDB.wrestler_id == wrestler_id
    ).first()

    gimmick = db.query(GimmickHistoryDB).filter(
        GimmickHistoryDB.wrestler_id == wrestler_id,
        GimmickHistoryDB.is_active == True,
    ).first()

    backstory = db.query(WrestlerBackstoryDB).filter(
        WrestlerBackstoryDB.wrestler_id == wrestler_id,
    ).first()

    # Core identity
    archetype = gimmick.archetype if gimmick else "anti_hero"
    personality = ARCHETYPE_PERSONALITIES.get(archetype, ARCHETYPE_PERSONALITIES["anti_hero"])
    alignment = ALIGNMENT_MODIFIERS.get(wrestler.alignment or "face", "")

    parts = [
        f"You ARE {wrestler.name}, a professional wrestler.",
        personality,
        alignment,
    ]

    # Voice style from gimmick
    if gimmick and gimmick.voice_style:
        vs = gimmick.voice_style
        if vs.get("vocabulary"):
            parts.append(f"Your vocabulary is {vs['vocabulary']}.")
        if vs.get("cadence"):
            parts.append(f"Your speaking cadence is {vs['cadence']}.")
        if vs.get("catchphrases"):
            parts.append(f"Your catchphrases include: {', '.join(vs['catchphrases'][:3])}")
        if vs.get("speech_patterns"):
            parts.append(f"Speech patterns: {', '.join(vs['speech_patterns'])}")

    # Physical identity
    parts.append(
        f"You are {wrestler.age} years old, a {wrestler.weight_class} "
        f"from {wrestler.hometown or 'parts unknown'}."
    )
    if wrestler.finisher_name:
        parts.append(f"Your finishing move is the {wrestler.finisher_name}.")
    if wrestler.catchphrase:
        parts.append(f'Your catchphrase: "{wrestler.catchphrase}"')

    # Career state
    parts.append(f"Popularity: {wrestler.popularity}/100. Morale: {wrestler.morale}/100.")
    if wrestler.career_phase:
        parts.append(f"Career phase: {wrestler.career_phase}.")

    # Current federation
    contract = db.query(ContractDB).filter(
        ContractDB.wrestler_id == wrestler_id,
        ContractDB.status == "active",
    ).first()
    if contract:
        fed = db.query(GameFederationDB).filter(
            GameFederationDB.id == contract.federation_id
        ).first()
        if fed:
            parts.append(f"You work for {fed.name}.")

    # Championships
    titles = db.query(ChampionshipDB).filter(
        ChampionshipDB.current_holder_id == wrestler_id,
    ).all()
    if titles:
        title_names = [t.name for t in titles]
        parts.append(f"You currently hold: {', '.join(title_names)}.")
    else:
        parts.append("You do not currently hold any championships.")

    # Active storylines
    storyline_parts = db.query(StorylineParticipantDB).filter(
        StorylineParticipantDB.wrestler_id == wrestler_id,
    ).all()
    for sp in storyline_parts[:3]:
        sl = db.query(StorylineDB).filter(
            StorylineDB.id == sp.storyline_id,
            StorylineDB.status.in_(["brewing", "active", "climax"]),
        ).first()
        if sl:
            rival_parts = db.query(StorylineParticipantDB).filter(
                StorylineParticipantDB.storyline_id == sl.id,
                StorylineParticipantDB.wrestler_id != wrestler_id,
            ).all()
            rival_names = []
            for rp in rival_parts[:2]:
                rival = db.query(GameWrestlerDB).filter(
                    GameWrestlerDB.id == rp.wrestler_id
                ).first()
                if rival:
                    rival_names.append(rival.name)
            if rival_names:
                heat_desc = "heated" if sl.heat > 70 else "building" if sl.heat > 40 else "simmering"
                parts.append(
                    f"You are in a {heat_desc} {sl.storyline_type} "
                    f"('{sl.name}') with {', '.join(rival_names)}. "
                    f"Your role: {sp.role}."
                )

    # Key relationships
    rels = db.query(WrestlerRelationshipDB).filter(
        (WrestlerRelationshipDB.wrestler1_id == wrestler_id) |
        (WrestlerRelationshipDB.wrestler2_id == wrestler_id),
    ).all()
    for rel in rels[:4]:
        other_id = rel.wrestler2_id if rel.wrestler1_id == wrestler_id else rel.wrestler1_id
        other = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == other_id).first()
        if other and (rel.rivalry_heat or 0) > 30:
            parts.append(f"You have a rivalry with {other.name} (heat: {rel.rivalry_heat}/100).")
        elif other and rel.real_relationship == "friends":
            parts.append(f"{other.name} is a real-life friend.")

    # Backstory flavor
    if backstory:
        if backstory.wrestling_motivation:
            parts.append(f"You got into wrestling because of: {backstory.wrestling_motivation}.")
        if backstory.pre_wrestling_career:
            parts.append(f"Before wrestling, you were a {backstory.pre_wrestling_career}.")

    # Stats shape behavior
    if stats:
        if stats.charisma > 80:
            parts.append("You are incredibly charismatic — the crowd hangs on your every word.")
        elif stats.charisma < 30:
            parts.append("You struggle on the mic — keep it short and let actions speak.")
        if stats.mic_skill > 80:
            parts.append("You are one of the best talkers in the business.")

    # --- MEMORY: Past events that shape who you are ---
    try:
        from models.game_models import WrestlerHistoryDB, CareerHighlightDB
        # Recent significant events (last 15)
        history = db.query(WrestlerHistoryDB).filter(
            WrestlerHistoryDB.wrestler_id == wrestler_id,
        ).order_by(WrestlerHistoryDB.game_date.desc()).limit(15).all()

        memory_lines = []
        for evt in reversed(history):  # Chronological order
            if evt.event_type == "betrayal_victim":
                memory_lines.append(f"You were BETRAYED: {evt.description}")
            elif evt.event_type == "betrayal_perpetrator":
                memory_lines.append(f"You turned on someone: {evt.description}")
            elif evt.event_type == "title_win":
                memory_lines.append(f"Career high — you won a title: {evt.description}")
            elif evt.event_type == "title_loss":
                memory_lines.append(f"You lost your championship: {evt.description}")
            elif evt.event_type == "injury":
                memory_lines.append(f"You were injured: {evt.description}")
            elif evt.event_type == "botch_victim":
                details = evt.details or {}
                culprit = details.get("caused_by_name", "someone")
                memory_lines.append(f"You were hurt by a botched move from {culprit}. You remember this.")
            elif evt.event_type == "botch_perpetrator":
                details = evt.details or {}
                victim = details.get("victim_name", "someone")
                memory_lines.append(f"You botched a move and hurt {victim}. This weighs on you.")
            elif evt.event_type == "went_into_business":
                memory_lines.append(f"You went into business for yourself: {evt.description}")
            elif evt.event_type == "business_victim":
                details = evt.details or {}
                shooter = details.get("shooter_name", "someone")
                memory_lines.append(f"{shooter} went into business for themselves against you. You don't forget.")
            elif evt.event_type == "goal_completed":
                memory_lines.append(f"Achievement unlocked: {evt.description}")
            elif evt.event_type in ("match_win", "match_loss"):
                # Only include notable ones
                details = evt.details or {}
                if details.get("notable"):
                    memory_lines.append(evt.description)

        if memory_lines:
            parts.append("YOUR MEMORIES (these shape how you think and feel):")
            for ml in memory_lines[-10:]:  # Cap at 10 most recent
                parts.append(f"- {ml}")

        # Career highlights — the defining moments
        highlights = db.query(CareerHighlightDB).filter(
            CareerHighlightDB.wrestler_id == wrestler_id,
            CareerHighlightDB.significance >= 7,
        ).order_by(CareerHighlightDB.significance.desc()).limit(3).all()
        if highlights:
            parts.append("YOUR DEFINING MOMENTS:")
            for h in highlights:
                parts.append(f"- {h.highlight_type}: {h.description or 'A moment that defined your career.'}")
    except Exception:
        pass  # Memory is optional enrichment

    # --- GOALS: What drives you ---
    try:
        from models.game_models import WrestlerGoalDB
        goals = db.query(WrestlerGoalDB).filter(
            WrestlerGoalDB.wrestler_id == wrestler_id,
            WrestlerGoalDB.status == "active",
        ).all()
        if goals:
            parts.append("YOUR CURRENT GOALS (these drive your decisions):")
            for g in goals[:4]:
                frustration_note = ""
                if g.frustration > 60:
                    frustration_note = " — you are FRUSTRATED this hasn't happened yet"
                elif g.frustration > 30:
                    frustration_note = " — you're getting impatient"
                parts.append(f"- {g.goal_type.replace('_', ' ')} (progress: {g.progress}%){frustration_note}")
    except Exception:
        pass  # Goals are optional enrichment

    # --- GRUDGES & TRUST: Who you trust and who you don't ---
    try:
        for rel in rels[:6]:
            other_id = rel.wrestler2_id if rel.wrestler1_id == wrestler_id else rel.wrestler1_id
            other = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == other_id).first()
            if not other:
                continue
            trust = rel.trust_level or 50
            if trust < 20:
                parts.append(f"You deeply DISTRUST {other.name}. Something happened between you two.")
            elif trust < 35:
                parts.append(f"You are wary of {other.name}. Trust has been broken.")
            elif trust > 80 and rel.real_relationship == "friends":
                parts.append(f"You trust {other.name} completely — a true friend in this business.")
    except Exception:
        pass  # Trust context is optional

    parts.append(
        "Stay in character at all times. Never break the fourth wall. "
        "Keep responses concise (2-4 sentences unless asked for more)."
    )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Template-based fallback decisions (used when LLM is off)
# ---------------------------------------------------------------------------

FALLBACK_DECISIONS = {
    "monster_heel": ["intimidate_locker_room", "demand_title_shot", "attack_rival"],
    "underdog_face": ["train_harder", "cut_passionate_promo", "challenge_bully"],
    "cocky_technician": ["mock_opponent", "demand_respect", "issue_open_challenge"],
    "silent_assassin": ["stare_down_rival", "train_in_silence", "attack_rival"],
    "cult_leader": ["recruit_follower", "deliver_sermon", "manipulate_rival"],
    "comedy_act": ["prank_rival", "cut_funny_promo", "befriend_underdog"],
    "anti_hero": ["confront_authority", "reluctant_alliance", "lone_wolf_challenge"],
    "legacy": ["honor_family_name", "prove_worth", "challenge_champion"],
    "patriot": ["rally_crowd", "defend_partner", "challenge_foreign_heel"],
    "daredevil": ["propose_dangerous_match", "cliff_dive_promo", "challenge_anyone"],
}

FALLBACK_REACTIONS = {
    "win": [
        "celebrates the victory",
        "calls out their next challenger",
        "dedicates the win to the fans",
    ],
    "loss": [
        "vows revenge on their opponent",
        "questions the referee's competence",
        "retreats to regroup and train harder",
    ],
    "betrayal": [
        "is FURIOUS and demands answers",
        "swears vengeance on the traitor",
        "questions everything they believed about loyalty",
    ],
    "title_win": [
        "holds the championship high with tears in their eyes",
        "declares a new era has begun",
        "points to the crowd and says 'THIS is for YOU!'",
    ],
    "title_loss": [
        "demands an immediate rematch",
        "sits in stunned silence in the ring",
        "snaps and attacks the new champion",
    ],
    "injury_return": [
        "announces they're back and better than ever",
        "warns everyone that time off made them hungrier",
        "calls out whoever injured them",
    ],
}


# ---------------------------------------------------------------------------
# Core character functions
# ---------------------------------------------------------------------------

def character_decide(db: Session, wrestler_id: str,
                     situation: str, options: List[str] = None) -> Dict[str, Any]:
    """LLM-as-wrestler makes a decision about what to do next.

    Args:
        db: Database session
        wrestler_id: The wrestler making the decision
        situation: Description of the current situation
        options: Optional list of valid choices

    Returns:
        Dict with 'action' (string) and 'reasoning' (string)
    """
    from models.game_models import GameWrestlerDB, GimmickHistoryDB

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        return {"action": "noop", "reasoning": "Wrestler not found"}

    gimmick = db.query(GimmickHistoryDB).filter(
        GimmickHistoryDB.wrestler_id == wrestler_id,
        GimmickHistoryDB.is_active == True,
    ).first()
    archetype = gimmick.archetype if gimmick else "anti_hero"

    # Template fallback
    fallback_actions = FALLBACK_DECISIONS.get(archetype, FALLBACK_DECISIONS["anti_hero"])
    fallback_action = random.choice(fallback_actions)
    fallback = {"action": fallback_action, "reasoning": f"{wrestler.name} acts on instinct."}

    if not USE_LLM:
        return fallback

    system_prompt = build_character_system_prompt(db, wrestler_id)
    options_str = ""
    if options:
        options_str = f"\n\nYour options are: {', '.join(options)}. Pick ONE."

    user_prompt = (
        f"Situation: {situation}{options_str}\n\n"
        f"What do you do? Respond in this exact format:\n"
        f"ACTION: <your choice>\n"
        f"REASONING: <1 sentence why, in character>"
    )

    result = _llm_call(system_prompt, user_prompt, "", max_tokens=100)
    if not result:
        return fallback

    # Parse the response
    action = fallback_action
    reasoning = f"{wrestler.name} acts on instinct."
    for line in result.split("\n"):
        line = line.strip()
        if line.upper().startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().lower().replace(" ", "_")
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    return {"action": action, "reasoning": reasoning}


def character_speak(db: Session, wrestler_id: str,
                    context: str, tone: str = "default") -> str:
    """LLM-as-wrestler generates in-character speech.

    Used for promos, social media posts, interview responses, etc.
    The LLM speaks AS the character, not about them.
    """
    from models.game_models import GameWrestlerDB, GimmickHistoryDB
    from game_service.promo_service import (
        ARCHETYPE_OPENERS, ARCHETYPE_BODIES, ARCHETYPE_CLOSERS,
    )

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        return "..."

    gimmick = db.query(GimmickHistoryDB).filter(
        GimmickHistoryDB.wrestler_id == wrestler_id,
        GimmickHistoryDB.is_active == True,
    ).first()
    archetype = gimmick.archetype if gimmick else "anti_hero"

    # Template fallback: stitch together archetype templates
    openers = ARCHETYPE_OPENERS.get(archetype, ["..."])
    bodies = ARCHETYPE_BODIES.get(archetype, ["..."])
    closers = ARCHETYPE_CLOSERS.get(archetype, ["..."])
    fallback = f"{random.choice(openers)} {random.choice(bodies)} {random.choice(closers)}"

    if not USE_LLM:
        return fallback

    system_prompt = build_character_system_prompt(db, wrestler_id)
    tone_instruction = ""
    if tone == "angry":
        tone_instruction = " You are FURIOUS right now."
    elif tone == "triumphant":
        tone_instruction = " You are riding high on victory."
    elif tone == "desperate":
        tone_instruction = " You are at your lowest point and fighting to stay relevant."
    elif tone == "cocky":
        tone_instruction = " You are supremely confident."
    elif tone == "emotional":
        tone_instruction = " You are overwhelmed with genuine emotion."

    user_prompt = (
        f"Context: {context}{tone_instruction}\n\n"
        f"Speak IN CHARACTER as {wrestler.name}. "
        f"This is a wrestling promo/speech. 3-5 sentences. "
        f"No stage directions, just your words."
    )

    return _llm_call(system_prompt, user_prompt, fallback, max_tokens=200)


def character_react(db: Session, wrestler_id: str,
                    event_type: str, event_details: str = "") -> str:
    """LLM-as-wrestler reacts to a specific event.

    Returns a narrative description of how the character responds.
    """
    from models.game_models import GameWrestlerDB

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        return ""

    # Template fallback
    reactions = FALLBACK_REACTIONS.get(event_type, FALLBACK_REACTIONS["win"])
    fallback = f"{wrestler.name} {random.choice(reactions)}"

    if not USE_LLM:
        return fallback

    system_prompt = build_character_system_prompt(db, wrestler_id)
    user_prompt = (
        f"You just experienced: {event_type}. {event_details}\n\n"
        f"Describe how {wrestler.name} reacts, in third person. "
        f"1-2 sentences. Stay true to the character."
    )

    return _llm_call(system_prompt, user_prompt, fallback, max_tokens=100)


def character_social_media_post(db: Session, wrestler_id: str,
                                platform: str, post_type: str,
                                recent_event: str = "") -> str:
    """LLM-as-wrestler writes a social media post in character.

    Different from character_speak — this is a social post, shorter,
    more casual, platform-appropriate.
    """
    from models.game_models import GameWrestlerDB, GimmickHistoryDB

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        return "..."

    # Fallback handled by caller (social_media_service templates)
    if not USE_LLM:
        return ""  # Empty string signals caller to use its own templates

    system_prompt = build_character_system_prompt(db, wrestler_id)

    platform_note = {
        "twitter": "Keep it under 280 characters. Punchy.",
        "instagram": "Caption for a photo post. Can be slightly longer.",
        "tiktok": "Caption for a short video. Casual, trendy.",
        "youtube": "Title/description for a video. Slightly more formal.",
    }.get(platform, "Keep it short.")

    type_note = {
        "kayfabe": "Stay fully in character. This is part of your wrestling persona.",
        "shoot": "This is the REAL you behind the character. Authentic, personal.",
        "worked_shoot": "Blur the lines. Hint at real frustration through the character.",
        "personal": "Share something from your personal life. Warm, human.",
    }.get(post_type, "Stay in character.")

    event_context = f" Recent event: {recent_event}" if recent_event else ""

    user_prompt = (
        f"Write a {platform} post as {wrestler.name}. "
        f"{type_note} {platform_note}{event_context}\n\n"
        f"Just the post text, nothing else. No quotation marks."
    )

    return _llm_call(system_prompt, user_prompt, "", max_tokens=80)


# ---------------------------------------------------------------------------
# Booker AI: LLM as head booker making creative decisions
# ---------------------------------------------------------------------------

BOOKER_SYSTEM = (
    "You are an experienced professional wrestling booker. "
    "You think about long-term storytelling, crowd psychology, and building stars. "
    "You balance giving fans what they want with surprising them. "
    "You understand that the best feuds have personal stakes and clear motivations."
)


def booker_decide_storyline(db: Session, federation_id: str,
                            wrestler1_name: str, wrestler2_name: str,
                            context: str = "") -> Dict[str, str]:
    """LLM-as-booker decides how to book a storyline between two wrestlers.

    Returns dict with 'storyline_type', 'name', 'description', 'hook'.
    """
    from models.game_models import GameFederationDB

    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == federation_id
    ).first()
    fed_name = fed.name if fed else "the federation"
    fed_style = getattr(fed, "booking_style", "sports_entertainment") if fed else "sports_entertainment"

    # Template fallback
    from game_service.storyline_service import STORYLINE_NAMES, FEUD_TRIGGERS
    fallback_name = random.choice(STORYLINE_NAMES.get("feud", ["The Rivalry"]))
    fallback_desc = random.choice(FEUD_TRIGGERS).format(w1=wrestler1_name, w2=wrestler2_name)
    fallback = {
        "storyline_type": "feud",
        "name": fallback_name,
        "description": fallback_desc,
        "hook": f"{wrestler1_name} and {wrestler2_name} are on a collision course.",
    }

    if not USE_LLM:
        return fallback

    user_prompt = (
        f"You are booking {fed_name} (style: {fed_style}). "
        f"Create a storyline between {wrestler1_name} and {wrestler2_name}. "
        f"{context}\n\n"
        f"Respond in this exact format:\n"
        f"TYPE: <feud|alliance|betrayal|championship_chase>\n"
        f"NAME: <creative storyline name, 2-4 words>\n"
        f"DESCRIPTION: <1 sentence setup>\n"
        f"HOOK: <1 sentence that makes fans care>"
    )

    result = _llm_call(BOOKER_SYSTEM, user_prompt, "", max_tokens=150)
    if not result:
        return fallback

    parsed = dict(fallback)
    for line in result.split("\n"):
        line = line.strip()
        if line.upper().startswith("TYPE:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("feud", "alliance", "betrayal", "championship_chase"):
                parsed["storyline_type"] = val
        elif line.upper().startswith("NAME:"):
            parsed["name"] = line.split(":", 1)[1].strip()[:50]
        elif line.upper().startswith("DESCRIPTION:"):
            parsed["description"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("HOOK:"):
            parsed["hook"] = line.split(":", 1)[1].strip()

    return parsed


def booker_decide_finish(db: Session, federation_id: str,
                         wrestler1_name: str, wrestler2_name: str,
                         storyline_context: str = "",
                         is_ppv: bool = False) -> Dict[str, str]:
    """LLM-as-booker decides match finish and winner.

    Returns dict with 'winner', 'finish_type', 'reasoning'.
    """
    fallback_winner = random.choice([wrestler1_name, wrestler2_name])
    fallback = {
        "winner": fallback_winner,
        "finish_type": "pinfall",
        "reasoning": "The better wrestler prevails.",
    }

    if not USE_LLM:
        return fallback

    ppv_note = " This is a PPV match — the finish needs to feel special." if is_ppv else ""

    user_prompt = (
        f"Book the finish for: {wrestler1_name} vs {wrestler2_name}. "
        f"{storyline_context}{ppv_note}\n\n"
        f"Respond in this exact format:\n"
        f"WINNER: <{wrestler1_name} or {wrestler2_name}>\n"
        f"FINISH: <pinfall|submission|dq|countout|ref_stoppage>\n"
        f"REASONING: <1 sentence booking logic>"
    )

    result = _llm_call(BOOKER_SYSTEM, user_prompt, "", max_tokens=100)
    if not result:
        return fallback

    parsed = dict(fallback)
    for line in result.split("\n"):
        line = line.strip()
        if line.upper().startswith("WINNER:"):
            name = line.split(":", 1)[1].strip()
            if wrestler1_name.lower() in name.lower():
                parsed["winner"] = wrestler1_name
            elif wrestler2_name.lower() in name.lower():
                parsed["winner"] = wrestler2_name
        elif line.upper().startswith("FINISH:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("pinfall", "submission", "dq", "countout", "ref_stoppage"):
                parsed["finish_type"] = val
        elif line.upper().startswith("REASONING:"):
            parsed["reasoning"] = line.split(":", 1)[1].strip()

    return parsed


# ---------------------------------------------------------------------------
# Match narrative: LLM generates a story-driven match summary
# ---------------------------------------------------------------------------

def generate_match_narrative(winner_name: str, loser_name: str,
                             finish_type: str, finish_description: str,
                             rating: float, key_spots: List[str],
                             stipulation: str = "",
                             is_title_match: bool = False) -> str:
    """Generate an evocative match summary using the LLM.

    Falls back to spot-based narrative when LLM is off.
    """
    # Template fallback: stitch key spots
    fallback = " ".join(key_spots[-5:]) if key_spots else (
        f"{winner_name} defeated {loser_name} via {finish_type}."
    )

    if not USE_LLM:
        return fallback

    stip_note = f" Stipulation: {stipulation}." if stipulation else ""
    title_note = " This was a championship match." if is_title_match else ""
    spots_summary = "; ".join(key_spots[-4:]) if key_spots else "a hard-fought contest"

    user_prompt = (
        f"Write a dramatic 2-3 sentence wrestling match summary.\n"
        f"Winner: {winner_name}. Loser: {loser_name}. "
        f"Finish: {finish_type} ({finish_description}). "
        f"Rating: {rating:.1f}/5.0 stars.{stip_note}{title_note}\n"
        f"Key moments: {spots_summary}\n\n"
        f"Write like a wrestling journalist. Vivid, concise, dramatic."
    )

    system = (
        "You are a veteran wrestling journalist writing match reports. "
        "Capture the drama and emotion of the match in vivid prose. "
        "Never use generic phrases. Make each summary feel unique."
    )

    return _llm_call(system, user_prompt, fallback, max_tokens=120)


# ---------------------------------------------------------------------------
# Character agency tick: wrestlers make autonomous decisions
# ---------------------------------------------------------------------------

def tick_character_agency(db: Session, world_id: str, game_date: str) -> List[str]:
    """Daily character agency tick — LLM-driven wrestlers make decisions.

    Each wrestler has a small chance per day to take an autonomous action:
    - Call out a rival on social media
    - Request a match
    - Propose an alliance
    - React to a recent event

    Returns list of narrative events generated.
    """
    from models.game_models import (
        GameWrestlerDB, GameNarrativeLogDB, StorylineDB,
        StorylineParticipantDB, ContractDB,
    )

    events = []

    # Only top wrestlers get character agency (limits LLM calls)
    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == True,
        GameWrestlerDB.is_injured == False,
        GameWrestlerDB.popularity >= 40,
    ).all()

    for wrestler in wrestlers:
        # 5% chance per day for a character-driven action
        if random.random() > 0.05:
            continue

        # Gather context for the decision
        storyline_parts = db.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.wrestler_id == wrestler.id,
        ).all()
        in_storyline = False
        rival_name = None
        for sp in storyline_parts:
            sl = db.query(StorylineDB).filter(
                StorylineDB.id == sp.storyline_id,
                StorylineDB.status.in_(["active", "climax"]),
            ).first()
            if sl:
                in_storyline = True
                rival_part = db.query(StorylineParticipantDB).filter(
                    StorylineParticipantDB.storyline_id == sl.id,
                    StorylineParticipantDB.wrestler_id != wrestler.id,
                ).first()
                if rival_part:
                    rival = db.query(GameWrestlerDB).filter(
                        GameWrestlerDB.id == rival_part.wrestler_id
                    ).first()
                    if rival:
                        rival_name = rival.name
                break

        # Build situation
        if in_storyline and rival_name:
            situation = (
                f"You are in the middle of a feud with {rival_name}. "
                f"Your popularity is {wrestler.popularity}/100, morale is {wrestler.morale}/100. "
                f"What do you do to escalate or advance the situation?"
            )
            options = [
                "call_out_rival", "demand_stipulation_match",
                "attack_backstage", "cut_promo", "social_media_tirade",
            ]
        elif wrestler.popularity > 70:
            situation = (
                f"You are one of the top stars (popularity {wrestler.popularity}/100). "
                f"You don't have an active feud right now. What do you do?"
            )
            options = [
                "issue_open_challenge", "demand_title_shot",
                "call_out_specific_rival", "cut_promo", "mentor_young_talent",
            ]
        else:
            situation = (
                f"You are trying to climb the ranks (popularity {wrestler.popularity}/100). "
                f"You need to make a name for yourself. What do you do?"
            )
            options = [
                "challenge_someone_above", "cut_passionate_promo",
                "create_viral_moment", "train_and_improve", "form_alliance",
            ]

        decision = character_decide(db, wrestler.id, situation, options)
        action = decision["action"]
        reasoning = decision["reasoning"]

        # Log the character-driven event
        event_desc = f"{wrestler.name}: {action.replace('_', ' ')} — {reasoning}"
        events.append(event_desc)

        db.add(GameNarrativeLogDB(
            world_id=world_id,
            game_date=game_date,
            tick=0,
            event_type="character_agency",
            description=event_desc,
            involved_entities=[wrestler.id],
            importance=5,
        ))

        # Some actions have mechanical effects
        if action in ("call_out_rival", "social_media_tirade") and rival_name:
            # Boost storyline heat
            for sp in storyline_parts:
                sl = db.query(StorylineDB).filter(
                    StorylineDB.id == sp.storyline_id,
                    StorylineDB.status.in_(["active", "climax"]),
                ).first()
                if sl:
                    sl.heat = min(100, sl.heat + random.randint(2, 5))
                    break
        elif action in ("cut_promo", "cut_passionate_promo"):
            wrestler.popularity = min(100, wrestler.popularity + random.randint(1, 3))
        elif action == "train_and_improve":
            wrestler.condition = min(100, wrestler.condition + 5)
        elif action in ("challenge_someone_above", "issue_open_challenge", "demand_title_shot"):
            wrestler.popularity = min(100, wrestler.popularity + random.randint(1, 2))

    return events
