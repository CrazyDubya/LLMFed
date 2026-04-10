"""
Core world models: users, players, worlds, and world state.
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
# Users & Players
# ---------------------------------------------------------------------------

class UserDB(Base):
    """User account for authentication."""
    __tablename__ = "users"

    # Roles: admin, owner, player, viewer
    VALID_ROLES = ("admin", "owner", "player", "viewer")

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="player")
    api_key = Column(String(64), nullable=True, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    players = relationship("PlayerDB", back_populates="user", cascade="all, delete-orphan")


class PlayerDB(Base):
    """A user's game identity within a world."""
    __tablename__ = "players"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    player_type = Column(String(20), nullable=False)  # promoter or wrestler
    # If promoter, links to a federation. If wrestler, links to a wrestler character.
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    user = relationship("UserDB", back_populates="players")
    world = relationship("WorldDB", back_populates="players")
    federation = relationship("GameFederationDB", back_populates="owner_player", foreign_keys=[federation_id])
    wrestler = relationship("GameWrestlerDB", back_populates="player", foreign_keys=[wrestler_id])

    __table_args__ = (
        UniqueConstraint("user_id", "world_id", name="uq_player_user_world"),
    )


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

class WorldDB(Base):
    """A game world instance (single-player or multiplayer)."""
    __tablename__ = "worlds"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_multiplayer = Column(Boolean, default=False)
    max_players = Column(Integer, default=1)
    current_game_date = Column(String(10), default="2026-01-01")  # YYYY-MM-DD in-game
    current_tick = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    world_config = Column(JSON, default=dict)  # Difficulty, speed, etc.
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    players = relationship("PlayerDB", back_populates="world")
    federations = relationship("GameFederationDB", back_populates="world")
    wrestlers = relationship("GameWrestlerDB", back_populates="world")
    shows = relationship("ShowDB", back_populates="world")
    storylines = relationship("StorylineDB", back_populates="world")
    championships = relationship("ChampionshipDB", back_populates="world")
    world_state = relationship("WorldStateDB", back_populates="world", cascade="all, delete-orphan")
    narrative_logs = relationship("GameNarrativeLogDB", back_populates="world")
    world_news = relationship("WorldNewsDB", back_populates="world")


class WorldStateDB(Base):
    """Key-value store for world-level state."""
    __tablename__ = "world_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    key = Column(String(100), nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    world = relationship("WorldDB", back_populates="world_state")

    __table_args__ = (
        UniqueConstraint("world_id", "key", name="uq_world_state_key"),
    )
