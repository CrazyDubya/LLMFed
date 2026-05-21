"""
World anchor: 4-year spine centered on one marquee annual show two years in the future.

The engine is designed backward (what must come together over 2 years) and forward
(2 years of payoff and consequences) from this anchor. Promoter decisions determine
whether the federation achieves that reality; the anchor provides continuity and stakes.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class WorldPhase(str, Enum):
    """Temporal phase relative to the marquee anchor."""
    BUILD_UP = "build_up"   # Years 0-1: 24 months toward anchor
    ANCHOR = "anchor"       # Anchor month/show
    AFTERMATH = "aftermath" # Years 2-3: 24 months after anchor


# Default: world start = first Monday of year; anchor = same month + 2 years
def _default_anchor_date(world_start: date) -> date:
    """Anchor = first Sunday of same month, two years after world start."""
    anchor_year = world_start.year + 2
    anchor_month = world_start.month
    # First Sunday of that month
    first = date(anchor_year, anchor_month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7)


class WorldAnchor(BaseModel):
    """
    Federation's 4-year world spine anchored on one marquee annual show.

    - world_start_date: canonical "day 1" (e.g. first Monday of year).
    - anchor_event_name: marquee show name (e.g. Grandstand, Summit).
    - anchor_date: fixed at world_start + 2 years (e.g. first Sunday of that month).
    - world_end_date: optional; world_start + 4 years for design boundary.
    """

    federation_id: str = Field(description="Federation that owns this world")
    world_start_date: date = Field(description="Canonical start of the 4-year world")
    anchor_event_name: str = Field(default="Grandstand", description="Marquee annual show name")
    anchor_date: Optional[date] = Field(default=None, description="Marquee show date (default: world_start + 2 years)")
    world_end_date: Optional[date] = Field(default=None, description="End of 4-year window (default: world_start + 4 years)")

    def get_anchor_date(self) -> date:
        """Return anchor date (computed if not set)."""
        if self.anchor_date is not None:
            return self.anchor_date
        return _default_anchor_date(self.world_start_date)

    def get_world_end_date(self) -> date:
        """Return world end date (world_start + 4 years if not set)."""
        if self.world_end_date is not None:
            return self.world_end_date
        return self.world_start_date.replace(year=self.world_start_date.year + 4)

    def phase_for(self, card_date: date) -> WorldPhase:
        """Return build_up | anchor | aftermath for a given date."""
        anchor = self.get_anchor_date()
        # Anchor "month" = same calendar month as anchor date
        if card_date.year == anchor.year and card_date.month == anchor.month:
            return WorldPhase.ANCHOR
        if card_date < anchor:
            return WorldPhase.BUILD_UP
        return WorldPhase.AFTERMATH

    def weeks_until_marquee(self, card_date: date) -> Optional[int]:
        """Weeks from card_date to anchor (negative if past). None if anchor month."""
        anchor = self.get_anchor_date()
        if card_date.year == anchor.year and card_date.month == anchor.month:
            return None
        delta = (anchor - card_date).days
        return delta // 7 if delta >= 0 else -(abs(delta) // 7)

    def weeks_since_marquee(self, card_date: date) -> Optional[int]:
        """Weeks from anchor to card_date (positive = after). None if before or anchor month."""
        anchor = self.get_anchor_date()
        if card_date <= anchor:
            return None
        return (card_date - anchor).days // 7

    def years_from_anchor(self, card_date: date) -> float:
        """Signed years from anchor (-2 to +2 over the 4-year window)."""
        anchor = self.get_anchor_date()
        delta = (card_date - anchor).days
        return round(delta / 365.25, 2)


class AnchorMilestone(BaseModel):
    """A milestone that should be reachable before/at the anchor (for pacing; not scripted)."""
    milestone_id: str = Field(description="Unique id")
    name: str = Field(description="e.g. Main event set, Title picture locked")
    due_phase: WorldPhase = Field(default=WorldPhase.ANCHOR)
    metadata: dict = Field(default_factory=dict)


# Default milestones: what should come together over 2 years (promoter-facing; not scripted)
DEFAULT_ANCHOR_MILESTONES: List[AnchorMilestone] = [
    AnchorMilestone(milestone_id="roster_set", name="Roster and contracts set through anchor", due_phase=WorldPhase.BUILD_UP),
    AnchorMilestone(milestone_id="title_picture", name="Title picture and #1 contenders clear", due_phase=WorldPhase.ANCHOR),
    AnchorMilestone(milestone_id="main_event_set", name="Main event and top feuds built", due_phase=WorldPhase.ANCHOR),
    AnchorMilestone(milestone_id="heat_peak", name="Crowd heat and engagement at peak", due_phase=WorldPhase.ANCHOR),
    AnchorMilestone(milestone_id="payoff_arcs", name="Long-term storylines ready for payoff", due_phase=WorldPhase.ANCHOR),
]


def build_default_anchor(federation_id: str, start_year: int = 2025) -> WorldAnchor:
    """Build a default 4-year world: start first Monday of start_year, anchor +2 years."""
    first_jan = date(start_year, 1, 1)
    # First Monday of year
    world_start = first_jan + timedelta(days=(7 - first_jan.weekday()) % 7)
    return WorldAnchor(
        federation_id=federation_id,
        world_start_date=world_start,
        anchor_event_name="Grandstand",
    )
