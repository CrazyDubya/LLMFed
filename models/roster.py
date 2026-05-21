"""
Roster, contracts, wrestler stats, personalities, tenure, injuries.

- Roster: federation's active talent list
- Contract: agent-federation agreement with terms (start_date = join/debut with this fed)
- Tenure: veteran / rising / newcomer (who joined when) for anchor-card mix
- Injury: time off, returns, surprise comebacks
- WrestlerStats, WrestlerPersonality
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import date
from pydantic import BaseModel, Field


class TenureTier(str, Enum):
    """Talent tier by tenure (relative to anchor or reference date)."""
    VETERAN = "veteran"   # With fed since early (join before world_start + 12 months)
    RISING = "rising"     # Joined mid-build (12-24 months before anchor)
    NEWCOMER = "newcomer" # Joined recently (last 12 months before anchor or after)


class ContractType(str, Enum):
    """Contract type."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    PPV_APPEARANCE = "ppv_appearance"
    DEVELOPMENTAL = "developmental"
    LEGEND = "legend"


class ContractStatus(str, Enum):
    """Contract status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


class Contract(BaseModel):
    """Agent-federation contract."""
    contract_id: str = Field(description="Unique contract identifier")
    agent_id: str = Field(description="Agent (wrestler/staff) ID")
    federation_id: str = Field(description="Federation ID")
    contract_type: ContractType = Field(default=ContractType.FULL_TIME)
    status: ContractStatus = Field(default=ContractStatus.ACTIVE)
    start_date: date = Field(description="Contract start")
    end_date: Optional[date] = Field(default=None, description="Contract end (null = ongoing)")
    salary_terms: Optional[Dict[str, Any]] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WrestlerStats(BaseModel):
    """Per-wrestler stats (wins, losses, title reigns, etc.)."""
    agent_id: str = Field(description="Wrestler agent ID")
    federation_id: str = Field(description="Federation ID")
    wins: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)
    draws: int = Field(default=0, ge=0)
    no_contests: int = Field(default=0, ge=0)
    title_reigns: int = Field(default=0, ge=0)
    total_matches: int = Field(default=0, ge=0)
    main_events: int = Field(default=0, ge=0)
    ppv_matches: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        if self.total_matches <= 0:
            return 0.0
        return self.wins / self.total_matches


class WrestlerPersonality(BaseModel):
    """
    Wrestler personality: gimmick (TV/crowd) vs personal (backstage).
    """
    agent_id: str = Field(description="Wrestler agent ID")
    gimmick_traits: Dict[str, int] = Field(default_factory=dict)
    personal_traits: Dict[str, int] = Field(default_factory=dict)
    backstage_notes: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Roster(BaseModel):
    """Federation roster: contracted wrestlers and staff."""
    federation_id: str = Field(description="Federation ID")
    wrestler_ids: List[str] = Field(default_factory=list)
    staff_ids: List[str] = Field(default_factory=list)
    contracts: List[Contract] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Injury (depth: who's out when, comebacks, surprise returns)
# ---------------------------------------------------------------------------
class Injury(BaseModel):
    """Wrestler injury: out for a period; optional surprise return."""
    injury_id: str = Field(description="Unique injury id")
    agent_id: str = Field(description="Wrestler agent ID")
    federation_id: str = Field(description="Federation ID")
    injury_type: str = Field(default="unknown", description="e.g. kayfabe, legitimate, storyline")
    out_from: date = Field(description="First date out")
    out_until: Optional[date] = Field(default=None, description="Return date (null = indefinite)")
    return_surprise: bool = Field(default=False, description="Unadvertised/surprise return")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_out_on(self, d: date) -> bool:
        """True if wrestler is out on date d."""
        if d < self.out_from:
            return False
        if self.out_until is None:
            return True
        return d <= self.out_until
