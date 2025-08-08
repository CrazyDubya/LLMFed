"""
SQLAlchemy database models for LLMFed.

These models define the database schema and relationships for the wrestling
federation simulator.
"""

from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to agents
    agents = relationship("AgentDB", back_populates="federation")


class EngineRequestDB(Base):
    """SQLAlchemy model for engine requests."""
    __tablename__ = "engine_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=False, unique=True)
    agent_id = Column(String, nullable=False)
    due_tick = Column(Integer, nullable=False)
    context_json = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NarrativeLogDB(Base):
    """SQLAlchemy model for narrative logs."""
    __tablename__ = "narrative_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick_id = Column(String, nullable=False)
    time_index = Column(Integer, nullable=False)
    agent_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)