"""
Card structure: card types, segments, breaks, and POV (temporal streams).

Multiple temporal streams run simultaneously with selective information sharing:
- TV Audience: broadcast view (produced)
- Crowd: live view (raw)
- Backstage: behind-the-scenes (not seen by TV/crowd)
- Promoter: orchestration view (sees all)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import date
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Card types (hierarchy by stakes/production)
# ---------------------------------------------------------------------------
class CardType(str, Enum):
    """Card type by stakes and production level."""
    HOUSE = "house"               # House show, minimal production, crowd-only feel
    MINOR_TV = "minor_tv"         # Main Event, NXT Level Up - small audience
    MAJOR_TV = "major_tv"         # Raw, Dynamite, SmackDown - full production
    PPV = "ppv"                   # Monthly PPV (Clash at the Castle)
    MARQUEE_SEASON = "marquee_season"  # Seasonal climax (Survivor Series, Royal Rumble)
    MARQUEE_YEAR = "marquee_year"      # Annual climax (WrestleMania)


# ---------------------------------------------------------------------------
# POV / temporal streams
# ---------------------------------------------------------------------------
class POV(str, Enum):
    """Point of view / temporal stream. Each has its own information pool."""
    RING = "ring"         # Participant, referee - in-ring only
    TV = "tv"             # TV audience, announcer - broadcast view (edited)
    CROWD = "crowd"       # Live crowd - raw live view
    BACKSTAGE = "backstage"  # Backstage - behind-the-scenes (not seen by TV/crowd)
    PROMOTER = "promoter"    # Promoter - orchestration view (sees all)


# Which POVs see which segment types (by default)
SEGMENT_POV_VISIBILITY: dict[str, List[POV]] = {
    "opening": [POV.TV, POV.CROWD, POV.BACKSTAGE, POV.PROMOTER],
    "match": [POV.RING, POV.TV, POV.CROWD, POV.PROMOTER],
    "promo": [POV.TV, POV.CROWD, POV.BACKSTAGE, POV.PROMOTER],
    "backstage": [POV.BACKSTAGE, POV.PROMOTER],
    "commercial": [POV.TV],  # Crowd sees intermission, not "commercial"
    "intermission": [POV.CROWD, POV.BACKSTAGE, POV.PROMOTER],
    "dark_match": [POV.CROWD, POV.BACKSTAGE, POV.PROMOTER],
    "closing": [POV.TV, POV.CROWD, POV.BACKSTAGE, POV.PROMOTER],
    "preshow": [POV.BACKSTAGE, POV.PROMOTER],
}

# POV -> roles that have that POV (for non-match segment ticks)
POV_TO_ROLES: dict[str, List[str]] = {
    "ring": ["participant", "referee", "valet", "manager"],
    "tv": ["announcer"],
    "crowd": ["crowd"],
    "backstage": ["backstage"],
    "promoter": ["promoter"],
}

# Segment type -> roles to run for one segment tick (before/after match segments)
# Derived from SEGMENT_POV_VISIBILITY: which roles see this segment
SEGMENT_ROLES: dict[str, List[str]] = {
    "opening": ["announcer", "crowd", "backstage", "promoter"],
    "promo": ["announcer", "crowd", "backstage", "promoter"],
    "backstage": ["backstage", "promoter"],
    "commercial": ["announcer"],  # TV only; announcer does throw to break
    "intermission": ["crowd", "backstage", "promoter"],
    "closing": ["announcer", "crowd", "backstage", "promoter"],
    "preshow": ["backstage", "promoter"],
    "prep": ["backstage", "promoter"],  # Day before: travel, prep for tomorrow's card
    "fallout": ["backstage", "promoter"],  # Day after: react to results, plan next
}


# ---------------------------------------------------------------------------
# Segment types
# ---------------------------------------------------------------------------
class SegmentType(str, Enum):
    """Type of card segment."""
    OPENING = "opening"
    MATCH = "match"
    PROMO = "promo"
    BACKSTAGE = "backstage"
    COMMERCIAL = "commercial"
    INTERMISSION = "intermission"
    DARK_MATCH = "dark_match"
    CLOSING = "closing"
    PRESHOW = "preshow"


# ---------------------------------------------------------------------------
# Segment model
# ---------------------------------------------------------------------------
class Segment(BaseModel):
    """A single segment on a card (opening, match, promo, backstage, etc.)."""
    segment_id: str = Field(description="Unique segment identifier")
    card_id: str = Field(description="Parent card")
    segment_type: SegmentType = Field(description="Type of segment")
    order: int = Field(description="Order on card (1-based)")
    match_id: Optional[str] = Field(default=None, description="Match ID if type=match")
    participant_ids: List[str] = Field(default_factory=list, description="Participants (promo/backstage)")
    duration_blocks: int = Field(default=1, description="Duration in blocks (1 for non-match, N for match)")
    pov_visible: List[POV] = Field(default_factory=list, description="Which POVs see this segment (default from SEGMENT_POV_VISIBILITY)")
    metadata: dict = Field(default_factory=dict, description="Extra data (e.g. commercial length)")


# ---------------------------------------------------------------------------
# Extended Card with segments and card type
# ---------------------------------------------------------------------------
class FullCard(BaseModel):
    """
    Full card with segments, breaks, and card type.

    Replaces flat matches list with ordered segments (opening, match, commercial, etc.).
    """
    card_id: str = Field(description="Unique card identifier")
    federation_id: str = Field(description="Owning federation")
    name: str = Field(description="Card name")
    card_date: Optional[date] = Field(default=None)
    week_id: Optional[str] = Field(default=None)
    venue_id: Optional[str] = Field(default=None, description="Venue where the card is held")
    show_type: Optional[str] = Field(default=None, description="house, tv, ppv, dark")
    prep_date: Optional[date] = Field(default=None, description="Day before (travel/prep)")
    travel_squad_ids: Optional[List[str]] = Field(default=None, description="Agent IDs on this show")
    card_type: CardType = Field(default=CardType.MAJOR_TV)
    segments: List[Segment] = Field(default_factory=list, description="Ordered segments")
    # Legacy: matches extracted from match segments
    matches: List[dict] = Field(default_factory=list, description="Matches (from match segments)")

    def get_match_segments(self) -> List[Segment]:
        """Return segments that are matches."""
        return [s for s in self.segments if s.segment_type == SegmentType.MATCH]

    def get_segments_for_pov(self, pov: "POV") -> List["Segment"]:
        """Return segments visible to given POV."""
        result = []
        for s in self.segments:
            visible = s.pov_visible if s.pov_visible else SEGMENT_POV_VISIBILITY.get(s.segment_type.value, [])
            if pov in visible:
                result.append(s)
        return result


# ---------------------------------------------------------------------------
# Card type → segment template (suggested structure)
# ---------------------------------------------------------------------------
CARD_TYPE_SEGMENT_TEMPLATE: dict[CardType, List[SegmentType]] = {
    CardType.HOUSE: [
        SegmentType.OPENING,
        SegmentType.MATCH,
        SegmentType.INTERMISSION,
        SegmentType.MATCH,
        SegmentType.INTERMISSION,
        SegmentType.MATCH,
        SegmentType.CLOSING,
        SegmentType.DARK_MATCH,
    ],
    CardType.MINOR_TV: [
        SegmentType.OPENING,
        SegmentType.MATCH,
        SegmentType.COMMERCIAL,
        SegmentType.MATCH,
        SegmentType.CLOSING,
    ],
    CardType.MAJOR_TV: [
        SegmentType.OPENING,
        SegmentType.PROMO,
        SegmentType.MATCH,
        SegmentType.COMMERCIAL,
        SegmentType.BACKSTAGE,
        SegmentType.MATCH,
        SegmentType.COMMERCIAL,
        SegmentType.MATCH,
        SegmentType.CLOSING,
    ],
    CardType.PPV: [
        SegmentType.PRESHOW,
        SegmentType.OPENING,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.CLOSING,
    ],
    CardType.MARQUEE_SEASON: [
        SegmentType.OPENING,
        SegmentType.PROMO,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.CLOSING,
    ],
    CardType.MARQUEE_YEAR: [
        SegmentType.OPENING,
        SegmentType.PROMO,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.MATCH,
        SegmentType.CLOSING,
    ],
}


# ---------------------------------------------------------------------------
# Card run state (glue between segments: before match, match, after match)
# ---------------------------------------------------------------------------
class CardRunState(BaseModel):
    """
    State accumulated as the card runs: previous segment, last match result,
    and optional segment summaries. Passed into hints so each segment (and match)
    knows what came before and what just happened.
    """
    segment_index: int = Field(default=0, description="Current segment index (0-based)")
    previous_segment_type: Optional[str] = Field(default=None, description="Type of segment that just ran")
    last_match_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="After a match: winner_id, match_id, participant_ids, narrative_summary",
    )
    segment_results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="One entry per completed segment (type, order, optional summary)",
    )

    def to_hint_dict(self) -> Dict[str, Any]:
        """For inclusion in promoter_hints / context."""
        return {
            "segment_index": self.segment_index,
            "previous_segment_type": self.previous_segment_type,
            "last_match_result": self.last_match_result,
            "segments_completed": len(self.segment_results),
        }
