"""
Staff: announcers, referees, valets, managers.

Each has distinct attributes and behavior in the simulation.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AnnouncerType(str, Enum):
    """Announcer role on broadcast."""
    PLAY_BY_PLAY = "play_by_play"
    COLOR = "color"
    SPECIAL = "special"


class AnnouncerProfile(BaseModel):
    """Announcer-specific profile (extends agent with role=announcer)."""
    agent_id: str = Field(description="Announcer agent ID")
    announcer_type: AnnouncerType = Field(default=AnnouncerType.COLOR)
    signature_phrases: List[str] = Field(default_factory=list, description="Catchphrases")
    bias_toward: Optional[str] = Field(default=None, description="Agent ID of favorite wrestler")
    voice_style: Optional[str] = Field(default=None, description="e.g. excited, calm")
    metadata: dict = Field(default_factory=dict)


class RefereeProfile(BaseModel):
    """Referee-specific profile (extends agent with role=referee)."""
    agent_id: str = Field(description="Referee agent ID")
    strictness: int = Field(default=5, ge=1, le=10, description="1=lenient, 10=strict")
    specialty_matches: List[str] = Field(default_factory=list, description="e.g. hardcore, cage")
    metadata: dict = Field(default_factory=dict)


class ManagerProfile(BaseModel):
    """Manager: represents wrestler(s) at ringside, cuts promos, influences booking."""
    agent_id: str = Field(description="Manager agent ID")
    client_ids: List[str] = Field(default_factory=list, description="Wrestler(s) managed")
    alignment: str = Field(default="heel", description="babyface, heel, tweener")
    mic_skill: int = Field(default=5, ge=1, le=10, description="Promo ability 1-10")
    metadata: dict = Field(default_factory=dict)


class ValetProfile(BaseModel):
    """Valet: accompanies wrestler(s), provides support, occasional interference."""
    agent_id: str = Field(description="Valet agent ID")
    client_ids: List[str] = Field(default_factory=list, description="Wrestler(s) accompanied")
    interference_tendency: int = Field(default=5, ge=1, le=10, description="1=never, 10=often")
    metadata: dict = Field(default_factory=dict)
