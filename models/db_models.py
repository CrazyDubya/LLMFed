"""
SQLAlchemy database models for LLMFed.

These models define the database schema and relationships for the wrestling
federation simulator.
"""

from sqlalchemy import Boolean, Column, String, Integer, DateTime, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
import uuid


def _utc_now():
    return datetime.now(timezone.utc)


Base = declarative_base()


class AgentDB(Base):
    """SQLAlchemy model for the agents table."""
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="participant")
    gimmick_description = Column(Text, nullable=False)
    llm_config = Column(JSON, nullable=False)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=True)
    current_heat = Column(Integer, default=0)
    momentum = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationship to federation
    federation = relationship("FederationDB", back_populates="agents")


class FederationDB(Base):
    """SQLAlchemy model for the federations table."""
    __tablename__ = "federations"

    federation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    tier = Column(String, nullable=False, default="independent")
    owner_user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationship to agents
    agents = relationship("AgentDB", back_populates="federation")


class EngineRequestDB(Base):
    """SQLAlchemy model for engine requests."""
    __tablename__ = "engine_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=False, unique=True)
    agent_id = Column(String, nullable=False, index=True)
    due_tick = Column(Integer, nullable=False)
    context_json = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class NarrativeLogDB(Base):
    """SQLAlchemy model for narrative logs."""
    __tablename__ = "narrative_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick_id = Column(String, nullable=False)
    time_index = Column(Integer, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utc_now)

    __table_args__ = (
        Index("ix_narrative_tick_time", "tick_id", "time_index"),
    )


class TitleDB(Base):
    """Championship title used by tier-9 memory records. Separate from game championships."""
    __tablename__ = "titles"

    title_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    tier = Column(String, nullable=False, default="mid_card")
    prestige = Column(Integer, default=50)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class ReignDB(Base):
    """Championship reign history for tier-9 memory recall."""
    __tablename__ = "reigns"

    reign_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title_id = Column(String, ForeignKey("titles.title_id"), nullable=False)
    champion_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    end_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utc_now)


class VenueDB(Base):
    """Place a card happens. Game shows still store a venue name string."""
    __tablename__ = "venues"

    venue_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    capacity = Column(Integer, default=5000)
    venue_type = Column(String, default="arena")
    concessions_available = Column(Boolean, default=True)
    ppv_capable = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class Tier9ImmutableDB(Base):
    """Append-only card facts for memory recall."""
    __tablename__ = "tier9_immutables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    card_id = Column(String, nullable=False, index=True)
    card_date = Column(DateTime, nullable=False)
    card_name = Column(String, nullable=True)
    attendance = Column(Integer, default=0)
    match_records_json = Column(JSON, nullable=False, default=list)
    title_changes_json = Column(JSON, nullable=False, default=list)
    recorded_at = Column(DateTime, default=_utc_now)


class CardRevenueDB(Base):
    """Gate, PPV, and concession totals for a card."""
    __tablename__ = "card_revenue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String, nullable=False, index=True)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    gate_revenue = Column(Integer, default=0)
    ppv_revenue = Column(Integer, default=0)
    concession_revenue = Column(Integer, default=0)
    attendance = Column(Integer, default=0)
    total_revenue = Column(Integer, default=0)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=_utc_now)

