"""
Show and match models: shows, segments, matches, match participants,
match events, promos, and narrative/news logs.
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
# Shows & Segments
# ---------------------------------------------------------------------------

class ShowDB(Base):
    """A wrestling show/event."""
    __tablename__ = "shows"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    show_type = Column(String(20), default="weekly")
    venue = Column(String(100), nullable=True)
    capacity = Column(Integer, default=5000)
    attendance = Column(Integer, nullable=True)
    game_date = Column(String(10), nullable=False)  # In-game date
    is_completed = Column(Boolean, default=False)
    overall_rating = Column(Float, nullable=True)  # 0-5 stars average
    tv_rating = Column(Float, nullable=True)
    gate_revenue = Column(Float, nullable=True)
    ppv_buys = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    world = relationship("WorldDB", back_populates="shows")
    federation = relationship("GameFederationDB", back_populates="shows")
    segments = relationship("ShowSegmentDB", back_populates="show",
                            order_by="ShowSegmentDB.position", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_shows_world_date", "world_id", "game_date"),
        Index("ix_shows_world_completed", "world_id", "is_completed"),
    )


class ShowSegmentDB(Base):
    """A segment within a show (match, promo, backstage, etc.)."""
    __tablename__ = "show_segments"

    id = Column(String, primary_key=True, default=_uuid)
    show_id = Column(String, ForeignKey("shows.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)  # Order in the show
    segment_type = Column(String(20), nullable=False)  # match, promo, backstage, etc.
    match_id = Column(String, ForeignKey("matches.id"), nullable=True)
    promo_id = Column(String, ForeignKey("promos.id"), nullable=True)
    description = Column(Text, nullable=True)  # For non-match/promo segments
    planned_duration_minutes = Column(Integer, default=15)
    actual_duration_minutes = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    crowd_reaction = Column(String(50), nullable=True)  # pop, heat, silence, mixed
    notes = Column(Text, nullable=True)  # Booker's notes
    is_completed = Column(Boolean, default=False)

    show = relationship("ShowDB", back_populates="segments")
    match = relationship("MatchDB", back_populates="segment", uselist=False)
    promo = relationship("PromoDB", back_populates="segment", uselist=False)


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

class MatchDB(Base):
    """A wrestling match within a show."""
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    match_type = Column(String(30), default="singles")
    stipulation = Column(String(100), nullable=True)  # No DQ, Title Match, etc.
    is_title_match = Column(Boolean, default=False)
    championship_id = Column(String, ForeignKey("championships.id"), nullable=True)
    winner_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    finish_type = Column(String(30), nullable=True)
    finish_description = Column(Text, nullable=True)
    match_rating = Column(Float, nullable=True)  # 0.0 - 5.0 stars
    crowd_heat = Column(Integer, default=50)  # Final crowd heat level
    duration_minutes = Column(Integer, nullable=True)
    is_completed = Column(Boolean, default=False)
    # Detailed simulation data
    simulation_log = Column(JSON, default=list)  # Tick-by-tick events
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    participants = relationship("MatchParticipantDB", back_populates="match",
                                cascade="all, delete-orphan")
    events = relationship("MatchEventDB", back_populates="match",
                          order_by="MatchEventDB.tick", cascade="all, delete-orphan")
    segment = relationship("ShowSegmentDB", back_populates="match", uselist=False)


class MatchParticipantDB(Base):
    """A wrestler's participation in a match."""
    __tablename__ = "match_participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    role = Column(String(20), default="competitor")  # competitor, manager, referee, enforcer
    team = Column(Integer, nullable=True)  # Team number for tag matches
    is_winner = Column(Boolean, default=False)
    performance_rating = Column(Float, nullable=True)

    match = relationship("MatchDB", back_populates="participants")
    wrestler = relationship("GameWrestlerDB", back_populates="match_participations")


class MatchEventDB(Base):
    """A single event within a match (move, reversal, highspot, etc.)."""
    __tablename__ = "match_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    tick = Column(Integer, nullable=False)
    acting_wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    target_wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    event_type = Column(String(30), nullable=False)  # move, reversal, highspot, finish, etc.
    description = Column(Text, nullable=False)
    crowd_reaction = Column(String(30), nullable=True)
    heat_change = Column(Integer, default=0)
    momentum_change = Column(Integer, default=0)
    damage = Column(Integer, default=0)

    match = relationship("MatchDB", back_populates="events")


# ---------------------------------------------------------------------------
# Promos
# ---------------------------------------------------------------------------

class PromoDB(Base):
    """An in-character promo/speech segment."""
    __tablename__ = "promos"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)  # The promo text (LLM generated or player written)
    target_wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    promo_type = Column(String(30), default="in_ring")  # in_ring, backstage, interview
    crowd_reaction = Column(String(30), nullable=True)
    heat_generated = Column(Integer, default=0)
    quality_rating = Column(Float, nullable=True)  # 0-5
    game_date = Column(String(10), nullable=True)
    is_player_written = Column(Boolean, default=False)
    player_direction = Column(Text, nullable=True)  # Player's general direction for AI
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="promos",
                            foreign_keys="PromoDB.wrestler_id")
    target_wrestler = relationship("GameWrestlerDB",
                                   foreign_keys="PromoDB.target_wrestler_id")
    segment = relationship("ShowSegmentDB", back_populates="promo", uselist=False)


# ---------------------------------------------------------------------------
# Player Actions (the queue)
# ---------------------------------------------------------------------------

class PlayerActionDB(Base):
    """A player's queued decision awaiting world tick processing."""
    __tablename__ = "player_actions"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    player_id = Column(String, ForeignKey("players.id"), nullable=False, index=True)
    action_type = Column(String(30), nullable=False)
    action_data = Column(JSON, nullable=False)  # Payload specific to action type
    status = Column(String(20), default="pending")
    result = Column(JSON, nullable=True)
    submitted_at = Column(DateTime, default=_utc_now)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_player_actions_pending", "world_id", "status"),
    )


# ---------------------------------------------------------------------------
# Narrative & History
# ---------------------------------------------------------------------------

class GameNarrativeLogDB(Base):
    """World event log - what happened in the game world."""
    __tablename__ = "game_narrative_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    game_date = Column(String(10), nullable=False)
    tick = Column(Integer, nullable=False)
    event_type = Column(String(30), nullable=False)  # match, promo, signing, injury, etc.
    description = Column(Text, nullable=False)
    involved_entities = Column(JSON, default=list)  # List of wrestler/federation IDs
    importance = Column(Integer, default=5)  # 1-10 scale for filtering
    created_at = Column(DateTime, default=_utc_now)

    world = relationship("WorldDB", back_populates="narrative_logs")

    __table_args__ = (
        Index("ix_narrative_world_date", "world_id", "game_date"),
    )


class WorldNewsDB(Base):
    """LLM-generated news articles about the wrestling world."""
    __tablename__ = "world_news"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    headline = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(30), default="general")  # results, rumors, injury, business
    game_date = Column(String(10), nullable=False)
    is_kayfabe = Column(Boolean, default=True)  # In-character vs "dirt sheet"
    source = Column(String(50), default="Wrestling Observer")
    related_entities = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utc_now)

    world = relationship("WorldDB", back_populates="world_news")
