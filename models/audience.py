"""
Audience: fan types, demographics, viewing contexts, and fan preferences.

- FanType: superfan, super_viewer, common_viewer, common_fan
- Demographics: age, region, engagement
- AudienceSegment: mix of fan types + favorite/hated for crowd simulation
- ViewingContext: microcosms (arena, living_room, pub, watch_party, newsroom)
- FanPreferences: favorites and hated (so fans react with bias)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FanType(str, Enum):
    """Audience member type (affects reaction intensity, knowledge, loyalty)."""
    SUPERFAN = "superfan"        # Hardcore, knows history, intense reactions
    SUPER_VIEWER = "super_viewer"  # Watches every show, high engagement
    COMMON_VIEWER = "common_viewer"  # Regular viewer, moderate engagement
    COMMON_FAN = "common_fan"    # Casual fan, lower engagement


class AgeBracket(str, Enum):
    """Age demographic bracket."""
    KIDS = "kids"        # 6-12
    TEENS = "teens"      # 13-17
    YOUNG_ADULT = "young_adult"  # 18-24
    ADULT = "adult"      # 25-44
    MATURE = "mature"    # 45-64
    SENIOR = "senior"    # 65+


class Region(str, Enum):
    """Geographic/audience region."""
    LOCAL = "local"      # Home market
    REGIONAL = "regional"
    NATIONAL = "national"
    INTERNATIONAL = "international"


# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------
class AudienceDemographics(BaseModel):
    """Demographics of the federation's audience (in-world)."""
    federation_id: str = Field(description="Federation ID")
    age_distribution: dict = Field(
        default_factory=lambda: {"kids": 5, "teens": 10, "young_adult": 25, "adult": 40, "mature": 15, "senior": 5},
    )
    region_distribution: dict = Field(
        default_factory=lambda: {"local": 30, "regional": 40, "national": 25, "international": 5},
    )
    fan_type_distribution: dict = Field(
        default_factory=lambda: {"superfan": 10, "super_viewer": 20, "common_viewer": 40, "common_fan": 30},
    )
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Audience segment (for crowd agent context)
# ---------------------------------------------------------------------------
class ViewingContextType(str, Enum):
    """Where the audience is watching; microcosms that rise and pop."""
    ARENA_SECTION = "arena_section"   # Live crowd, section or aggregate
    LIVING_ROOM = "living_room"      # At-home TV/stream
    PUB = "pub"                      # Bar watch party
    WATCH_PARTY = "watch_party"      # Informal group (friend's house, dorm)
    NEWSROOM = "newsroom"            # Critics/journalists filing (real-time or next-day)


class ViewingContext(BaseModel):
    """
    Microcosm where people watch: arena, living room, pub, watch party, newsroom.

    Bubbles that activate when a show is on or when coverage is filed.
    """
    context_id: str = Field(description="Unique context identifier")
    context_type: ViewingContextType = Field(default=ViewingContextType.ARENA_SECTION)
    venue_id: Optional[str] = Field(default=None, description="Physical venue if pub/bar at a place")
    card_id: Optional[str] = Field(default=None, description="Card being watched if active")
    metadata: dict = Field(default_factory=dict)


class FanPreferences(BaseModel):
    """Per-segment or per-demo favorites and hated; fans react with bias."""
    favorite_agent_ids: List[str] = Field(default_factory=list, description="Agents this crowd cheers for")
    hated_agent_ids: List[str] = Field(default_factory=list, description="Agents this crowd boos (beyond heel heat)")


class AudienceSegment(BaseModel):
    """
    Mix of fan types for a given show/venue, plus favorite/hated for reaction bias.

    Used to weight crowd reactions: superfans react more intensely,
    common_fans react less; favorites get cheered, hated get booed.
    """
    segment_id: str = Field(description="Unique segment identifier")
    card_id: Optional[str] = Field(default=None, description="Card this segment is for")
    venue_type: str = Field(default="arena", description="arena, stadium, tv_only")
    superfan_pct: int = Field(default=10, ge=0, le=100)
    super_viewer_pct: int = Field(default=20, ge=0, le=100)
    common_viewer_pct: int = Field(default=40, ge=0, le=100)
    common_fan_pct: int = Field(default=30, ge=0, le=100)
    favorite_agent_ids: List[str] = Field(default_factory=list, description="Crowd favorites")
    hated_agent_ids: List[str] = Field(default_factory=list, description="Crowd hated (beyond heel heat)")
    metadata: dict = Field(default_factory=dict)
