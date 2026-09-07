"""
Match Narrative Engine — LLM-powered commentary and evolving wrestler chemistry.

Provides optional LLM-enhanced narrative for key match moments (finishers,
near-falls, dramatic reversals) and a chemistry system that tracks how
matchups evolve over time.

When LLM is unavailable or disabled, falls back to template-based descriptions.
"""

import logging
import os
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes")

# Cache the LLM instance
_llm_instance = None


def _get_llm():
    """Get the LLM singleton, or None if unavailable."""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance
    try:
        from llm_abstraction.provider import get_llm

        _llm_instance = get_llm()
        return _llm_instance
    except Exception as e:
        logger.debug("LLM not available for match narrative: %s", e)
        return None


def _llm_call(
    system_msg: str,
    user_msg: str,
    fallback: str,
    temperature: float = 0.9,
    max_tokens: int = 150,
) -> str:
    """Call the LLM and return the response text, or the fallback on any failure."""
    if not USE_LLM:
        return fallback
    llm = _get_llm()
    if not llm:
        return fallback
    try:
        response = llm.generate(
            prompt=user_msg,
            system_message=system_msg,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response and response.content:
            return response.content.strip()
    except Exception as e:
        logger.debug("LLM match narrative call failed: %s", e)
    return fallback


# ---------------------------------------------------------------------------
# Chemistry system
# ---------------------------------------------------------------------------


@dataclass
class ChemistryRecord:
    """Tracks evolving chemistry between two wrestlers."""

    wrestler_a_id: str
    wrestler_b_id: str
    match_count: int = 0
    total_rating: float = 0.0
    familiarity_bonus: float = 0.0  # Accumulated bonus from repeated matchups
    best_rating: float = 0.0
    last_match_date: Optional[str] = None
    signature_sequences: List[str] = field(default_factory=list)

    @property
    def average_rating(self) -> float:
        return self.total_rating / self.match_count if self.match_count > 0 else 0.0

    def record_match(self, rating: float, game_date: str = None) -> None:
        """Record a new match between these wrestlers."""
        self.match_count += 1
        self.total_rating += rating
        self.best_rating = max(self.best_rating, rating)
        self.last_match_date = game_date

        # Familiarity: first few matches build chemistry, then diminishing returns
        if self.match_count <= 5:
            self.familiarity_bonus = min(0.3, self.match_count * 0.06)
        elif self.match_count <= 10:
            self.familiarity_bonus = 0.3 + (self.match_count - 5) * 0.02
        else:
            # Staleness penalty after 10+ matches
            self.familiarity_bonus = max(0.0, 0.4 - (self.match_count - 10) * 0.03)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wrestler_a_id": self.wrestler_a_id,
            "wrestler_b_id": self.wrestler_b_id,
            "match_count": self.match_count,
            "average_rating": round(self.average_rating, 2),
            "best_rating": round(self.best_rating, 2),
            "familiarity_bonus": round(self.familiarity_bonus, 2),
            "last_match_date": self.last_match_date,
        }


class ChemistryTracker:
    """In-memory tracker for wrestler pair chemistry. Can be persisted to DB."""

    def __init__(self):
        self._records: Dict[str, ChemistryRecord] = {}

    @staticmethod
    def _pair_key(a_id: str, b_id: str) -> str:
        """Canonical key so (a,b) == (b,a)."""
        return "|".join(sorted([a_id, b_id]))

    def get(self, a_id: str, b_id: str) -> ChemistryRecord:
        key = self._pair_key(a_id, b_id)
        if key not in self._records:
            self._records[key] = ChemistryRecord(
                wrestler_a_id=min(a_id, b_id),
                wrestler_b_id=max(a_id, b_id),
            )
        return self._records[key]

    def record_match(
        self, a_id: str, b_id: str, rating: float, game_date: str = None
    ) -> ChemistryRecord:
        rec = self.get(a_id, b_id)
        rec.record_match(rating, game_date)
        return rec

    def all_records(self) -> List[ChemistryRecord]:
        return list(self._records.values())


# Global tracker (in production this would be backed by the DB)
chemistry_tracker = ChemistryTracker()


# ---------------------------------------------------------------------------
# LLM-powered narrative generation for key match moments
# ---------------------------------------------------------------------------

COMMENTARY_SYSTEM = (
    "You are a professional wrestling commentator providing play-by-play and color commentary. "
    "Write vivid, dramatic, concise commentary for key match moments. "
    "Use the wrestlers' names and personalities. Keep it to 1-3 sentences."
)


def narrate_finisher(
    attacker_name: str,
    defender_name: str,
    finisher_name: str,
    attacker_alignment: str = "face",
    crowd_heat: int = 50,
    is_title_match: bool = False,
) -> str:
    """Generate dramatic commentary for a finisher being hit."""
    context_parts = [
        f"{attacker_name} ({attacker_alignment}) hits {finisher_name} on {defender_name}!",
        f"Crowd heat: {crowd_heat}/100.",
    ]
    if is_title_match:
        context_parts.append("This is a title match!")

    fallback_templates = [
        f"{attacker_name} CONNECTS with the {finisher_name}! {defender_name} is DOWN!",
        f"There it is! The {finisher_name}! {attacker_name} hits it flush on {defender_name}!",
        f"{attacker_name} delivers a DEVASTATING {finisher_name}! This could be it!",
    ]
    fallback = random.choice(fallback_templates)

    return _llm_call(
        COMMENTARY_SYSTEM,
        "Write dramatic commentary for this moment: " + " ".join(context_parts),
        fallback,
    )


def narrate_near_fall(
    attacker_name: str,
    defender_name: str,
    kickout_count: int = 2,
) -> str:
    """Generate commentary for a dramatic near-fall/kickout."""
    fallback_templates = [
        f"{attacker_name} covers! ONE! TWO! {defender_name} KICKS OUT at {kickout_count}!",
        f"The pin! {defender_name} barely escapes at {kickout_count}! The crowd ERUPTS!",
        f"How did {defender_name} kick out?! {attacker_name} can't believe it!",
    ]
    fallback = random.choice(fallback_templates)

    return _llm_call(
        COMMENTARY_SYSTEM,
        f"Write commentary for a dramatic near-fall: {attacker_name} pins {defender_name}, "
        f"kickout at the count of {kickout_count}. Make it exciting.",
        fallback,
    )


def narrate_reversal(
    reverser_name: str,
    reversed_name: str,
    original_move: str,
    reversal_move: str,
    reverser_health: float = 50.0,
) -> str:
    """Generate commentary for a dramatic reversal or comeback."""
    is_comeback = reverser_health < 30
    context = f"{reverser_name} reverses {reversed_name}'s {original_move} into a {reversal_move}!"
    if is_comeback:
        context += f" {reverser_name} is at {reverser_health:.0f}% health — this is a comeback!"

    fallback_templates = [
        f"REVERSAL! {reverser_name} counters the {original_move} into a {reversal_move}!",
        f"{reverser_name} ducks the {original_move} and fires back with the {reversal_move}!",
    ]
    if is_comeback:
        fallback_templates.append(
            f"{reverser_name} refuses to stay down! "
            f"Counter into the {reversal_move}! What a comeback!"
        )
    fallback = random.choice(fallback_templates)

    return _llm_call(COMMENTARY_SYSTEM, f"Write commentary: {context}", fallback)


def narrate_match_finish(
    winner_name: str,
    loser_name: str,
    finish_type: str,
    finish_move: str = "",
    match_rating: float = 3.0,
    is_title_match: bool = False,
    is_upset: bool = False,
) -> str:
    """Generate the final match call."""
    parts = [
        f"{winner_name} defeats {loser_name} via {finish_type}",
    ]
    if finish_move:
        parts[0] += f" after hitting the {finish_move}"
    parts.append(f"Match rating: {match_rating:.1f} stars.")
    if is_title_match:
        parts.append("This was a championship match!")
    if is_upset:
        parts.append("THIS IS A MASSIVE UPSET!")

    fallback_templates = [
        f"It's over! {winner_name} wins via {finish_type}!",
        f"{winner_name} gets the victory! What a match — {match_rating:.1f} stars!",
    ]
    if is_upset:
        fallback_templates.append(
            f"UPSET! {winner_name} has done the impossible, defeating {loser_name}!"
        )
    fallback = random.choice(fallback_templates)

    return _llm_call(
        COMMENTARY_SYSTEM,
        "Write the final match commentary: " + " ".join(parts),
        fallback,
    )


def narrate_match_psychology(
    match_context: Dict[str, Any],
) -> str:
    """LLM-driven match psychology suggestion — what should happen next in the narrative arc.

    This is meant to be called between spots to guide the pacing agent.
    Returns a short suggestion like "build heat", "start comeback", "go home".
    """
    tick = match_context.get("tick", 0)
    target_length = match_context.get("target_length", 20)
    attacker_health = match_context.get("attacker_health", 80)
    defender_health = match_context.get("defender_health", 80)
    crowd_heat = match_context.get("crowd_heat", 50)

    # Simple heuristic as fallback
    progress = tick / max(target_length, 1)
    if progress < 0.3:
        fallback = "feeling_out"
    elif progress < 0.6:
        fallback = "build_heat"
    elif progress < 0.8:
        if defender_health < 40:
            fallback = "go_home"
        else:
            fallback = "false_finish"
    else:
        fallback = "go_home"

    if not USE_LLM:
        return fallback

    prompt = (
        f"Match psychology: tick {tick}/{target_length}, "
        f"attacker health {attacker_health:.0f}%, defender health {defender_health:.0f}%, "
        f"crowd heat {crowd_heat}/100. "
        f"What should happen next? Reply with exactly one of: "
        f"feeling_out, build_heat, false_finish, comeback, go_home"
    )
    result = _llm_call(
        "You are a wrestling match psychology advisor. Reply with exactly one phase name.",
        prompt,
        fallback,
        temperature=0.3,
        max_tokens=20,
    )
    # Validate the LLM response
    valid = {"feeling_out", "build_heat", "false_finish", "comeback", "go_home"}
    cleaned = result.strip().lower().replace(" ", "_")
    return cleaned if cleaned in valid else fallback
