"""
Character Agent — LLMs operating AS wrestlers and bookers in the simulation.

Each wrestler is an LLM-driven character with persistent identity, memory of
recent events, and the ability to make decisions that shape the simulation.
When LLMFED_USE_LLM is not set, every function returns a template-based
fallback so the simulation runs identically without an LLM provider configured.
"""

import logging
import os
import random
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from game_service.character_prompts import (
    FALLBACK_DECISIONS,
    FALLBACK_REACTIONS,
    BOOKER_SYSTEM,
    MATCH_NARRATOR_SYSTEM,
    build_character_system_prompt,
    build_decide_prompt,
    build_speak_prompt,
    build_react_prompt,
    build_social_media_prompt,
    build_booker_storyline_prompt,
    build_booker_finish_prompt,
    build_match_narrative_prompt,
)

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


def _llm_call(
    system_msg: str,
    user_msg: str,
    fallback: str,
    temperature: float = 0.8,
    max_tokens: int = 200,
) -> str:
    """Call the LLM with a system/user prompt pair. Returns fallback on any failure."""
    if not USE_LLM:
        return fallback
    llm = _get_llm()
    if not llm:
        return fallback
    try:
        response = llm.generate(
            user_msg,
            system_message=system_msg,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response and response.content and len(response.content.strip()) > 10:
            return response.content.strip()
    except Exception as e:
        logger.debug("LLM call failed, using fallback: %s", e)
    return fallback


# -- Shared response-parsing helper ------------------------------------------


def _parse_tagged_response(
    text: str, tags: Dict[str, Any], defaults: Dict[str, str]
) -> Dict[str, str]:
    """Parse a tagged LLM response (e.g. 'ACTION: something') into a dict.

    *tags* maps lowercase key -> ``None`` (accept any value) or a set of
    valid lowercase values.  *defaults* provides initial values that parsed
    tags override.
    """
    parsed = dict(defaults)
    if not text:
        return parsed
    for line in text.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        tag_part, _, value = line.partition(":")
        key = tag_part.strip().lower()
        value = value.strip()
        if key not in tags:
            continue
        valid_set = tags[key]
        if valid_set is not None:
            if value.lower() in valid_set:
                parsed[key] = value.lower()
        else:
            parsed[key] = value

    return parsed


# -- Core character functions -------------------------------------------------


def character_decide(
    db: Session, wrestler_id: str, situation: str, options: List[str] = None
) -> Dict[str, Any]:
    """LLM-as-wrestler decides what to do next.

    Returns dict with 'action' and 'reasoning'.
    """
    from models.game_models import GameWrestlerDB, GimmickHistoryDB

    wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler_id).first()
    if not wrestler:
        return {"action": "noop", "reasoning": "Wrestler not found"}

    gimmick = (
        db.query(GimmickHistoryDB)
        .filter(
            GimmickHistoryDB.wrestler_id == wrestler_id,
            GimmickHistoryDB.is_active == True,
        )
        .first()
    )
    archetype = gimmick.archetype if gimmick else "anti_hero"

    # Template fallback
    fallback_actions = FALLBACK_DECISIONS.get(
        archetype, FALLBACK_DECISIONS["anti_hero"]
    )
    fallback_action = random.choice(fallback_actions)
    fallback = {
        "action": fallback_action,
        "reasoning": f"{wrestler.name} acts on instinct.",
    }

    if not USE_LLM:
        return fallback

    system_prompt = build_character_system_prompt(db, wrestler_id)
    user_prompt = build_decide_prompt(wrestler.name, situation, options)

    result = _llm_call(system_prompt, user_prompt, "", max_tokens=100)
    if not result:
        return fallback

    # Parse the response
    parsed = _parse_tagged_response(
        result, {"action": None, "reasoning": None}, fallback
    )
    # Normalize action to snake_case
    parsed["action"] = parsed["action"].lower().replace(" ", "_")
    return parsed


def character_speak(
    db: Session, wrestler_id: str, context: str, tone: str = "default"
) -> str:
    """LLM-as-wrestler generates in-character speech.

    Used for promos, social media posts, interview responses, etc.
    The LLM speaks AS the character, not about them.
    """
    from models.game_models import GameWrestlerDB, GimmickHistoryDB
    from game_service.promo_service import (
        ARCHETYPE_OPENERS,
        ARCHETYPE_BODIES,
        ARCHETYPE_CLOSERS,
    )

    wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler_id).first()
    if not wrestler:
        return "..."

    gimmick = (
        db.query(GimmickHistoryDB)
        .filter(
            GimmickHistoryDB.wrestler_id == wrestler_id,
            GimmickHistoryDB.is_active == True,
        )
        .first()
    )
    archetype = gimmick.archetype if gimmick else "anti_hero"

    # Template fallback: stitch together archetype templates
    openers = ARCHETYPE_OPENERS.get(archetype, ["..."])
    bodies = ARCHETYPE_BODIES.get(archetype, ["..."])
    closers = ARCHETYPE_CLOSERS.get(archetype, ["..."])
    fallback = (
        f"{random.choice(openers)} {random.choice(bodies)} {random.choice(closers)}"
    )

    if not USE_LLM:
        return fallback

    system_prompt = build_character_system_prompt(db, wrestler_id)
    user_prompt = build_speak_prompt(wrestler.name, context, tone)

    return _llm_call(system_prompt, user_prompt, fallback, max_tokens=200)


def character_react(
    db: Session, wrestler_id: str, event_type: str, event_details: str = ""
) -> str:
    """LLM-as-wrestler reacts to a specific event.

    Returns a narrative description of how the character responds.
    """
    from models.game_models import GameWrestlerDB

    wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler_id).first()
    if not wrestler:
        return ""

    # Template fallback
    reactions = FALLBACK_REACTIONS.get(event_type, FALLBACK_REACTIONS["win"])
    fallback = f"{wrestler.name} {random.choice(reactions)}"

    if not USE_LLM:
        return fallback

    system_prompt = build_character_system_prompt(db, wrestler_id)
    user_prompt = build_react_prompt(wrestler.name, event_type, event_details)

    return _llm_call(system_prompt, user_prompt, fallback, max_tokens=100)


def character_social_media_post(
    db: Session, wrestler_id: str, platform: str, post_type: str, recent_event: str = ""
) -> str:
    """LLM-as-wrestler writes a social media post in character.

    Different from character_speak — this is a social post, shorter,
    more casual, platform-appropriate.
    """
    from models.game_models import GameWrestlerDB

    wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler_id).first()
    if not wrestler:
        return "..."

    # Fallback handled by caller (social_media_service templates)
    if not USE_LLM:
        return ""  # Empty string signals caller to use its own templates

    system_prompt = build_character_system_prompt(db, wrestler_id)
    user_prompt = build_social_media_prompt(
        wrestler.name, platform, post_type, recent_event
    )

    return _llm_call(system_prompt, user_prompt, "", max_tokens=80)


# -- Booker AI ----------------------------------------------------------------


def booker_decide_storyline(
    db: Session,
    federation_id: str,
    wrestler1_name: str,
    wrestler2_name: str,
    context: str = "",
) -> Dict[str, str]:
    """LLM-as-booker decides how to book a storyline between two wrestlers.

    Returns dict with 'storyline_type', 'name', 'description', 'hook'.
    """
    from models.game_models import GameFederationDB

    fed = (
        db.query(GameFederationDB).filter(GameFederationDB.id == federation_id).first()
    )
    fed_name = fed.name if fed else "the federation"
    fed_style = (
        getattr(fed, "booking_style", "sports_entertainment")
        if fed
        else "sports_entertainment"
    )

    # Template fallback
    from game_service.storyline_service import STORYLINE_NAMES, FEUD_TRIGGERS

    fallback_name = random.choice(STORYLINE_NAMES.get("feud", ["The Rivalry"]))
    fallback_desc = random.choice(FEUD_TRIGGERS).format(
        w1=wrestler1_name, w2=wrestler2_name
    )
    fallback = {
        "storyline_type": "feud",
        "name": fallback_name,
        "description": fallback_desc,
        "hook": f"{wrestler1_name} and {wrestler2_name} are on a collision course.",
    }

    if not USE_LLM:
        return fallback

    user_prompt = build_booker_storyline_prompt(
        fed_name, fed_style, wrestler1_name, wrestler2_name, context
    )

    result = _llm_call(BOOKER_SYSTEM, user_prompt, "", max_tokens=150)
    if not result:
        return fallback

    parsed = _parse_tagged_response(
        result,
        {
            "type": {"feud", "alliance", "betrayal", "championship_chase"},
            "name": None,
            "description": None,
            "hook": None,
        },
        fallback,
    )
    # Map 'type' key to 'storyline_type' for backward compatibility
    if "type" in parsed and parsed["type"] != fallback.get("type"):
        parsed["storyline_type"] = parsed["type"]
    parsed.pop("type", None)
    # Truncate name to 50 chars
    parsed["name"] = parsed["name"][:50]

    return parsed


def booker_decide_finish(
    db: Session,
    federation_id: str,
    wrestler1_name: str,
    wrestler2_name: str,
    storyline_context: str = "",
    is_ppv: bool = False,
) -> Dict[str, str]:
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

    user_prompt = build_booker_finish_prompt(
        wrestler1_name, wrestler2_name, storyline_context, is_ppv
    )

    result = _llm_call(BOOKER_SYSTEM, user_prompt, "", max_tokens=100)
    if not result:
        return fallback

    parsed = _parse_tagged_response(
        result,
        {
            "winner": None,
            "finish": {"pinfall", "submission", "dq", "countout", "ref_stoppage"},
            "reasoning": None,
        },
        fallback,
    )

    # Normalize winner to one of the two known names
    winner_raw = parsed.get("winner", "")
    if wrestler1_name.lower() in winner_raw.lower():
        parsed["winner"] = wrestler1_name
    elif wrestler2_name.lower() in winner_raw.lower():
        parsed["winner"] = wrestler2_name

    # Map 'finish' -> 'finish_type' for backward compatibility
    if "finish" in parsed:
        parsed["finish_type"] = parsed["finish"]
        del parsed["finish"]

    return parsed


# -- Match narrative ----------------------------------------------------------


def generate_match_narrative(
    winner_name: str,
    loser_name: str,
    finish_type: str,
    finish_description: str,
    rating: float,
    key_spots: List[str],
    stipulation: str = "",
    is_title_match: bool = False,
) -> str:
    """Generate an evocative match summary using the LLM.

    Falls back to spot-based narrative when LLM is off.
    """
    # Template fallback: stitch key spots
    fallback = (
        " ".join(key_spots[-5:])
        if key_spots
        else (f"{winner_name} defeated {loser_name} via {finish_type}.")
    )

    if not USE_LLM:
        return fallback

    user_prompt = build_match_narrative_prompt(
        winner_name,
        loser_name,
        finish_type,
        finish_description,
        rating,
        key_spots,
        stipulation,
        is_title_match,
    )

    return _llm_call(MATCH_NARRATOR_SYSTEM, user_prompt, fallback, max_tokens=120)


# -- Character agency tick ----------------------------------------------------


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
        GameWrestlerDB,
        GameNarrativeLogDB,
        StorylineDB,
        StorylineParticipantDB,
    )

    events = []

    # Only top wrestlers get character agency (limits LLM calls)
    wrestlers = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.world_id == world_id,
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.is_injured == False,
            GameWrestlerDB.popularity >= 40,
        )
        .all()
    )

    for wrestler in wrestlers:
        # 5% chance per day for a character-driven action
        if random.random() > 0.05:
            continue

        # Gather context for the decision
        storyline_parts = (
            db.query(StorylineParticipantDB)
            .filter(
                StorylineParticipantDB.wrestler_id == wrestler.id,
            )
            .all()
        )
        in_storyline = False
        rival_name = None
        for sp in storyline_parts:
            sl = (
                db.query(StorylineDB)
                .filter(
                    StorylineDB.id == sp.storyline_id,
                    StorylineDB.status.in_(["active", "climax"]),
                )
                .first()
            )
            if sl:
                in_storyline = True
                rival_part = (
                    db.query(StorylineParticipantDB)
                    .filter(
                        StorylineParticipantDB.storyline_id == sl.id,
                        StorylineParticipantDB.wrestler_id != wrestler.id,
                    )
                    .first()
                )
                if rival_part:
                    rival = (
                        db.query(GameWrestlerDB)
                        .filter(GameWrestlerDB.id == rival_part.wrestler_id)
                        .first()
                    )
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
                "call_out_rival",
                "demand_stipulation_match",
                "attack_backstage",
                "cut_promo",
                "social_media_tirade",
            ]
        elif wrestler.popularity > 70:
            situation = (
                f"You are one of the top stars (popularity {wrestler.popularity}/100). "
                f"You don't have an active feud right now. What do you do?"
            )
            options = [
                "issue_open_challenge",
                "demand_title_shot",
                "call_out_specific_rival",
                "cut_promo",
                "mentor_young_talent",
            ]
        else:
            situation = (
                f"You are trying to climb the ranks (popularity {wrestler.popularity}/100). "
                f"You need to make a name for yourself. What do you do?"
            )
            options = [
                "challenge_someone_above",
                "cut_passionate_promo",
                "create_viral_moment",
                "train_and_improve",
                "form_alliance",
            ]

        decision = character_decide(db, wrestler.id, situation, options)
        action = decision["action"]
        reasoning = decision["reasoning"]

        # Log the character-driven event
        event_desc = f"{wrestler.name}: {action.replace('_', ' ')} — {reasoning}"
        events.append(event_desc)

        db.add(
            GameNarrativeLogDB(
                world_id=world_id,
                game_date=game_date,
                tick=0,
                event_type="character_agency",
                description=event_desc,
                involved_entities=[wrestler.id],
                importance=5,
            )
        )

        # Some actions have mechanical effects
        if action in ("call_out_rival", "social_media_tirade") and rival_name:
            # Boost storyline heat
            for sp in storyline_parts:
                sl = (
                    db.query(StorylineDB)
                    .filter(
                        StorylineDB.id == sp.storyline_id,
                        StorylineDB.status.in_(["active", "climax"]),
                    )
                    .first()
                )
                if sl:
                    sl.heat = min(100, sl.heat + random.randint(2, 5))
                    break
        elif action in ("cut_promo", "cut_passionate_promo"):
            wrestler.popularity = min(100, wrestler.popularity + random.randint(1, 3))
        elif action == "train_and_improve":
            wrestler.condition = min(100, wrestler.condition + 5)
        elif action in (
            "challenge_someone_above",
            "issue_open_challenge",
            "demand_title_shot",
        ):
            wrestler.popularity = min(100, wrestler.popularity + random.randint(1, 2))

    return events
