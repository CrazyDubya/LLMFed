"""
Archive tiers and memory for federation history.

Tier 0: Last 4 weeks, full detail (narrative, tick-level)
Tier 1: Last year, match-level
Tier 2: 1-10 years, season-level
Tier 3: 10-100 years, decade-level
Tier 9: Absolute immutables — card dates, attendance, match card and results,
        title holder and changes. Append-only, never contradicted.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


class ArchiveTier(IntEnum):
    """Memory/archive tier. Higher = more compressed, longer retention."""
    TIER_0 = 0   # Last 4 weeks, full detail
    TIER_1 = 1   # Last year, match-level
    TIER_2 = 2   # 1-10 years, season-level
    TIER_3 = 3   # 10-100 years, decade-level
    TIER_9 = 9   # Absolute immutables: card dates, attendance, match card/results, title changes


# Time windows for each tier (approximate)
TIER_WINDOWS: Dict[int, str] = {
    0: "4 weeks",
    1: "1 year",
    2: "10 years",
    3: "100 years",
    9: "forever",  # Immutables never expire
}


class ImmutableMatchRecord(BaseModel):
    """One match in Tier 9 — immutable fact."""
    match_id: str
    participant_ids: List[str]
    winner_id: Optional[str]
    stipulation: str = "StandardMatch"
    title_id: Optional[str] = None
    title_changed: bool = False


class ImmutableTitleChange(BaseModel):
    """One title change in Tier 9 — immutable fact."""
    title_id: str
    new_champion_id: str
    previous_champion_id: Optional[str] = None


class Tier9CardRecord(BaseModel):
    """Tier 9 immutable record for one card. Append-only."""
    card_id: str
    card_date: date
    card_name: str
    federation_id: str
    attendance: int = 0
    match_records: List[ImmutableMatchRecord] = Field(default_factory=list)
    title_changes: List[ImmutableTitleChange] = Field(default_factory=list)
    recorded_at: Optional[datetime] = None
