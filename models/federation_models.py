"""
Federation models: federations, PPV events, booking visions, wrestler pushes, talent offers.
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, JSON, ForeignKey, Text, Boolean,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from models.db_models import Base


def _utc_now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Federations (game-level, distinct from legacy FederationDB)
# ---------------------------------------------------------------------------

class GameFederationDB(Base):
    """A wrestling federation/promotion in the game world."""
    __tablename__ = "game_federations"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    short_name = Column(String(10), nullable=True)
    description = Column(Text, nullable=True)
    is_npc = Column(Boolean, default=True)  # AI-controlled unless player owns it
    prestige = Column(Integer, default=50)  # 0-100 scale
    budget = Column(Float, default=100000.0)
    weekly_revenue = Column(Float, default=0.0)
    weekly_expenses = Column(Float, default=0.0)
    tv_deal_value = Column(Float, default=0.0)
    home_region = Column(String(50), default="Northeast")
    style = Column(String(50), default="Sports Entertainment")  # Strong style, lucha, etc.
    founded_date = Column(String(10), nullable=True)  # In-game date
    market_share = Column(Float, default=0.0)  # Percentage of total viewership
    momentum = Column(Integer, default=50)  # 0-100, how "hot" the fed is
    fanbase_loyalty = Column(Integer, default=50)  # 0-100, how loyal the audience is (affects floor)
    regional_strength = Column(JSON, default=dict)  # {region: 0-100} strength per market
    is_active = Column(Boolean, default=True)
    ai_personality = Column(JSON, default=dict)  # LLM personality traits for NPC booking
    # --- Kayfabe Profile ---
    kayfabe_strictness = Column(Integer, default=50)  # 0-100, how strictly kayfabe is enforced
    allows_worked_shoots = Column(Boolean, default=True)  # Whether worked shoots are permitted
    social_media_policy = Column(String(20), default="guided")  # strict_kayfabe, guided, free
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    world = relationship("WorldDB", back_populates="federations")
    talent_offers = relationship("TalentOfferDB", back_populates="federation")
    owner_player = relationship("PlayerDB", back_populates="federation",
                                foreign_keys="PlayerDB.federation_id", uselist=False)
    contracts = relationship("ContractDB", back_populates="federation")
    shows = relationship("ShowDB", back_populates="federation")
    championships = relationship("ChampionshipDB", back_populates="federation")

    __table_args__ = (
        UniqueConstraint("world_id", "name", name="uq_federation_name_world"),
    )


# ---------------------------------------------------------------------------
# Talent Offers (Inter-Federation)
# ---------------------------------------------------------------------------

class TalentOfferDB(Base):
    """A contract offer from a federation to a wrestler (poaching/signing)."""
    __tablename__ = "talent_offers"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    salary_offered = Column(Float, default=2000.0)
    contract_length_weeks = Column(Integer, default=52)
    status = Column(String(20), default="pending")  # pending, accepted, rejected, expired
    offered_date = Column(String(10), nullable=False)
    expires_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utc_now)

    federation = relationship("GameFederationDB", back_populates="talent_offers")


# ---------------------------------------------------------------------------
# Promoter Vision & Booking Plans
# ---------------------------------------------------------------------------

class PPVEventDB(Base):
    """A planned or completed PPV event on a federation's annual calendar.

    PPVs are the destination -- weekly TV exists to build toward them.
    Created at world gen for the full year, then rolled forward annually.
    """
    __tablename__ = "ppv_events"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # "WrestleMania", "SummerSlam", etc.
    theme = Column(String(50), nullable=True)  # tournament, grudge_matches, showcase, etc.
    scheduled_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    is_crown_jewel = Column(Boolean, default=False)  # The big one (WrestleMania equivalent)
    is_completed = Column(Boolean, default=False)
    show_id = Column(String, ForeignKey("shows.id"), nullable=True)  # Linked when show is created
    capacity = Column(Integer, default=10000)
    venue = Column(String(100), nullable=True)

    # Penciled-in main event (may change)
    planned_main_event = Column(JSON, default=dict)  # {wrestler_ids: [], title_id: str, storyline_id: str}
    planned_matches = Column(JSON, default=list)  # [{wrestler_ids, title_id, match_type, storyline_id, status: "penciled"|"ink"}]

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class BookingVisionDB(Base):
    """A federation's strategic booking vision -- the promoter's master plan.

    This is the 'big picture': identity, goals, who to push, what the
    crown jewel PPV should look like. NPC feds get one at world gen;
    player feds get a suggested one they can edit.
    """
    __tablename__ = "booking_visions"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, unique=True)

    # Strategic identity
    identity = Column(String(200), nullable=True)  # "The workrate company", "Sports entertainment empire"
    long_term_goal = Column(String(200), nullable=True)  # "Become #1 federation", "Dominate the Southeast"
    crown_jewel_vision = Column(JSON, default=dict)  # {main_event_dream: str, theme: str, ideal_wrestlers: []}

    # Push tiers -- who the promoter sees at each level
    push_tiers = Column(JSON, default=dict)
    # Structure: {
    #   "main_event": [wrestler_id, ...],
    #   "upper_midcard": [wrestler_id, ...],
    #   "midcard": [wrestler_id, ...],
    #   "lower_card": [wrestler_id, ...],
    #   "jobber": [wrestler_id, ...],
    #   "developmental": [wrestler_id, ...],
    # }

    # Wrestler trajectories -- planned direction for specific wrestlers
    trajectories = Column(JSON, default=dict)
    # Structure: {wrestler_id: {
    #   "direction": "rising"|"established"|"transitional"|"cooling_off",
    #   "target_tier": "main_event",
    #   "target_date": "2026-06-01",  # When they should arrive
    #   "notes": "Next big babyface",
    #   "status": "penciled"|"ink",
    # }}

    # Title pipelines -- who's next for each belt
    title_pipelines = Column(JSON, default=dict)
    # Structure: {championship_id: {
    #   "current_holder": wrestler_id,
    #   "planned_reign_weeks": 16,
    #   "next_challengers": [wrestler_id, wrestler_id],
    #   "dream_match": {wrestler_ids: [], ppv_event_id: str},
    # }}

    # Planned feuds/storylines that haven't started yet
    planned_storylines = Column(JSON, default=list)
    # [{wrestler_ids: [], type: "feud"|"betrayal", target_ppv_id: str, status: "penciled"|"ink"}]

    # Adaptation log -- what changed and why
    adaptation_log = Column(JSON, default=list)
    # [{date: str, change: str, reason: str}]

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class WrestlerPushDB(Base):
    """Tracks a wrestler's current push status and trajectory within a federation.

    Separate from BookingVisionDB for efficient querying -- 'who are my main eventers?'
    """
    __tablename__ = "wrestler_pushes"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)

    push_tier = Column(String(20), default="midcard")  # main_event, upper_midcard, midcard, lower_card, jobber, developmental
    direction = Column(String(20), default="established")  # rising, established, transitional, cooling_off
    confidence = Column(Integer, default=50)  # 0-100, how confident the booker is in this push
    protected = Column(Boolean, default=False)  # Protected wrestlers don't job clean
    weeks_at_tier = Column(Integer, default=0)  # How long they've been at current tier

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("federation_id", "wrestler_id", name="uq_push_fed_wrestler"),
    )
