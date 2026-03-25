"""
SQLAlchemy models for the LLMFed wrestling world game.

These models define the full persistent world schema: users, players, wrestlers,
federations, shows, matches, storylines, championships, contracts, and narrative logs.
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, JSON, ForeignKey, Text, Boolean,
    Enum, UniqueConstraint, Index, Table
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum

from models.db_models import Base


def _utc_now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlayerType(str, enum.Enum):
    PROMOTER = "promoter"
    WRESTLER = "wrestler"


class WrestlerAlignment(str, enum.Enum):
    FACE = "face"          # Good guy
    HEEL = "heel"          # Bad guy
    TWEENER = "tweener"    # In between


class ShowType(str, enum.Enum):
    WEEKLY = "weekly"
    PPV = "ppv"
    SPECIAL = "special"
    HOUSE_SHOW = "house_show"


class SegmentType(str, enum.Enum):
    MATCH = "match"
    PROMO = "promo"
    BACKSTAGE = "backstage"
    INTERVIEW = "interview"
    ENTRANCE = "entrance"
    ANGLE = "angle"         # Storyline progression


class MatchType(str, enum.Enum):
    SINGLES = "singles"
    TAG_TEAM = "tag_team"
    TRIPLE_THREAT = "triple_threat"
    FATAL_FOUR_WAY = "fatal_four_way"
    BATTLE_ROYAL = "battle_royal"
    LADDER = "ladder"
    CAGE = "cage"
    HELL_IN_A_CELL = "hell_in_a_cell"
    ROYAL_RUMBLE = "royal_rumble"
    TABLES = "tables"
    IRON_MAN = "iron_man"


class MatchFinish(str, enum.Enum):
    PINFALL = "pinfall"
    SUBMISSION = "submission"
    COUNT_OUT = "count_out"
    DQ = "disqualification"
    NO_CONTEST = "no_contest"
    STIPULATION = "stipulation"  # Ladder grab, cage escape, etc.


class ContractStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    OFFERED = "offered"


class StorylineStatus(str, enum.Enum):
    BREWING = "brewing"       # Building tension
    ACTIVE = "active"         # In full swing
    CLIMAX = "climax"         # Approaching blowoff
    RESOLVED = "resolved"     # Finished
    ABANDONED = "abandoned"   # Dropped


class StorylineType(str, enum.Enum):
    FEUD = "feud"
    ALLIANCE = "alliance"
    BETRAYAL = "betrayal"
    CHAMPIONSHIP_CHASE = "championship_chase"
    DEBUT = "debut"
    RETURN = "return"
    RETIREMENT = "retirement"
    MYSTERY = "mystery"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionType(str, enum.Enum):
    # Promoter actions
    BOOK_SHOW = "book_show"
    BOOK_MATCH = "book_match"
    SIGN_WRESTLER = "sign_wrestler"
    RELEASE_WRESTLER = "release_wrestler"
    CREATE_CHAMPIONSHIP = "create_championship"
    SET_STORYLINE = "set_storyline"
    SET_TV_DEAL = "set_tv_deal"
    # Wrestler actions
    TRAIN = "train"
    CUT_PROMO = "cut_promo"
    CHALLENGE = "challenge"
    FORM_TAG_TEAM = "form_tag_team"
    ACCEPT_CONTRACT = "accept_contract"
    REJECT_CONTRACT = "reject_contract"
    REQUEST_RELEASE = "request_release"


# ---------------------------------------------------------------------------
# Users & Players
# ---------------------------------------------------------------------------

class UserDB(Base):
    """User account for authentication."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
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
    is_active = Column(Boolean, default=True)
    ai_personality = Column(JSON, default=dict)  # LLM personality traits for NPC booking
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
# Wrestlers
# ---------------------------------------------------------------------------

class GameWrestlerDB(Base):
    """A wrestler character in the game world."""
    __tablename__ = "game_wrestlers"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    real_name = Column(String(100), nullable=True)
    is_npc = Column(Boolean, default=True)  # AI-controlled unless player owns
    gimmick = Column(Text, nullable=True)
    alignment = Column(String(20), default="face")
    alignment_momentum = Column(Integer, default=0)  # -100 (heel) to +100 (face)
    popularity = Column(Integer, default=50)  # 0-100
    condition = Column(Integer, default=100)  # Health/stamina 0-100
    morale = Column(Integer, default=75)  # 0-100
    win_streak = Column(Integer, default=0)  # Current consecutive wins (neg = loss streak)
    last_booked_date = Column(String(10), nullable=True)  # Last date wrestler was on a show
    age = Column(Integer, default=25)
    experience_years = Column(Integer, default=0)
    gender = Column(String(20), default="male")
    weight_class = Column(String(20), default="heavyweight")
    hometown = Column(String(100), nullable=True)
    entrance_music = Column(String(200), nullable=True)
    finisher_name = Column(String(100), nullable=True)
    finisher_type = Column(String(50), nullable=True)  # power, submission, aerial
    signature_moves = Column(JSON, default=list)
    catchphrase = Column(String(200), nullable=True)
    personality_traits = Column(JSON, default=dict)  # For LLM personality
    career_goals = Column(JSON, default=list)  # AI goal system
    is_active = Column(Boolean, default=True)
    is_injured = Column(Boolean, default=False)
    injury_return_date = Column(String(10), nullable=True)
    debut_date = Column(String(10), nullable=True)
    retirement_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    world = relationship("WorldDB", back_populates="wrestlers")
    player = relationship("PlayerDB", back_populates="wrestler",
                          foreign_keys="PlayerDB.wrestler_id", uselist=False)
    stats = relationship("WrestlerStatsDB", back_populates="wrestler", uselist=False,
                         cascade="all, delete-orphan")
    contracts = relationship("ContractDB", back_populates="wrestler")
    match_participations = relationship("MatchParticipantDB", back_populates="wrestler")
    promos = relationship("PromoDB", back_populates="wrestler",
                         foreign_keys="PromoDB.wrestler_id")
    storyline_roles = relationship("StorylineParticipantDB", back_populates="wrestler")
    title_reigns = relationship("ChampionshipHistoryDB", back_populates="wrestler")
    history_entries = relationship("WrestlerHistoryDB", back_populates="wrestler")


class WrestlerStatsDB(Base):
    """Detailed wrestler attributes for match simulation."""
    __tablename__ = "wrestler_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, unique=True)
    # In-ring stats (0-100)
    power = Column(Integer, default=50)
    speed = Column(Integer, default=50)
    technical = Column(Integer, default=50)
    aerial = Column(Integer, default=50)
    brawling = Column(Integer, default=50)
    submission = Column(Integer, default=50)
    stamina = Column(Integer, default=50)
    toughness = Column(Integer, default=50)
    # Out-of-ring stats
    charisma = Column(Integer, default=50)
    mic_skill = Column(Integer, default=50)
    psychology = Column(Integer, default=50)  # Ring psychology / storytelling
    selling = Column(Integer, default=50)     # Ability to sell moves
    # Hidden stats
    backstage_politics = Column(Integer, default=50)
    loyalty = Column(Integer, default=50)
    work_ethic = Column(Integer, default=50)
    injury_prone = Column(Integer, default=30)  # Higher = more injury risk
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="stats")


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

class ContractDB(Base):
    """Employment contract between a wrestler and federation."""
    __tablename__ = "contracts"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    status = Column(String(20), default="active")
    salary_weekly = Column(Float, default=1000.0)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=True)
    is_exclusive = Column(Boolean, default=True)
    merchandise_split = Column(Float, default=0.1)  # Wrestler's cut (10%)
    downside_guarantee = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="contracts")
    federation = relationship("GameFederationDB", back_populates="contracts")


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


class WrestlerHistoryDB(Base):
    """Career milestones and notable events for a wrestler."""
    __tablename__ = "wrestler_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    game_date = Column(String(10), nullable=False)
    event_type = Column(String(30), nullable=False)  # debut, title_win, injury, retirement, etc.
    description = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="history_entries")


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
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    formed_date = Column(String(10), nullable=True)
    dissolved_date = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


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
