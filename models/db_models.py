"""
SQLAlchemy database models for LLMFed.

These models define the database schema and relationships for the wrestling
federation simulator.
"""

from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text, Boolean
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
    alignment = Column(String, nullable=True, default="babyface")  # babyface, heel, tweener
    win_streak = Column(Integer, default=0)
    loss_streak = Column(Integer, default=0)
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
    agent_id = Column(String, nullable=False)
    due_tick = Column(Integer, nullable=False)
    context_json = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class NarrativeLogDB(Base):
    """SQLAlchemy model for narrative logs."""
    __tablename__ = "narrative_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick_id = Column(String, nullable=False)
    time_index = Column(Integer, nullable=False)
    agent_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# Wrestling domain
# ---------------------------------------------------------------------------
class TitleDB(Base):
    """SQLAlchemy model for championships."""
    __tablename__ = "titles"

    title_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    tier = Column(String, nullable=False, default="mid_card")
    prestige = Column(Integer, default=50)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class ReignDB(Base):
    """SQLAlchemy model for championship reigns."""
    __tablename__ = "reigns"

    reign_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title_id = Column(String, ForeignKey("titles.title_id"), nullable=False)
    champion_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    end_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utc_now)


class TeamDB(Base):
    """SQLAlchemy model for tag teams."""
    __tablename__ = "teams"

    team_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    member_ids = Column(JSON, nullable=False, default=list)  # ["agent_id1", "agent_id2"]
    formed_date = Column(DateTime, nullable=False)
    disbanded_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class StableDB(Base):
    """SQLAlchemy model for stables."""
    __tablename__ = "stables"

    stable_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    leader_id = Column(String, ForeignKey("agents.agent_id"), nullable=True)
    member_ids = Column(JSON, nullable=False, default=list)
    formed_date = Column(DateTime, nullable=False)
    disbanded_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class StorylineDB(Base):
    """SQLAlchemy model for storylines."""
    __tablename__ = "storylines"

    storyline_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    title = Column(String, nullable=False)
    storyline_type = Column(String, nullable=False, default="feud")
    participant_ids = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="active")
    heat = Column(Integer, default=50)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    payoff_phase = Column(String, nullable=True)  # build_up, anchor, aftermath
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class MatchResultDB(Base):
    """SQLAlchemy model for match results (history/records)."""
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, nullable=False, index=True)
    card_id = Column(String, nullable=False, index=True)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    participant_ids = Column(JSON, nullable=False, default=list)
    winner_id = Column(String, ForeignKey("agents.agent_id"), nullable=True)
    title_id = Column(String, ForeignKey("titles.title_id"), nullable=True)
    title_changed = Column(Boolean, default=False)
    storyline_id = Column(String, ForeignKey("storylines.storyline_id"), nullable=True)
    completed_at = Column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# Roster, contracts, staff, audience
# ---------------------------------------------------------------------------
class ContractDB(Base):
    """SQLAlchemy model for agent-federation contracts."""
    __tablename__ = "contracts"

    contract_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    contract_type = Column(String, nullable=False, default="full_time")
    status = Column(String, nullable=False, default="active")
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    salary_terms = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class WrestlerStatsDB(Base):
    """SQLAlchemy model for wrestler stats (per agent per federation)."""
    __tablename__ = "wrestler_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    no_contests = Column(Integer, default=0)
    title_reigns = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    main_events = Column(Integer, default=0)
    ppv_matches = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class WrestlerPersonalityDB(Base):
    """SQLAlchemy model for wrestler personality (gimmick vs personal)."""
    __tablename__ = "wrestler_personalities"

    agent_id = Column(String, ForeignKey("agents.agent_id"), primary_key=True)
    gimmick_traits = Column(JSON, nullable=False, default=dict)
    personal_traits = Column(JSON, nullable=False, default=dict)
    backstage_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class StaffProfileDB(Base):
    """SQLAlchemy model for staff profiles (announcer, referee, manager, valet)."""
    __tablename__ = "staff_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    staff_type = Column(String, nullable=False)  # announcer, referee, manager, valet
    profile_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class AudienceDemographicsDB(Base):
    """SQLAlchemy model for federation audience demographics."""
    __tablename__ = "audience_demographics"

    federation_id = Column(String, ForeignKey("federations.federation_id"), primary_key=True)
    age_distribution = Column(JSON, nullable=False, default=dict)
    region_distribution = Column(JSON, nullable=False, default=dict)
    fan_type_distribution = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class AudienceSegmentDB(Base):
    """SQLAlchemy model for per-card audience mix (superfan %, favorites/hated)."""
    __tablename__ = "audience_segments"

    segment_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    card_id = Column(String, nullable=True, index=True)
    venue_type = Column(String, default="arena")
    superfan_pct = Column(Integer, default=10)
    super_viewer_pct = Column(Integer, default=20)
    common_viewer_pct = Column(Integer, default=40)
    common_fan_pct = Column(Integer, default=30)
    favorite_agent_ids = Column(JSON, nullable=True, default=list)
    hated_agent_ids = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# Venue (place where card happens; concessions, PPV, gate)
# ---------------------------------------------------------------------------
class VenueDB(Base):
    """SQLAlchemy model for venues (arena, stadium, tv_only, special)."""
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


# ---------------------------------------------------------------------------
# Week template (show type per day; roster split, travel squad)
# ---------------------------------------------------------------------------
class WeekTemplateDB(Base):
    """Week template: which days have house/tv/ppv/dark/off."""
    __tablename__ = "week_templates"

    week_template_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    slots_json = Column(JSON, nullable=False, default=list)  # List of {day_of_week, show_type, loop}
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


# ---------------------------------------------------------------------------
# Fatigue (off-camera: worked last night -> rest; travel squad excludes high fatigue)
# ---------------------------------------------------------------------------
class AgentFatigueDB(Base):
    """Per-agent fatigue: incremented when working a card, decay on rest days."""
    __tablename__ = "agent_fatigue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    fatigue_level = Column(Integer, default=0)  # 0-100; high = needs rest
    last_work_date = Column(DateTime, nullable=True)  # Last date they worked a card
    as_of_date = Column(DateTime, nullable=False)  # Date this row is valid for
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


# ---------------------------------------------------------------------------
# Injury (depth: who's out when, comebacks, surprise returns)
# ---------------------------------------------------------------------------
class InjuryDB(Base):
    """Wrestler injury: out_from, out_until, optional surprise return."""
    __tablename__ = "injuries"

    injury_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    injury_type = Column(String, default="unknown")
    out_from = Column(DateTime, nullable=False)
    out_until = Column(DateTime, nullable=True)
    return_surprise = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


# ---------------------------------------------------------------------------
# World anchor (4-year spine, marquee show)
# ---------------------------------------------------------------------------
class WorldAnchorDB(Base):
    """Federation's 4-year world spine: marquee annual show at world_start + 2 years."""
    __tablename__ = "world_anchors"

    federation_id = Column(String, ForeignKey("federations.federation_id"), primary_key=True)
    world_start_date = Column(DateTime, nullable=False)
    anchor_event_name = Column(String, nullable=False, default="Grandstand")
    anchor_date = Column(DateTime, nullable=True)
    world_end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


# ---------------------------------------------------------------------------
# Media / coverage (next-day recaps)
# ---------------------------------------------------------------------------
class MediaOutletDB(Base):
    """Media outlet: blog, newspaper, TV. Default 'Recap Wire' per federation."""
    __tablename__ = "media_outlets"

    outlet_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    name = Column(String, nullable=False)
    outlet_type = Column(String, default="blog")
    reach = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class RippleDB(Base):
    """Ripple: effect that propagates (injury, cold start, luck, trapdoor)."""
    __tablename__ = "ripples"

    ripple_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    cause = Column(String, nullable=False)  # injury, cold_start, luck_good, luck_ill, trapdoor, etc.
    at_date = Column(DateTime, nullable=True)
    agent_ids = Column(JSON, nullable=False, default=list)
    storyline_ids = Column(JSON, nullable=False, default=list)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=_utc_now)


class TrapdoorDB(Base):
    """Trapdoor: change of direction (swerve, dropped branch, new focus)."""
    __tablename__ = "trapdoors"

    trapdoor_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    at_date = Column(DateTime, nullable=True)
    from_branch = Column(String, nullable=True)
    to_branch = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    ripple_ids = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=_utc_now)


class Tier9ImmutableDB(Base):
    """Tier 9: absolute immutables. Append-only. Card dates, attendance, match card/results, title changes."""
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
    """Revenue per card: gate, PPV, concessions."""
    __tablename__ = "card_revenue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String, nullable=False, index=True)
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    gate_revenue = Column(Integer, default=0)  # cents or whole units
    ppv_revenue = Column(Integer, default=0)
    concession_revenue = Column(Integer, default=0)
    attendance = Column(Integer, default=0)
    total_revenue = Column(Integer, default=0)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=_utc_now)


class CoverageDB(Base):
    """Coverage: scope=next_day for morning-after recaps."""
    __tablename__ = "coverage"

    coverage_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    federation_id = Column(String, ForeignKey("federations.federation_id"), nullable=False)
    outlet_id = Column(String, ForeignKey("media_outlets.outlet_id"), nullable=False)
    critic_id = Column(String, nullable=True)
    scope = Column(String, nullable=False, default="next_day")
    target_card_id = Column(String, nullable=True, index=True)
    target_match_id = Column(String, nullable=True)
    headline = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class ConceptualCardDB(Base):
    """Conceptual/target card for the marquee show (plan, not run state)."""
    __tablename__ = "conceptual_cards"

    federation_id = Column(String, ForeignKey("federations.federation_id"), primary_key=True)
    main_event_target = Column(JSON, nullable=True)
    title_matches_target = Column(JSON, nullable=True, default=list)
    planned_storyline_payoffs = Column(JSON, nullable=True, default=list)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
