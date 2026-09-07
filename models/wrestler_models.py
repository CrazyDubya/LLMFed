"""
Wrestler models: wrestlers, stats, contracts, goals, backstory, gimmick history,
life events, social media, mentorship, career highlights, and hall of fame.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    Text,
    Boolean,
    UniqueConstraint,
    Index,
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
    draw_rating = Column(
        Float, default=50.0
    )  # 0-100, computed from popularity + titles + streaks + rivalries
    condition = Column(Integer, default=100)  # Health/stamina 0-100
    morale = Column(Integer, default=75)  # 0-100
    win_streak = Column(
        Integer, default=0
    )  # Current consecutive wins (neg = loss streak)
    last_booked_date = Column(
        String(10), nullable=True
    )  # Last date wrestler was on a show
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
    birth_date = Column(
        String(10), nullable=True
    )  # YYYY-MM-DD, age derived from game_date
    peak_age = Column(Integer, default=28)  # Randomized 26-32 at creation
    career_phase = Column(
        String(20), default="prime"
    )  # rookie/rising/prime/veteran/declining
    ring_rust_days = Column(Integer, default=0)  # Days since last match
    # --- Group 2: Career Goals ---
    satisfaction = Column(Integer, default=50)  # 0-100, aggregate of goal fulfillment
    # --- Group 3: Backstage Politics ---
    locker_room_standing = Column(
        String(20), default="neutral"
    )  # leader/respected/neutral/disliked/toxic
    creative_influence = Column(Integer, default=0)  # 0-100
    # --- Group 5: Legacy ---
    legacy_score = Column(
        Integer, default=0
    )  # Computed: titles + highlights + years + match_avg
    is_hall_of_famer = Column(Boolean, default=False)
    # --- Group 6: Physical Identity ---
    height_cm = Column(Integer, nullable=True)  # 160-210
    weight_kg = Column(Integer, nullable=True)  # 70-160
    body_type = Column(
        String(20), nullable=True
    )  # cruiserweight/average/big_man/super_heavyweight
    is_active = Column(Boolean, default=True)
    is_injured = Column(Boolean, default=False)
    injury_return_date = Column(String(10), nullable=True)
    debut_date = Column(String(10), nullable=True)
    retirement_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # --- Persona & Gimmick ---
    kayfabe_commitment = Column(
        Integer, default=50
    )  # 0-100, how seriously they protect kayfabe
    social_media_following = Column(Integer, default=1000)  # Fan base size
    public_perception = Column(
        String(30), default="neutral"
    )  # beloved, respected, controversial, forgotten, neutral
    character_depth = Column(
        Integer, default=40
    )  # 0-100, how developed their character work is
    gimmick_changes = Column(Integer, default=0)  # How many times repackaged
    kayfabe_break_count = Column(
        Integer, default=0
    )  # Times the person broke character publicly

    world = relationship("WorldDB", back_populates="wrestlers")
    player = relationship(
        "PlayerDB",
        back_populates="wrestler",
        foreign_keys="PlayerDB.wrestler_id",
        uselist=False,
    )
    stats = relationship(
        "WrestlerStatsDB",
        back_populates="wrestler",
        uselist=False,
        cascade="all, delete-orphan",
    )
    contracts = relationship("ContractDB", back_populates="wrestler")
    match_participations = relationship("MatchParticipantDB", back_populates="wrestler")
    promos = relationship(
        "PromoDB", back_populates="wrestler", foreign_keys="PromoDB.wrestler_id"
    )
    storyline_roles = relationship("StorylineParticipantDB", back_populates="wrestler")
    title_reigns = relationship("ChampionshipHistoryDB", back_populates="wrestler")
    history_entries = relationship("WrestlerHistoryDB", back_populates="wrestler")
    backstory = relationship(
        "WrestlerBackstoryDB",
        back_populates="wrestler",
        uselist=False,
        cascade="all, delete-orphan",
    )
    gimmick_history = relationship(
        "GimmickHistoryDB", back_populates="wrestler", cascade="all, delete-orphan"
    )
    life_events = relationship(
        "LifeEventDB", back_populates="wrestler", cascade="all, delete-orphan"
    )
    social_media_posts = relationship(
        "SocialMediaPostDB",
        back_populates="wrestler",
        foreign_keys="SocialMediaPostDB.wrestler_id",
        cascade="all, delete-orphan",
    )


class WrestlerStatsDB(Base):
    """Detailed wrestler attributes for match simulation."""

    __tablename__ = "wrestler_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, unique=True
    )
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
    selling = Column(Integer, default=50)  # Ability to sell moves
    # Hidden stats
    backstage_politics = Column(Integer, default=50)
    loyalty = Column(Integer, default=50)
    work_ethic = Column(Integer, default=50)
    injury_prone = Column(Integer, default=30)  # Higher = more injury risk
    # --- Group 6: Match Specialization & Conditioning ---
    cage_specialist = Column(Integer, default=0)  # 0-100 bonus in cage/cell matches
    ladder_specialist = Column(Integer, default=0)  # 0-100 bonus in ladder matches
    hardcore_specialist = Column(
        Integer, default=0
    )  # 0-100 bonus in tables/extreme matches
    conditioning_level = Column(
        Integer, default=70
    )  # Current physical conditioning 0-100
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
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    federation_id = Column(
        String, ForeignKey("game_federations.id"), nullable=False, index=True
    )
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
# Career History
# ---------------------------------------------------------------------------


class WrestlerHistoryDB(Base):
    """Career milestones and notable events for a wrestler."""

    __tablename__ = "wrestler_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    game_date = Column(String(10), nullable=False)
    event_type = Column(
        String(30), nullable=False
    )  # debut, title_win, injury, retirement, etc.
    description = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="history_entries")


# ---------------------------------------------------------------------------
# Group 2: Career Goals
# ---------------------------------------------------------------------------


class WrestlerGoalDB(Base):
    """Tracks a wrestler's active career goals and progress toward them."""

    __tablename__ = "wrestler_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    goal_type = Column(
        String(30), nullable=False
    )  # win_title, main_event_ppv, 5_star_match, etc.
    target_entity_id = Column(
        String, nullable=True
    )  # Optional: specific title/rival ID
    status = Column(
        String(20), default="active"
    )  # active, completed, failed, abandoned
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
    mentor_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    protege_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    federation_id = Column(
        String, ForeignKey("game_federations.id"), nullable=False, index=True
    )
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
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    highlight_type = Column(
        String(30), nullable=False
    )  # 5_star_classic, title_win, ppv_main_event, iron_man_defense
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
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
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
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, unique=True
    )
    origin_story = Column(Text, nullable=True)  # Narrative of where they came from
    family_situation = Column(
        String(50), default="single"
    )  # single, married, divorced, kids, estranged
    pre_wrestling_career = Column(
        String(100), nullable=True
    )  # Bouncer, teacher, athlete, military
    wrestling_motivation = Column(
        String(50), default="passion"
    )  # passion, money, legacy, escape, family_tradition
    real_personality = Column(JSON, default=dict)
    # Structure: {
    #   "temperament": "calm"|"volatile"|"anxious"|"steady",
    #   "introversion": 0-100 (0=extrovert, 100=introvert),
    #   "ambition": 0-100,
    #   "ego": 0-100,
    #   "substance_risk": 0-100,
    #   "media_savvy": 0-100,
    # }
    personal_struggles = Column(
        JSON, default=list
    )  # ["financial_pressure", "family_estrangement"]
    personal_life_stability = Column(
        Integer, default=70
    )  # 0-100 aggregate health of real life
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
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
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
    visual_identity = Column(
        JSON, default=dict
    )  # attire, mask, face_paint, signature_look
    start_date = Column(String(10), nullable=True)  # Game date adopted
    end_date = Column(String(10), nullable=True)  # Game date retired (null = current)
    depth_score = Column(Integer, default=40)  # 0-100, how layered/developed
    effectiveness = Column(
        Integer, default=50
    )  # 0-100, how well it's working with audiences
    staleness = Column(Integer, default=0)  # 0-100, increases over time
    fan_investment = Column(Integer, default=30)  # 0-100, emotional attachment
    is_active = Column(Boolean, default=True)
    reason_for_change = Column(
        Text, nullable=True
    )  # Why they changed (for retired gimmicks)
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship("GameWrestlerDB", back_populates="gimmick_history")


class LifeEventDB(Base):
    """A real-life event affecting the person behind the wrestler.

    These events can affect morale, performance, and potentially become
    storyline material depending on federation kayfabe strictness.
    """

    __tablename__ = "life_events"

    id = Column(String, primary_key=True, default=_uuid)
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
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

    __table_args__ = (Index("ix_life_event_world_date", "world_id", "game_date"),)


class SocialMediaPostDB(Base):
    """A social media post by a wrestler — in-character, shoot, or ambiguous."""

    __tablename__ = "social_media_posts"

    id = Column(String, primary_key=True, default=_uuid)
    wrestler_id = Column(
        String, ForeignKey("game_wrestlers.id"), nullable=False, index=True
    )
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False, index=True)
    game_date = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)  # The post text
    post_type = Column(
        String(20), default="kayfabe"
    )  # kayfabe, shoot, worked_shoot, personal
    platform = Column(
        String(20), default="twitter"
    )  # twitter, instagram, youtube, tiktok, podcast
    engagement_score = Column(Integer, default=10)  # 0-100 virality/interaction
    controversy_level = Column(Integer, default=0)  # 0-100 heat generated
    storyline_id = Column(String, ForeignKey("storylines.id"), nullable=True)
    target_wrestler_id = Column(String, ForeignKey("game_wrestlers.id"), nullable=True)
    is_viral = Column(Boolean, default=False)
    fan_reaction = Column(
        String(20), default="positive"
    )  # positive, negative, mixed, confused
    kayfabe_break_level = Column(
        Integer, default=0
    )  # 0-100, how much fourth wall is broken
    popularity_impact = Column(Integer, default=0)  # Delta to wrestler popularity
    created_at = Column(DateTime, default=_utc_now)

    wrestler = relationship(
        "GameWrestlerDB",
        back_populates="social_media_posts",
        foreign_keys=[wrestler_id],
    )

    __table_args__ = (Index("ix_social_media_world_date", "world_id", "game_date"),)
