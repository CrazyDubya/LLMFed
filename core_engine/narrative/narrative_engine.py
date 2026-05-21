"""
Advanced narrative engine (ENHANCEMENT_PROPOSAL Phase 2.1).

Generates rich storylines:
- Pre-match buildup, live commentary, post-match aftermath
- Storyline continuity
"""

from __future__ import annotations

import logging
from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MatchNarrative(BaseModel):
    """Narrative for a match: buildup, commentary, aftermath."""
    buildup: str = Field(default="", description="Pre-match buildup")
    commentary: List[str] = Field(default_factory=list, description="Live commentary moments")
    aftermath: str = Field(default="", description="Post-match consequences")


class NarrativeEngine:
    """Generate rich, coherent narratives for matches and storylines."""

    def __init__(self):
        pass

    def generate_match_narrative(
        self,
        match: Any,
        participant_names: Optional[Dict[str, str]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> MatchNarrative:
        """Generate pre-match buildup, in-match commentary, post-match aftermath."""
        pids = getattr(match, "participant_ids", []) or []
        names = participant_names or {}
        a = names.get(pids[0], pids[0] if pids else "?")
        b = names.get(pids[1], pids[1] if len(pids) > 1 else "?")
        winner = (result or {}).get("winner_id")
        w_name = names.get(winner, winner or "?") if winner else "?"

        buildup = f"The stage is set for {a} vs {b}. Tensions run high as both competitors prepare for battle."
        commentary = [
            f"{a} and {b} lock up in the center of the ring.",
            "The crowd is on their feet as the action intensifies.",
            f"{w_name} seizes the moment and delivers a decisive blow!",
        ]
        aftermath = f"{w_name} emerges victorious. The crowd reacts as the result sinks in." if winner else "The match concludes with both competitors battered but unbowed."

        return MatchNarrative(buildup=buildup, commentary=commentary, aftermath=aftermath)
