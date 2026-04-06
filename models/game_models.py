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
    FACTION_WAR = "faction_war"
    POWER_STRUGGLE = "power_struggle"
    MANAGER_BETRAYAL = "manager_betrayal"


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
    # Faction/manager actions
    FORM_STABLE = "form_stable"
    JOIN_STABLE = "join_stable"
    LEAVE_STABLE = "leave_stable"
    ASSIGN_MANAGER = "assign_manager"


class StableRole(str, enum.Enum):
    LEADER = "leader"
    ENFORCER = "enforcer"
    MOUTHPIECE = "mouthpiece"
    LIEUTENANT = "lieutenant"
    MEMBER = "member"
    RECRUIT = "recruit"


class ManagerArchetype(str, enum.Enum):
    SCHEMING_MANAGER = "scheming_manager"
    CORPORATE_SUIT = "corporate_suit"
    FLAMBOYANT_MOUTHPIECE = "flamboyant_mouthpiece"
    ENFORCER_TYPE = "enforcer_type"
    OLD_SCHOOL = "old_school"


class ManagerRole(str, enum.Enum):
    MANAGER = "manager"
    VALET = "valet"
    ADVOCATE = "advocate"
    HANDLER = "handler"


class ManagerSpecialization(str, enum.Enum):
    PROMO_BOOST = "promo_boost"
    INTERFERENCE = "interference"
    NEGOTIATION = "negotiation"
    DISTRACTION = "distraction"
    ALL_AROUND = "all_around"


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
    draw_rating = Column(Float, default=50.0)  # 0-100, computed from popularity + titles + streaks + rivalries
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
    # --- Group 1: Aging & Decline ---
    birth_date = Column(String(10), nullable=True)  # YYYY-MM-DD, age derived from game_date
    peak_age = Column(Integer, default=28)  # Randomized 26-32 at creation
    career_phase = Column(String(20), default="prime")  # rookie/rising/prime/veteran/declining
    ring_rust_days = Column(Integer, default=0)  # Days since last match
    # --- Group 2: Career Goals ---
    satisfaction = Column(Integer, default=50)  # 0-100, aggregate of goal fulfillment
    # --- Group 3: Backstage Politics ---
    locker_room_standing = Column(String(20), default="neutral")  # leader/respected/neutral/disliked/toxic
    creative_influence = Column(Integer, default=0)  # 0-100
    # --- Group 5: Legacy ---
    legacy_score = Column(Integer, default=0)  # Computed: titles + highlights + years + match_avg
    is_hall_of_famer = Column(Boolean, default=False)
    # --- Group 6: Physical Identity ---
    height_cm = Column(Integer, nullable=True)  # 160-210
    weight_kg = Column(Integer, nullable=True)  # 70-160
    body_type = Column(String(20), nullable=True)  # cruiserweight/average/big_man/super_heavyweight
    is_active = Column(Boolean, default=True)
    is_injured = Column(Boolean, default=False)
    injury_return_date = Column(String(10), nullable=True)
    debut_date = Column(String(10), nullable=True)
    retirement_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # --- Persona & Gimmick ---
    kayfabe_commitment = Column(Integer, default=50)  # 0-100, how seriously they protect kayfabe
    social_media_following = Column(Integer, default=1000)  # Fan base size
    public_perception = Column(String(30), default="neutral")  # beloved, respected, controversial, forgotten, neutral
    character_depth = Column(Integer, default=40)  # 0-100, how developed their character work is
    gimmick_changes = Column(Integer, default=0)  # How many times repackaged
    kayfabe_break_count = Column(Integer, default=0)  # Times the person broke character publicly

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
    backstory = relationship("WrestlerBackstoryDB", back_populates="wrestler",
                             uselist=False, cascade="all, delete-orphan")
    gimmick_history = relationship("GimmickHistoryDB", back_populates="wrestler",
                                   cascade="all, delete-orphan")
    life_events = relationship("LifeEventDB", back_populates="wrestler",
                               cascade="all, delete-orphan")
    social_media_posts = relationship("SocialMediaPostDB", back_populates="wrestler",
                                      foreign_keys="SocialMediaPostDB.wrestler_id",
                                      cascade="all, delete-orphan")


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
    # --- Group 6: Match Specialization & Conditioning ---
    cage_specialist = Column(Integer, default=0)  # 0-100 bonus in cage/cell matches
    ladder_specialist = Column(Integer, default=0)  # 0-100 bonus in ladder matches
    hardcore_specialist = Column(Integer, default=0)  # 0-100 bonus in tables/extreme matches
    conditioning_level = Column(Integer, default=70)  # Current physical conditioning 0-100
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


# ---------------------------------------------------------------------------
# Promoter Vision & Booking Plans
# ---------------------------------------------------------------------------

class PPVEventDB(Base):
    """A planned or completed PPV event on a federation's annual calendar.

    PPVs are the destination — weekly TV exists to build toward them.
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
    """A federation's strategic booking vision — the promoter's master plan.

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

    # Push tiers — who the promoter sees at each level
    push_tiers = Column(JSON, default=dict)
    # Structure: {
    #   "main_event": [wrestler_id, ...],
    #   "upper_midcard": [wrestler_id, ...],
    #   "midcard": [wrestler_id, ...],
    #   "lower_card": [wrestler_id, ...],
    #   "jobber": [wrestler_id, ...],
    #   "developmental": [wrestler_id, ...],
    # }

    # Wrestler trajectories — planned direction for specific wrestlers
    trajectories = Column(JSON, default=dict)
    # Structure: {wrestler_id: {
    #   "direction": "rising"|"established"|"transitional"|"cooling_off",
    #   "target_tier": "main_event",
    #   "target_date": "2026-06-01",  # When they should arrive
    #   "notes": "Next big babyface",
    #   "status": "penciled"|"ink",
    # }}

    # Title pipelines — who's next for each belt
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

    # Adaptation log — what changed and why
    adaptation_log = Column(JSON, default=list)
    # [{date: str, change: str, reason: str}]

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class WrestlerPushDB(Base):
    """Tracks a wrestler's current push status and trajectory within a federation.

    Separate from BookingVisionDB for efficient querying — 'who are my main eventers?'
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


# ---------------------------------------------------------------------------
# Group 2: Career Goals
# ---------------------------------------------------------------------------

class WrestlerGoalDB(Base):
    """Tracks a wrestler's active career goals and progress toward them."""
    __tablename__ = "wrestler_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    goal_type = Column(String(30), nullable=False)  # win_title, main_event_ppv, 5_star_match, etc.
    target_entity_id = Column(String, nullable=True)  # Optional: specific title/rival ID
    status = Column(String(20), default="active")  # active, completed, failed, abandoned
    progress = Column(Integer, default=0)  # 0-100 percentage
    frustration = Column(Integer, default=0)  # 0-100, grows when blocked
    set_date = Column(String(10), nullable=True)
    completed_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# Group 4: Developmental Pipeline — Mentorship
# ---------------------------------------------------------------------------

class MentorshipDB(Base):
    """A mentor/protege relationship between two wrestlers in a federation."""
    __tablename__ = "mentorships"

    id = Column(String, primary_key=True, default=_uuid)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    mentor_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    protege_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    federation_id = Column(String, ForeignKey("game_federations.id"), nullable=False, index=True)
    started_date = Column(String(10), nullable=True)
    ended_date = Column(String(10), nullable=True)
    skill_focus = Column(String(30), nullable=True)  # power, technical, aerial, etc.
    mentor_bonus = Column(Float, default=0.5)  # Effectiveness multiplier
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# Group 5: Legacy & Hall of Fame
# ---------------------------------------------------------------------------

class CareerHighlightDB(Base):
    """A notable career moment for a wrestler."""
    __tablename__ = "career_highlights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    highlight_type = Column(String(30), nullable=False)  # 5_star_classic, title_win, ppv_main_event, iron_man_defense
    description = Column(Text, nullable=False)
    game_date = Column(String(10), nullable=False)
    significance = Column(Integer, default=5)  # 1-10
    match_id = Column(String, ForeignKey("matches.id"), nullable=True)
    created_at = Column(DateTime, default=_utc_now)


class HallOfFameDB(Base):
    """Hall of Fame induction record."""
    __tablename__ = "hall_of_fame"

    id = Column(Integer, primary_key=True, autoincrement=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    inducted_date = Column(String(10), nullable=False)
    legacy_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utc_now)

    __table_args__ = (
        UniqueConstraint("world_id", "wrestler_id", name="uq_hof_wrestler"),
    )


# ---------------------------------------------------------------------------
# Persona Duality: The Human Behind the Character
# ---------------------------------------------------------------------------

class WrestlerBackstoryDB(Base):
    """The real person behind the wrestling character."""
    __tablename__ = "wrestler_backstories"

    id = Column(String, primary_key=True, default=_uuid)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, unique=True)
    origin_story = Column(Text, nullable=True)  # Narrative of where they came from
    family_situation = Column(String(50), default="single")  # single, married, divorced, kids, estranged
    pre_wrestling_career = Column(String(100), nullable=True)  # Bouncer, teacher, athlete, military
    wrestling_motivation = Column(String(50), default="passion")  # passion, money, legacy, escape, family_tradition
    real_personality = Column(JSON, default=dict)
    # Structure: {
    #   "temperament": "calm"|"volatile"|"anxious"|"steady",
    #   "introversion": 0-100 (0=extrovert, 100=introvert),
    #   "ambition": 0-100,
    #   "ego": 0-100,
    #   "substance_risk": 0-100,
    #   "media_savvy": 0-100,
    # }
    personal_struggles = Column(JSON, default=list)  # ["financial_pressure", "family_estrangement"]
    personal_life_stability = Column(Integer, default=70)  # 0-100 aggregate health of real life
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="backstory")


class GimmickHistoryDB(Base):
    """A wrestling gimmick/character that a wrestler has adopted.

    Wrestlers can have multiple gimmicks over their career (1-to-many).
    Exactly one should have is_active=True at any time.
    """
    __tablename__ = "gimmick_history"

    id = Column(String, primary_key=True, default=_uuid)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    gimmick_name = Column(String(100), nullable=False)  # Ring name / character name
    archetype = Column(String(30), default="anti_hero")
    # Archetypes: monster_heel, underdog_face, cocky_technician, silent_assassin,
    #             cult_leader, comedy_act, anti_hero, legacy, patriot, daredevil
    description = Column(Text, nullable=True)  # Full character description
    origin_narrative = Column(Text, nullable=True)  # Kayfabe origin story
    alignment = Column(String(20), default="face")  # Alignment during this gimmick
    voice_style = Column(JSON, default=dict)
    # Structure: {
    #   "vocabulary": "simple"|"elaborate"|"street"|"academic",
    #   "cadence": "rapid_fire"|"slow_burn"|"staccato"|"conversational",
    #   "catchphrases": ["..."],
    #   "speech_patterns": ["third_person", "yelling", "whispering", "monotone"],
    #   "promo_tempo": "aggressive"|"methodical"|"erratic"|"cool",
    # }
    visual_identity = Column(JSON, default=dict)  # attire, mask, face_paint, signature_look
    start_date = Column(String(10), nullable=True)  # Game date adopted
    end_date = Column(String(10), nullable=True)  # Game date retired (null = current)
    depth_score = Column(Integer, default=40)  # 0-100, how layered/developed
    effectiveness = Column(Integer, default=50)  # 0-100, how well it's working with audiences
    staleness = Column(Integer, default=0)  # 0-100, increases over time
    fan_investment = Column(Integer, default=30)  # 0-100, emotional attachment
    is_active = Column(Boolean, default=True)
    reason_for_change = Column(Text, nullable=True)  # Why they changed (for retired gimmicks)
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="gimmick_history")


class LifeEventDB(Base):
    """A real-life event affecting the person behind the wrestler.

    These events can affect morale, performance, and potentially become
    storyline material depending on federation kayfabe strictness.
    """
    __tablename__ = "life_events"

    id = Column(String, primary_key=True, default=_uuid)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    game_date = Column(String(10), nullable=False)
    event_type = Column(String(30), nullable=False)
    # Types: marriage, divorce, child_born, death_in_family, legal_trouble,
    #        personal_achievement, substance_issue, public_controversy,
    #        charity_work, outside_media, financial_trouble, mental_health,
    #        relationship_start, relationship_end, family_reconciliation
    description = Column(Text, nullable=False)
    severity = Column(Integer, default=5)  # 1-10 impact magnitude
    is_public = Column(Boolean, default=False)  # Known to fans/media?
    morale_impact = Column(Integer, default=0)  # Delta to wrestler morale
    performance_impact = Column(Integer, default=0)  # Delta to in-ring work quality
    storyline_potential = Column(Boolean, default=False)  # Could become a storyline?
    was_used_in_storyline = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)  # Ongoing vs resolved
    resolved_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="life_events")

    __table_args__ = (
        Index("ix_life_event_world_date", "world_id", "game_date"),
    )


class SocialMediaPostDB(Base):
    """A social media post by a wrestler — in-character, shoot, or ambiguous."""
    __tablename__ = "social_media_posts"

    id = Column(String, primary_key=True, default=_uuid)
    wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=False, index=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    game_date = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)  # The post text
    post_type = Column(String(20), default="kayfabe")  # kayfabe, shoot, worked_shoot, personal
    platform = Column(String(20), default="twitter")  # twitter, instagram, youtube, tiktok, podcast
    engagement_score = Column(Integer, default=10)  # 0-100 virality/interaction
    controversy_level = Column(Integer, default=0)  # 0-100 heat generated
    storyline_id = Column(String, ForeignKey("storylines.id"), nullable=True)
    target_wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    is_viral = Column(Boolean, default=False)
    fan_reaction = Column(String(20), default="positive")  # positive, negative, mixed, confused
    kayfabe_break_level = Column(Integer, default=0)  # 0-100, how much fourth wall is broken
    popularity_impact = Column(Integer, default=0)  # Delta to wrestler popularity
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="social_media_posts",
                            foreign_keys=[wrestler_id])

    __table_args__ = (
        Index("ix_social_media_world_date", "world_id", "game_date"),
    )


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
