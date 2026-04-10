"""
Prompt templates, system messages, and prompt construction for the character agent.

This module contains all the string templates and prompt-building logic used by
character_agent.py. Separating prompts from orchestration keeps the agent file
focused on control flow while making prompt iteration easy.
"""

import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Archetype / alignment data
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
# Booker system prompt
# ---------------------------------------------------------------------------

BOOKER_SYSTEM = (
    "You are an experienced professional wrestling booker. "
    "You think about long-term storytelling, crowd psychology, and building stars. "
    "You balance giving fans what they want with surprising them. "
    "You understand that the best feuds have personal stakes and clear motivations."
)

MATCH_NARRATOR_SYSTEM = (
    "You are a veteran wrestling journalist writing match reports. "
    "Capture the drama and emotion of the match in vivid prose. "
    "Never use generic phrases. Make each summary feel unique."
)

# ---------------------------------------------------------------------------
# Tone and platform lookup maps
# ---------------------------------------------------------------------------

TONE_INSTRUCTIONS = {
    "angry": " You are FURIOUS right now.",
    "triumphant": " You are riding high on victory.",
    "desperate": " You are at your lowest point and fighting to stay relevant.",
    "cocky": " You are supremely confident.",
    "emotional": " You are overwhelmed with genuine emotion.",
}

PLATFORM_NOTES = {
    "twitter": "Keep it under 280 characters. Punchy.",
    "instagram": "Caption for a photo post. Can be slightly longer.",
    "tiktok": "Caption for a short video. Casual, trendy.",
    "youtube": "Title/description for a video. Slightly more formal.",
}

POST_TYPE_NOTES = {
    "kayfabe": "Stay fully in character. This is part of your wrestling persona.",
    "shoot": "This is the REAL you behind the character. Authentic, personal.",
    "worked_shoot": "Blur the lines. Hint at real frustration through the character.",
    "personal": "Share something from your personal life. Warm, human.",
}


# ---------------------------------------------------------------------------
# Character system prompt builder (the big one)
# ---------------------------------------------------------------------------

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
# User prompt builders for each agent function
# ---------------------------------------------------------------------------

def build_decide_prompt(wrestler_name: str, situation: str,
                        options: List[str] = None) -> str:
    """Build the user prompt for character_decide()."""
    options_str = ""
    if options:
        options_str = f"\n\nYour options are: {', '.join(options)}. Pick ONE."

    return (
        f"Situation: {situation}{options_str}\n\n"
        f"What do you do? Respond in this exact format:\n"
        f"ACTION: <your choice>\n"
        f"REASONING: <1 sentence why, in character>"
    )


def build_speak_prompt(wrestler_name: str, context: str,
                       tone: str = "default") -> str:
    """Build the user prompt for character_speak()."""
    tone_instruction = TONE_INSTRUCTIONS.get(tone, "")

    return (
        f"Context: {context}{tone_instruction}\n\n"
        f"Speak IN CHARACTER as {wrestler_name}. "
        f"This is a wrestling promo/speech. 3-5 sentences. "
        f"No stage directions, just your words."
    )


def build_react_prompt(wrestler_name: str, event_type: str,
                       event_details: str = "") -> str:
    """Build the user prompt for character_react()."""
    return (
        f"You just experienced: {event_type}. {event_details}\n\n"
        f"Describe how {wrestler_name} reacts, in third person. "
        f"1-2 sentences. Stay true to the character."
    )


def build_social_media_prompt(wrestler_name: str, platform: str,
                              post_type: str, recent_event: str = "") -> str:
    """Build the user prompt for character_social_media_post()."""
    platform_note = PLATFORM_NOTES.get(platform, "Keep it short.")
    type_note = POST_TYPE_NOTES.get(post_type, "Stay in character.")
    event_context = f" Recent event: {recent_event}" if recent_event else ""

    return (
        f"Write a {platform} post as {wrestler_name}. "
        f"{type_note} {platform_note}{event_context}\n\n"
        f"Just the post text, nothing else. No quotation marks."
    )


def build_booker_storyline_prompt(fed_name: str, fed_style: str,
                                  wrestler1_name: str, wrestler2_name: str,
                                  context: str = "") -> str:
    """Build the user prompt for booker_decide_storyline()."""
    return (
        f"You are booking {fed_name} (style: {fed_style}). "
        f"Create a storyline between {wrestler1_name} and {wrestler2_name}. "
        f"{context}\n\n"
        f"Respond in this exact format:\n"
        f"TYPE: <feud|alliance|betrayal|championship_chase>\n"
        f"NAME: <creative storyline name, 2-4 words>\n"
        f"DESCRIPTION: <1 sentence setup>\n"
        f"HOOK: <1 sentence that makes fans care>"
    )


def build_booker_finish_prompt(wrestler1_name: str, wrestler2_name: str,
                               storyline_context: str = "",
                               is_ppv: bool = False) -> str:
    """Build the user prompt for booker_decide_finish()."""
    ppv_note = " This is a PPV match — the finish needs to feel special." if is_ppv else ""

    return (
        f"Book the finish for: {wrestler1_name} vs {wrestler2_name}. "
        f"{storyline_context}{ppv_note}\n\n"
        f"Respond in this exact format:\n"
        f"WINNER: <{wrestler1_name} or {wrestler2_name}>\n"
        f"FINISH: <pinfall|submission|dq|countout|ref_stoppage>\n"
        f"REASONING: <1 sentence booking logic>"
    )


def build_match_narrative_prompt(winner_name: str, loser_name: str,
                                 finish_type: str, finish_description: str,
                                 rating: float, key_spots: List[str],
                                 stipulation: str = "",
                                 is_title_match: bool = False) -> str:
    """Build the user prompt for generate_match_narrative()."""
    stip_note = f" Stipulation: {stipulation}." if stipulation else ""
    title_note = " This was a championship match." if is_title_match else ""
    spots_summary = "; ".join(key_spots[-4:]) if key_spots else "a hard-fought contest"

    return (
        f"Write a dramatic 2-3 sentence wrestling match summary.\n"
        f"Winner: {winner_name}. Loser: {loser_name}. "
        f"Finish: {finish_type} ({finish_description}). "
        f"Rating: {rating:.1f}/5.0 stars.{stip_note}{title_note}\n"
        f"Key moments: {spots_summary}\n\n"
        f"Write like a wrestling journalist. Vivid, concise, dramatic."
    )
