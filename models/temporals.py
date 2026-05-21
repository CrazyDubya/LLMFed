"""
Two temporals: conceptual timeline (plan to achieve the card) vs run timeline (reality in the moment).

The promoter plans in conceptual terms but runs in the moment—pieces must be introduced,
sorted from chaff; gamification (chance, branches, trapdoors, ripples) applies to the run.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from datetime import date
from pydantic import BaseModel, Field


class TemporalLayer(str, Enum):
    """Which timeline we're referring to."""
    CONCEPTUAL = "conceptual"  # Plan / target: world built to achieve the card
    RUN = "run"                # Reality: state as it unfolds, in the moment


class BranchStatus(str, Enum):
    """Status of a branch (push, feud, storyline) in the run."""
    ALIVE = "alive"      # Being pursued, has heat/momentum
    PRUNED = "pruned"    # Dropped, cut, or failed (chaff)
    ACHIEVED = "achieved"  # Paid off (e.g. at anchor)
    DEFERRED = "deferred"  # Paused, might return


class RippleCause(str, Enum):
    """What caused a ripple (effect) in the run timeline."""
    INJURY = "injury"
    COLD_START = "cold_start"   # Talent or angle didn't get over
    LUCK_GOOD = "luck_good"     # Breakout, surprise pop, perfect timing
    LUCK_ILL = "luck_ill"       # Bad timing, setback, crowd turned
    TRAPDOOR = "trapdoor"       # Change of mind, swerve, dropped plan
    DEBUT = "debut"
    RETURN = "return"
    RELEASE = "release"
    OTHER = "other"


class Ripple(BaseModel):
    """An effect that propagates through the run (injury, cold start, luck, trapdoor)."""
    ripple_id: str = Field(description="Unique id")
    cause: RippleCause = Field(description="What caused it")
    at_date: Optional[date] = Field(default=None)
    agent_ids: list = Field(default_factory=list, description="Agents affected")
    storyline_ids: list = Field(default_factory=list)
    description: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Trapdoor(BaseModel):
    """A change of direction in the run: plan shifted (swerve, dropped branch, new focus)."""
    trapdoor_id: str = Field(description="Unique id")
    at_date: Optional[date] = Field(default=None)
    from_branch: Optional[str] = Field(default=None, description="Branch or plan we're leaving")
    to_branch: Optional[str] = Field(default=None, description="New direction (if any)")
    reason: str = Field(default="", description="e.g. injury, cold start, change of mind")
    ripple_ids: list = Field(default_factory=list, description="Ripples this trapdoor triggered")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunState(BaseModel):
    """Snapshot of the run timeline at a point in time (for gamification layer)."""
    as_of_date: Optional[date] = Field(default=None)
    current_phase: str = Field(default="build_up")
    branch_statuses: Dict[str, str] = Field(default_factory=dict, description="branch_id -> BranchStatus")
    recent_ripples: list = Field(default_factory=list)
    recent_trapdoors: list = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptualCard(BaseModel):
    """Target card (conceptual timeline): what we're building toward, not yet real."""
    anchor_date: date = Field(description="Marquee date")
    anchor_event_name: str = Field(default="Grandstand")
    main_event_target: Optional[Dict[str, Any]] = Field(default=None)
    title_matches_target: list = Field(default_factory=list)
    planned_storyline_payoffs: list = Field(default_factory=list, description="Storyline ids planned to climax at anchor")
    metadata: Dict[str, Any] = Field(default_factory=dict)
