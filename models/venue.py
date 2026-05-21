"""
Venue: the place where the card happens.

- Named location (arena, stadium, ballroom, bingo hall)
- Capacity, venue_type, concessions, PPV capability
- Gate/revenue context (structure for "they make money, PPV is shown")
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VenueType(str, Enum):
    """Type of venue; affects prestige, gate, and production."""
    ARENA = "arena"           # Regular show, typical capacity
    STADIUM = "stadium"       # Marquee, big gate
    TV_ONLY = "tv_only"       # No live crowd, studio/taping
    SPECIAL = "special"       # Historic, one-off (MSG, Wembley)


class Venue(BaseModel):
    """
    The place where a card is held.

    Defines where the show is, how big it is, whether it's special,
    and whether concessions/PPV apply.
    """
    venue_id: str = Field(description="Unique venue identifier")
    federation_id: str = Field(description="Owning federation (or shared)")
    name: str = Field(description="Venue name (e.g. Madison Square Garden)")
    location: Optional[str] = Field(default=None, description="City/region")
    capacity: int = Field(default=5000, ge=0, description="Max attendance")
    venue_type: VenueType = Field(default=VenueType.ARENA)
    concessions_available: bool = Field(default=True, description="Food/drink sold at venue")
    ppv_capable: bool = Field(default=False, description="Can host PPV broadcast")
    metadata: dict = Field(default_factory=dict)
