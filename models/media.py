"""
Media and critics: next-day stories, real-time coverage, blogs.

- MediaOutlet: blog, newspaper, TV, podcast
- Critic: byline/agent; bias, style
- Coverage/Story: recap, live blog, editorial; scope (real_time, next_day, recap)
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class OutletType(str, Enum):
    """Type of media outlet."""
    BLOG = "blog"
    NEWSPAPER = "newspaper"
    TV = "tv"
    PODCAST = "podcast"


class CoverageScope(str, Enum):
    """When the piece is published relative to the show."""
    REAL_TIME = "real_time"   # Live blog, live reaction during show
    NEXT_DAY = "next_day"     # Recap, ratings, "what we learned" next morning
    WEEKLY_RECAP = "weekly_recap"
    EDITORIAL = "editorial"   # Opinion, hot take, anytime


class MediaOutlet(BaseModel):
    """Source of coverage: blog, newspaper, TV, podcast."""
    outlet_id: str = Field(description="Unique outlet identifier")
    name: str = Field(description="Outlet name")
    outlet_type: OutletType = Field(default=OutletType.BLOG)
    reach: Optional[str] = Field(default=None, description="e.g. local, national, niche")
    metadata: dict = Field(default_factory=dict)


class Critic(BaseModel):
    """Byline/agent for an outlet; can have bias and style."""
    critic_id: str = Field(description="Unique critic identifier")
    outlet_id: str = Field(description="Owning outlet")
    name: str = Field(description="Byline name")
    bias_toward_agent_id: Optional[str] = Field(default=None, description="Favorite wrestler")
    bias_against_agent_id: Optional[str] = Field(default=None, description="Hated wrestler or gimmick")
    style: Optional[str] = Field(default=None, description="smark, casual, kayfabe")
    metadata: dict = Field(default_factory=dict)


class Coverage(BaseModel):
    """
    A piece of media: recap, live blog, editorial.

    Scope: real_time (during show), next_day (morning after), weekly_recap, editorial.
    """
    coverage_id: str = Field(description="Unique coverage identifier")
    federation_id: str = Field(description="Federation this is about")
    outlet_id: str = Field(description="Publishing outlet")
    critic_id: Optional[str] = Field(default=None, description="Byline")
    scope: CoverageScope = Field(default=CoverageScope.NEXT_DAY)
    target_card_id: Optional[str] = Field(default=None, description="Card being covered")
    target_match_id: Optional[str] = Field(default=None, description="Match or angle")
    headline: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    published_at: Optional[datetime] = Field(default=None)
    metadata: dict = Field(default_factory=dict)
