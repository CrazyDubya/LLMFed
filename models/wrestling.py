"""Wrestling domain models: titles, teams, stables, storylines, alignment."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


class Alignment(str, Enum):
    """Wrestler alignment: babyface (face), heel, or tweener."""
    BABYFACE = "babyface"
    HEEL = "heel"
    TWEENER = "tweener"


class TitleTier(str, Enum):
    """Championship tier."""
    WORLD = "world"
    MID_CARD = "mid_card"
    TAG = "tag"
    SPECIALTY = "specialty"


# ---------------------------------------------------------------------------
# Titles & Lineage
# ---------------------------------------------------------------------------
class Reign(BaseModel):
    """A single championship reign."""
    reign_id: str = Field(description="Unique reign identifier")
    title_id: str = Field(description="Title this reign is for")
    champion_id: str = Field(description="Agent ID of champion")
    start_date: date = Field(description="When reign began")
    end_date: Optional[date] = Field(default=None, description="When reign ended (null = current)")
    end_reason: Optional[str] = Field(default=None, description="How reign ended (pinfall, vacated, etc.)")


class Title(BaseModel):
    """Championship with lineage."""
    title_id: str = Field(description="Unique title identifier")
    federation_id: str = Field(description="Owning federation")
    name: str = Field(description="Title name (e.g. 'World Heavyweight Championship')")
    tier: TitleTier = Field(default=TitleTier.MID_CARD, description="Title tier")
    reigns: List[Reign] = Field(default_factory=list, description="Lineage (ordered, most recent last)")
    prestige: int = Field(default=50, ge=0, le=100, description="Title prestige 0–100")


# ---------------------------------------------------------------------------
# Teams & Stables
# ---------------------------------------------------------------------------
class Team(BaseModel):
    """Tag team or trio."""
    team_id: str = Field(description="Unique team identifier")
    federation_id: str = Field(description="Owning federation")
    name: str = Field(description="Team name")
    member_ids: List[str] = Field(default_factory=list, description="Agent IDs in team")
    formed_date: date = Field(description="When team formed")
    disbanded_date: Optional[date] = Field(default=None, description="When team disbanded")


class Stable(BaseModel):
    """Faction (stable)."""
    stable_id: str = Field(description="Unique stable identifier")
    federation_id: str = Field(description="Owning federation")
    name: str = Field(description="Stable name")
    leader_id: Optional[str] = Field(default=None, description="Agent ID of leader")
    member_ids: List[str] = Field(default_factory=list, description="Agent IDs in stable")
    formed_date: date = Field(description="When stable formed")
    disbanded_date: Optional[date] = Field(default=None, description="When stable disbanded")


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------
class StorylinePayoffPhase(str, Enum):
    """When a storyline is planned to climax (for crafting the 4-year arc)."""
    BUILD_UP = "build_up"
    ANCHOR = "anchor"
    AFTERMATH = "aftermath"


class StorylineType(str, Enum):
    """Type of storyline."""
    FEUD = "feud"
    ALLIANCE = "alliance"
    BETRAYAL = "betrayal"
    TITLE_CHASE = "title_chase"


class StorylineStatus(str, Enum):
    """Storyline status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    DROPPED = "dropped"


class Storyline(BaseModel):
    """Narrative arc: feud, alliance, angle."""
    storyline_id: str = Field(description="Unique storyline identifier")
    federation_id: str = Field(description="Owning federation")
    title: str = Field(description="Storyline title")
    storyline_type: StorylineType = Field(default=StorylineType.FEUD)
    participant_ids: List[str] = Field(default_factory=list, description="Agent IDs involved")
    status: StorylineStatus = Field(default=StorylineStatus.ACTIVE)
    heat: int = Field(default=50, ge=0, le=100, description="Storyline heat 0–100")
    start_date: date = Field(description="When storyline started")
    end_date: Optional[date] = Field(default=None, description="When storyline ended")
    payoff_phase: Optional[StorylinePayoffPhase] = Field(default=None, description="Planned climax: build_up, anchor, or aftermath")


# ---------------------------------------------------------------------------
# Match Result (for history/records)
# ---------------------------------------------------------------------------
class MatchResult(BaseModel):
    """Recorded outcome of a match for history and records."""
    match_result_id: str = Field(description="Unique result identifier")
    match_id: str = Field(description="Match that produced this result")
    card_id: str = Field(description="Card this match was on")
    federation_id: str = Field(description="Owning federation")
    participant_ids: List[str] = Field(default_factory=list, description="Participants in match")
    winner_id: Optional[str] = Field(default=None, description="Winner (from finisher)")
    title_id: Optional[str] = Field(default=None, description="Title if title match")
    title_changed: bool = Field(default=False, description="True if title changed hands")
    storyline_id: Optional[str] = Field(default=None, description="Storyline advanced by this match")
    completed_at: datetime = Field(default_factory=datetime.utcnow)
