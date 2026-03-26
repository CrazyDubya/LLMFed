"""
Pydantic schemas for the game API - request/response models.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    display_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

class WorldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    is_multiplayer: bool = False
    max_players: int = Field(default=1, ge=1, le=100)
    world_config: Dict[str, Any] = Field(default_factory=dict)


class WorldResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_multiplayer: bool
    max_players: int
    current_game_date: str
    current_tick: int
    is_active: bool
    world_config: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class PlayerCreate(BaseModel):
    world_id: str
    player_type: str = Field(pattern=r"^(promoter|wrestler)$")
    # If promoter: create or join a federation
    federation_name: Optional[str] = Field(default=None, max_length=100)
    federation_description: Optional[str] = None
    # If wrestler: create a character
    wrestler_name: Optional[str] = Field(default=None, max_length=100)
    wrestler_gimmick: Optional[str] = None
    wrestler_alignment: Optional[str] = Field(default="face", pattern=r"^(face|heel|tweener)$")
    wrestler_style: Optional[str] = None  # technical, brawler, highflyer, powerhouse, allrounder


class PlayerResponse(BaseModel):
    id: str
    user_id: str
    world_id: str
    player_type: str
    federation_id: Optional[str]
    wrestler_id: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Federation
# ---------------------------------------------------------------------------

class FederationResponse(BaseModel):
    id: str
    world_id: str
    name: str
    short_name: Optional[str]
    description: Optional[str]
    is_npc: bool
    prestige: int
    budget: float
    weekly_revenue: float
    weekly_expenses: float
    tv_deal_value: float
    home_region: str
    style: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FederationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    style: Optional[str] = None
    home_region: Optional[str] = None


# ---------------------------------------------------------------------------
# Wrestler
# ---------------------------------------------------------------------------

class WrestlerResponse(BaseModel):
    id: str
    world_id: str
    name: str
    real_name: Optional[str]
    is_npc: bool
    gimmick: Optional[str]
    alignment: str
    popularity: int
    condition: int
    morale: int
    age: int
    weight_class: str
    finisher_name: Optional[str]
    finisher_type: Optional[str]
    catchphrase: Optional[str]
    is_active: bool
    is_injured: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WrestlerStatsResponse(BaseModel):
    power: int
    speed: int
    technical: int
    aerial: int
    brawling: int
    submission: int
    stamina: int
    toughness: int
    charisma: int
    mic_skill: int
    psychology: int
    selling: int

    model_config = ConfigDict(from_attributes=True)


class WrestlerDetailResponse(BaseModel):
    wrestler: WrestlerResponse
    stats: Optional[WrestlerStatsResponse]
    current_federation: Optional[str] = None
    current_championships: List[str] = []
    active_storylines: List[str] = []
    win_loss: Dict[str, int] = Field(default_factory=lambda: {"wins": 0, "losses": 0, "draws": 0})


# ---------------------------------------------------------------------------
# Shows
# ---------------------------------------------------------------------------

class ShowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    show_type: str = Field(default="weekly", pattern=r"^(weekly|ppv|special|house_show)$")
    venue: Optional[str] = Field(default=None, max_length=100)
    capacity: int = Field(default=5000, ge=100, le=100000)
    game_date: str  # YYYY-MM-DD


class ShowResponse(BaseModel):
    id: str
    world_id: str
    federation_id: str
    name: str
    show_type: str
    venue: Optional[str]
    capacity: int
    attendance: Optional[int]
    game_date: str
    is_completed: bool
    overall_rating: Optional[float]
    tv_rating: Optional[float]
    gate_revenue: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Match Booking
# ---------------------------------------------------------------------------

class MatchBooking(BaseModel):
    match_type: str = Field(default="singles")
    stipulation: Optional[str] = None
    is_title_match: bool = False
    championship_id: Optional[str] = None
    participant_ids: List[str] = Field(min_length=2)
    planned_winner_id: Optional[str] = None  # Promoter's planned finish
    planned_finish: Optional[str] = None
    planned_duration_minutes: int = Field(default=15, ge=5, le=60)
    segment_position: Optional[int] = None


class SegmentBooking(BaseModel):
    segment_type: str = Field(pattern=r"^(match|promo|backstage|interview|entrance|angle)$")
    match_booking: Optional[MatchBooking] = None
    wrestler_id: Optional[str] = None  # For promos
    description: Optional[str] = None
    planned_duration_minutes: int = Field(default=10, ge=1, le=60)


# ---------------------------------------------------------------------------
# Player Actions
# ---------------------------------------------------------------------------

class PlayerActionSubmit(BaseModel):
    action_type: str
    action_data: Dict[str, Any]


class PlayerActionResponse(BaseModel):
    id: str
    action_type: str
    action_data: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]]
    submitted_at: datetime
    processed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------

class StorylineResponse(BaseModel):
    id: str
    world_id: str
    federation_id: Optional[str]
    name: str
    storyline_type: str
    status: str
    description: Optional[str]
    heat: int
    start_date: Optional[str]
    participants: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Championships
# ---------------------------------------------------------------------------

class ChampionshipCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    weight_class: Optional[str] = None
    is_tag_team: bool = False


class ChampionshipResponse(BaseModel):
    id: str
    world_id: str
    federation_id: str
    name: str
    prestige: int
    weight_class: Optional[str]
    is_tag_team: bool
    current_holder_id: Optional[str]
    defenses: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Narrative / News
# ---------------------------------------------------------------------------

class NarrativeLogResponse(BaseModel):
    id: int
    game_date: str
    event_type: str
    description: str
    importance: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorldNewsResponse(BaseModel):
    id: str
    headline: str
    body: str
    category: str
    game_date: str
    is_kayfabe: bool
    source: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# World Tick Status
# ---------------------------------------------------------------------------

class WorldTickStatus(BaseModel):
    world_id: str
    current_game_date: str
    current_tick: int
    events_today: List[str] = []
    pending_actions: int = 0


# ---------------------------------------------------------------------------
# Show Card / Match Results
# ---------------------------------------------------------------------------

class ShowSegmentResponse(BaseModel):
    id: str
    show_id: str
    position: int
    segment_type: str
    match_id: Optional[str]
    description: Optional[str]
    planned_duration_minutes: int
    actual_duration_minutes: Optional[int]
    rating: Optional[float]
    crowd_reaction: Optional[str]
    is_completed: bool

    model_config = ConfigDict(from_attributes=True)


class MatchResultResponse(BaseModel):
    id: str
    match_type: str
    stipulation: Optional[str]
    is_title_match: bool
    winner_id: Optional[str]
    finish_type: Optional[str]
    finish_description: Optional[str]
    match_rating: Optional[float]
    crowd_heat: int
    duration_minutes: Optional[int]
    is_completed: bool

    model_config = ConfigDict(from_attributes=True)


class ShowCardResponse(BaseModel):
    show: ShowResponse
    segments: List[ShowSegmentResponse] = []


# ---------------------------------------------------------------------------
# Promo
# ---------------------------------------------------------------------------

class PromoRequest(BaseModel):
    wrestler_id: str
    target_wrestler_id: Optional[str] = None
    promo_type: str = Field(default="in_ring", pattern=r"^(in_ring|backstage|interview)$")
    player_direction: Optional[str] = None  # What vibe/angle to go for
    player_content: Optional[str] = None   # Full player-written promo


class PromoResponse(BaseModel):
    id: str
    wrestler_id: str
    target_wrestler_id: Optional[str]
    content: str
    promo_type: str
    crowd_reaction: Optional[str]
    heat_generated: int
    quality_rating: Optional[float]
    game_date: Optional[str]
    is_player_written: bool

    model_config = ConfigDict(from_attributes=True)
