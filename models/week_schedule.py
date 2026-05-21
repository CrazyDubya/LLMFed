"""
Week schedule: show type per day, week template, slots.

Supports week structure (how many house/TV/PPV), travel squad by show type,
and month/week building from templates.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import date
from pydantic import BaseModel, Field


class ShowType(str, Enum):
    """Type of show on a given day."""
    HOUSE = "house"
    TV = "tv"
    PPV = "ppv"
    DARK = "dark"   # Dark match / preshow
    OFF = "off"     # No show


class ShowSlot(BaseModel):
    """One slot in a week template: day_of_week (0=Mon .. 6=Sun) + show_type."""
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    show_type: ShowType = Field(default=ShowType.OFF)
    venue_type: Optional[str] = Field(default=None, description="arena, stadium, default")
    loop: Optional[str] = Field(default=None, description="For house: 'A' or 'B' for alternating crew")


class WeekTemplate(BaseModel):
    """Template defining which days have which show type (house, tv, ppv, dark, off)."""
    week_template_id: str = Field(description="Unique template identifier")
    federation_id: str = Field(description="Owning federation")
    name: str = Field(description="e.g. Standard, PPV week")
    slots: List[ShowSlot] = Field(default_factory=list, description="One per day or only active days")
    metadata: Dict[str, Any] = Field(default_factory=dict)


def default_standard_week_template(federation_id: str) -> WeekTemplate:
    """Default: Mon TV, Tue-Thu house (A/B/A), Fri TV, Sat-Sun house (B)."""
    import uuid
    return WeekTemplate(
        week_template_id=str(uuid.uuid4()),
        federation_id=federation_id,
        name="Standard",
        slots=[
            ShowSlot(day_of_week=0, show_type=ShowType.TV),
            ShowSlot(day_of_week=1, show_type=ShowType.HOUSE, loop="A"),
            ShowSlot(day_of_week=2, show_type=ShowType.HOUSE, loop="B"),
            ShowSlot(day_of_week=3, show_type=ShowType.HOUSE, loop="A"),
            ShowSlot(day_of_week=4, show_type=ShowType.TV),
            ShowSlot(day_of_week=5, show_type=ShowType.HOUSE, loop="B"),
            ShowSlot(day_of_week=6, show_type=ShowType.HOUSE, loop="A"),
        ],
    )


def default_ppv_week_template(federation_id: str) -> WeekTemplate:
    """PPV week: Mon TV, Tue-Thu house, Fri TV, Sat dark, Sun PPV."""
    import uuid
    return WeekTemplate(
        week_template_id=str(uuid.uuid4()),
        federation_id=federation_id,
        name="PPV week",
        slots=[
            ShowSlot(day_of_week=0, show_type=ShowType.TV),
            ShowSlot(day_of_week=1, show_type=ShowType.HOUSE, loop="A"),
            ShowSlot(day_of_week=2, show_type=ShowType.HOUSE, loop="B"),
            ShowSlot(day_of_week=3, show_type=ShowType.HOUSE, loop="A"),
            ShowSlot(day_of_week=4, show_type=ShowType.TV),
            ShowSlot(day_of_week=5, show_type=ShowType.DARK),
            ShowSlot(day_of_week=6, show_type=ShowType.PPV),
        ],
    )
