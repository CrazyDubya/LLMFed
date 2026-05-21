"""
Calendar and event hierarchy for LLMFed.

Builds from match phases (pre_match, match, post_match) to a full federation calendar:

  Year
    └── Season (multiple per year)
          └── Month (multiple per season; culminates with PPV)
                └── Week (multiple per month)
                      └── Card
                            └── Match -> Phases

PPV is a special Card that culminates each month's cycle.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Match phases (ring-time granularity)
# ---------------------------------------------------------------------------
class EventPhase(str, Enum):
    """Temporal phase of a match or event."""
    PRE_MATCH = "pre_match"   # Promoter sets story, backstage prepares
    MATCH = "match"           # Ring ticks, in-ring action
    POST_MATCH = "post_match" # Promoter reacts, backstage plans next


# ---------------------------------------------------------------------------
# Per-role tick cadence (how often each role runs during MATCH phase)
# Participants/ref every tick; announcer every 4; crowd every 6; backstage every 12; promoter pre + every 20
# ---------------------------------------------------------------------------
ROLE_TICK_CADENCE: dict[str, int] = {
    "participant": 1,
    "referee": 1,
    "announcer": 4,
    "crowd": 6,
    "valet": 8,
    "manager": 8,
    "backstage": 12,
    "promoter": 20,
}

# Roles that run in pre_match / post_match (promoter sets story, backstage prepares/reacts)
PRE_MATCH_ROLES: tuple[str, ...] = ("promoter", "backstage")
POST_MATCH_ROLES: tuple[str, ...] = ("promoter", "backstage")


# ---------------------------------------------------------------------------
# Calendar concepts
# ---------------------------------------------------------------------------
class Match(BaseModel):
    """A single match on a card."""
    match_id: str = Field(description="Unique match identifier")
    card_id: str = Field(description="Parent card")
    participant_ids: List[str] = Field(default_factory=list, description="Agent IDs in the match")
    stipulation: str = Field(default="StandardMatch", description="Match type")
    phase: EventPhase = Field(default=EventPhase.MATCH, description="Current phase")
    current_tick: int = Field(default=0, description="Ring ticks elapsed in match phase")
    is_title_match: bool = Field(default=False, description="True if championship on the line")
    title_id: Optional[str] = Field(default=None, description="Title at stake if title match")
    storyline_id: Optional[str] = Field(default=None, description="Storyline advanced by this match")


class Card(BaseModel):
    """A show/event card: one or more matches; held at a venue (the place)."""
    card_id: str = Field(description="Unique card identifier")
    federation_id: str = Field(description="Owning federation")
    name: str = Field(description="Card name (e.g. 'Monday Night Raw', 'WrestleMania')")
    card_date: Optional[date] = Field(default=None, description="Date of the card")
    week_id: Optional[str] = Field(default=None, description="Parent week if part of calendar")
    venue_id: Optional[str] = Field(default=None, description="Venue where the card is held")
    show_type: Optional[str] = Field(default=None, description="house, tv, ppv, dark (from week template)")
    prep_date: Optional[date] = Field(default=None, description="Day before show (travel/prep day)")
    travel_squad_ids: Optional[List[str]] = Field(default=None, description="Agent IDs on this show (who traveled)")
    promo_lineup: Optional[List[List[str]]] = Field(default=None, description="Per-promo agent_ids; promoter picks who cuts each promo")
    is_ppv: bool = Field(default=False, description="True if pay-per-view")
    matches: List[Match] = Field(default_factory=list, description="Matches on the card")


class Week(BaseModel):
    """A calendar week (e.g. Mon–Sun)."""
    week_id: str = Field(description="Unique week identifier")
    federation_id: str = Field(description="Owning federation")
    month_id: Optional[str] = Field(default=None, description="Parent month if part of calendar")
    start_date: date = Field(description="Monday of the week")
    end_date: date = Field(description="Sunday of the week")
    cards: List[Card] = Field(default_factory=list, description="Cards in this week")


class PPV(BaseModel):
    """Pay-per-view event: a special Card with higher stakes; culminates each month."""
    ppv_id: str = Field(description="Unique PPV identifier")
    card: Card = Field(description="Underlying card")
    title: str = Field(description="PPV name (e.g. 'WrestleMania', 'SummerSlam')")
    month_id: Optional[str] = Field(default=None, description="Parent month this PPV culminates")


class Month(BaseModel):
    """A calendar month: multiple weeks, culminates in a PPV."""
    month_id: str = Field(description="Unique month identifier")
    federation_id: str = Field(description="Owning federation")
    season_id: str = Field(description="Parent season")
    year_number: int = Field(description="Calendar year (e.g. 2025)")
    month_number: int = Field(description="Month 1-12")
    start_date: date = Field(description="First day of month")
    end_date: date = Field(description="Last day of month")
    weeks: List[Week] = Field(default_factory=list, description="Weeks in this month")
    ppv: Optional[PPV] = Field(default=None, description="PPV that culminates this month")


class Season(BaseModel):
    """A season: multiple months within a year."""
    season_id: str = Field(description="Unique season identifier")
    federation_id: str = Field(description="Owning federation")
    year_id: str = Field(description="Parent year")
    season_number: int = Field(description="Season index within year (e.g. 1, 2, 3)")
    months: List[Month] = Field(default_factory=list, description="Months in this season")


class Year(BaseModel):
    """A federation year: multiple seasons."""
    year_id: str = Field(description="Unique year identifier")
    federation_id: str = Field(description="Owning federation")
    year_number: int = Field(description="Calendar year (e.g. 2025)")
    seasons: List[Season] = Field(default_factory=list, description="Seasons in this year")


class Calendar(BaseModel):
    """Federation calendar: years, seasons, months, weeks, cards, PPVs."""
    federation_id: str = Field(description="Owning federation")
    years: List[Year] = Field(default_factory=list, description="Years in the calendar")
    weeks: List[Week] = Field(default_factory=list, description="Flat week list (legacy)")
    ppvs: List[PPV] = Field(default_factory=list, description="Flat PPV list (legacy)")
