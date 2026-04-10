"""
Social/relationship models: storylines, wrestler relationships, tag teams,
championships, managers, stables, and their join tables.
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
# Championships
# ---------------------------------------------------------------------------

class ChampionshipDB(Base):
    """A championship title belt."""
    __tablename__ = "championships"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    prestige = Column(Integer, default=50)  # 0-100
    weight_class = Column(String(20), nullable=True)
    is_tag_team = Column(Boolean, default=False)
    current_holder_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    current_reign_start = Column(String(10), nullable=True)
    defenses = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    world = relationship("WorldDB", back_populates="championships")
    federation = relationship("GameFederationDB", back_populates="championships")
    history = relationship("ChampionshipHistoryDB", back_populates="championship",
                           order_by="ChampionshipHistoryDB.reign_start")


class ChampionshipHistoryDB(Base):
    """Record of a title reign."""
    __tablename__ = "championship_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    championship_id = Column(String, ForeignKey("championships.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    reign_start = Column(String(10), nullable=False)
    reign_end = Column(String(10), nullable=True)
    defenses = Column(Integer, default=0)
    how_won = Column(String(50), nullable=True)  # pinfall, submission, etc.
    how_lost = Column(String(50), nullable=True)

    championship = relationship("ChampionshipDB", back_populates="history")
    wrestler = relationship("GameWrestlerDB", back_populates="title_reigns")


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------

class StorylineDB(Base):
    """An active narrative arc in the world."""
    __tablename__ = "storylines"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=True)
    name = Column(String(100), nullable=False)
    storyline_type = Column(String(30), default="feud")
    status = Column(String(20), default="active")
    description = Column(Text, nullable=True)
    heat = Column(Integer, default=50)  # How hot is this angle
    start_date = Column(String(10), nullable=True)
    end_date = Column(String(10), nullable=True)
    planned_blowoff = Column(Text, nullable=True)  # Planned conclusion
    ai_notes = Column(JSON, default=dict)  # LLM context for continuing the story
    kayfabe_level = Column(Integer, default=100)  # 100=pure fiction, 0=shoot; for worked-shoot storylines
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    world = relationship("WorldDB", back_populates="storylines")
    participants = relationship("StorylineParticipantDB", back_populates="storyline",
                                cascade="all, delete-orphan")


class StorylineParticipantDB(Base):
    """A wrestler's role in a storyline."""
    __tablename__ = "storyline_participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    storyline_id = Column(String, ForeignKey("storylines.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    role = Column(String(30), default="protagonist")  # protagonist, antagonist, ally, manager
    joined_date = Column(String(10), nullable=True)
    left_date = Column(String(10), nullable=True)

    storyline = relationship("StorylineDB", back_populates="participants")
    wrestler = relationship("GameWrestlerDB", back_populates="storyline_roles")


# ---------------------------------------------------------------------------
# Wrestler Relationships & Chemistry
# ---------------------------------------------------------------------------

class WrestlerRelationshipDB(Base):
    """Tracks the history and chemistry between two wrestlers."""
    __tablename__ = "wrestler_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    wrestler1_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    wrestler2_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    matches_together = Column(Integer, default=0)
    total_rating = Column(Float, default=0.0)  # Sum of match ratings for avg calculation
    chemistry_score = Column(Float, default=0.0)  # Computed: total_rating / matches_together
    rivalry_heat = Column(Integer, default=0)  # 0-100, intensity of rivalry
    last_match_date = Column(String(10), nullable=True)
    # --- Real vs Kayfabe relationship layers ---
    relationship_type = Column(String(20), default="professional")  # professional, personal, romantic, family, mentorship
    kayfabe_alignment = Column(String(20), nullable=True)  # allies, rivals, tag_partners, neutral (on-screen)
    real_relationship = Column(String(20), nullable=True)  # friends, enemies, indifferent, romantic (backstage)
    trust_level = Column(Integer, default=50)  # 0-100, real interpersonal trust
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("world_id", "wrestler1_id", "wrestler2_id",
                         name="uq_wrestler_relationship"),
        Index("ix_relationship_pair", "wrestler1_id", "wrestler2_id"),
    )


# ---------------------------------------------------------------------------
# Tag Teams
# ---------------------------------------------------------------------------

class TagTeamDB(Base):
    """A tag team partnership between two wrestlers."""
    __tablename__ = "tag_teams"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    wrestler1_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    wrestler2_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    team_chemistry = Column(Integer, default=30)  # 0-100
    team_finisher_name = Column(String(100), nullable=True)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    formed_date = Column(String(10), nullable=True)
    dissolved_date = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


# ---------------------------------------------------------------------------
# Managers & Valets — Dedicated non-competitor characters
# ---------------------------------------------------------------------------

class ManagerDB(Base):
    """A manager/valet character — dedicated to the craft of management but
    capable of occasional wrestling if the story demands it.

    Managers are separate from wrestlers: they have their own archetype,
    promo voice, and stat profile focused on charisma and interference
    rather than in-ring work.  Think Paul Heyman, Bobby Heenan, Jim Cornette.
    """
    __tablename__ = "managers"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    real_name = Column(String(100), nullable=True)
    gender = Column(String(10), default="male")  # male, female, non_binary

    # Character identity
    alignment = Column(String(10), default="heel")  # face, heel, tweener
    archetype = Column(String(30), default="scheming_manager")  # ManagerArchetype values
    personality_traits = Column(JSON, default=list)  # e.g. ["cunning", "loud", "manipulative"]
    catchphrase = Column(String(200), nullable=True)
    entrance_music = Column(String(100), nullable=True)

    # Manager-specific stats (primary)
    charisma = Column(Integer, default=60)       # 0-100
    mic_skill = Column(Integer, default=60)      # 0-100
    cunning = Column(Integer, default=50)        # 0-100, ability to scheme & manipulate
    interference_skill = Column(Integer, default=40)  # 0-100, ringside shenanigans

    # Ring stats (secondary — low defaults, can grow if they wrestle)
    can_wrestle = Column(Boolean, default=False)
    power = Column(Integer, default=20)          # 0-100
    speed = Column(Integer, default=25)          # 0-100
    toughness = Column(Integer, default=20)      # 0-100

    # Popularity & standing
    popularity = Column(Integer, default=30)     # 0-100
    heat = Column(Integer, default=30)           # 0-100, crowd reaction intensity

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    clients = relationship("ManagerClientDB", back_populates="manager",
                           foreign_keys="ManagerClientDB.manager_id")


class ManagerClientDB(Base):
    """A persistent bond between a manager/valet and a wrestler client.

    Tracks the ongoing relationship: how effective the pairing is,
    what the manager specializes in, and the bonuses they provide.
    """
    __tablename__ = "manager_clients"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    manager_id = Column(String, ForeignKey("managers.id"), nullable=False, index=True)
    client_wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)

    role = Column(String(20), default="manager")  # ManagerRole values
    effectiveness = Column(Integer, default=50)    # 0-100, how well the pairing works
    specialization = Column(String(20), default="all_around")  # ManagerSpecialization values

    # Bonuses the manager provides to the client
    charisma_bonus = Column(Integer, default=5)    # 0-20, added to client's effective charisma
    heat_bonus = Column(Integer, default=5)        # 0-20, added to client's heat generation

    contract_started = Column(String(10), nullable=True)
    contract_ended = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    manager = relationship("ManagerDB", back_populates="clients",
                           foreign_keys=[manager_id])

    __table_args__ = (
        UniqueConstraint("manager_id", "client_wrestler_id",
                         name="uq_manager_client_pair"),
        Index("ix_manager_client_world", "world_id"),
    )


# ---------------------------------------------------------------------------
# Stables / Factions — Multi-member groups with internal politics
# ---------------------------------------------------------------------------

class StableDB(Base):
    """A stable (faction) — a named group of 2+ wrestlers with shared identity.

    Stables are where the richest storylines live: nWo, DX, Evolution,
    The Bloodline. Internal politics drive betrayals, power struggles,
    and career-making moments when a member strikes out on their own.
    """
    __tablename__ = "stables"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    short_name = Column(String(20), nullable=True)  # e.g. "nWo", "DX"

    # Identity
    alignment = Column(String(10), default="heel")  # face, heel, tweener
    catchphrase = Column(String(200), nullable=True)
    group_finisher_name = Column(String(100), nullable=True)
    entrance_music = Column(String(100), nullable=True)

    # Status & metrics
    heat = Column(Integer, default=30)          # 0-100, crowd reaction intensity
    prestige = Column(Integer, default=20)      # 0-100, how respected/feared the group is
    dominance = Column(Integer, default=0)       # 0-100, how much they control the fed

    # Internal health
    cohesion = Column(Integer, default=80)      # 0-100, how united the group is
    # Below 40 = "fracturing", below 20 = auto-generates POWER_STRUGGLE storyline

    # Manager association (optional — a stable can have a manager)
    manager_id = Column(String, ForeignKey("managers.id"), nullable=True)

    # Lifecycle
    formed_date = Column(String(10), nullable=True)
    dissolved_date = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    members = relationship("StableMemberDB", back_populates="stable",
                           foreign_keys="StableMemberDB.stable_id")

    __table_args__ = (
        Index("ix_stable_world_fed", "world_id", "federation_id"),
    )


class StableMemberDB(Base):
    """Tracks a wrestler's membership in a stable, including their role
    and internal political standing.

    Roles define the faction's power structure:
    - leader: The face of the faction, makes decisions
    - enforcer: The muscle, protects the leader
    - mouthpiece: The talker, cuts promos for the group
    - lieutenant: Second-in-command, potential successor/usurper
    - member: Rank and file
    - recruit: New addition, low loyalty, proving themselves
    """
    __tablename__ = "stable_members"

    id = Column(String, primary_key=True, default=_uuid)
    stable_id = Column(String, ForeignKey("stables.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)

    role = Column(String(20), default="member")  # StableRole values
    loyalty = Column(Integer, default=70)         # 0-100, how committed to the group
    influence = Column(Integer, default=30)       # 0-100, power within the group

    joined_date = Column(String(10), nullable=True)
    left_date = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)

    stable = relationship("StableDB", back_populates="members",
                          foreign_keys=[stable_id])

    __table_args__ = (
        UniqueConstraint("stable_id", "wrestler_id",
                         name="uq_stable_member_pair"),
    )
