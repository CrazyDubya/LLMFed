"""
Pydantic models for LLMFed API data validation and serialization.

These models define the structure of API request/response payloads and provide
data validation for the wrestling federation simulator.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class AgentConfig(BaseModel):
    """Configuration for LLM agent behavior."""
    model_name: str = Field(description="LLM model to use for this agent")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature setting")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens for LLM response")
    personality_prompt: Optional[str] = Field(default=None, description="Base personality prompt for agent")


class PossibleAction(BaseModel):
    """Represents an action that an agent can take in response to an event."""
    action_id: str = Field(description="Unique identifier for the action")
    name: str = Field(description="Human-readable name of the action")
    description: str = Field(description="Description of what this action does")
    requires_target: bool = Field(default=False, description="Whether this action requires a target agent")


class EventContext(BaseModel):
    """Context information provided to an agent for decision making."""
    event_id: str = Field(description="Unique identifier for this event")
    event_type: str = Field(description="Type of event (e.g., 'MatchEvent', 'PromoEvent')")
    role: str = Field(description="Agent's role in this context")
    description: str = Field(description="Human-readable description of the event")
    requesting_agent_id: str = Field(description="ID of the agent that should respond")
    available_actions: List[PossibleAction] = Field(description="Actions the agent can choose from")
    state: Dict[str, Any] = Field(description="Current game/match state information")


# Agent Response Models
class AgentActionResponse(BaseModel):
    """Response from an agent when choosing an action."""
    event_id: str = Field(description="ID of the event being responded to")
    chosen_action_id: str = Field(description="ID of the chosen action")
    target_agent_id: Optional[str] = Field(default=None, description="Target agent ID if action requires one")
    commentary: Optional[str] = Field(default=None, description="Agent's commentary on the action")
    intensity: Optional[int] = Field(default=5, ge=1, le=10, description="Intensity level of the action")


class RefereeCallResponse(BaseModel):
    """Response from a referee agent."""
    call: str = Field(description="Referee's call (e.g., 'pinfall', 'submission', 'disqualification')")
    reason: Optional[str] = Field(default=None, description="Reason for the call")


class CrowdReactionResponse(BaseModel):
    """Response from crowd agent."""
    reaction: str = Field(description="Type of crowd reaction")
    heat_adjustment: int = Field(default=0, description="How much this reaction affects crowd heat")


class AnnouncerCommentaryResponse(BaseModel):
    """Response from announcer agent."""
    commentary: str = Field(description="Announcer's commentary on the action")


class PromoterHintResponse(BaseModel):
    """Response from promoter with guidance hints."""
    new_hints: Dict[str, Any] = Field(description="New hints to guide the match")


class BackstageActionResponse(BaseModel):
    """Response from backstage agent."""
    action: str = Field(description="Backstage action taken")
    description: Optional[str] = Field(default=None, description="Description of the action")


# Agent CRUD Models
class AgentCreateData(BaseModel):
    """Data required to create a new agent."""
    user_id: str = Field(description="ID of the user creating this agent")
    name: str = Field(description="Agent's wrestling name")
    role: str = Field(default="participant", description="Agent's role in matches")
    gimmick_description: str = Field(description="Description of the agent's wrestling character")
    llm_config: Dict[str, Any] = Field(description="LLM configuration for this agent")
    federation_id: Optional[str] = Field(default=None, description="Federation this agent belongs to")


class AgentUpdateData(BaseModel):
    """Data for updating an existing agent."""
    name: Optional[str] = Field(default=None, description="Updated agent name")
    role: Optional[str] = Field(default=None, description="Updated agent role")
    gimmick_description: Optional[str] = Field(default=None, description="Updated gimmick description")
    llm_config: Optional[Dict[str, Any]] = Field(default=None, description="Updated LLM configuration")
    federation_id: Optional[str] = Field(default=None, description="Updated federation assignment")


class Agent(BaseModel):
    """Full agent model for API responses."""
    agent_id: str = Field(description="Unique agent identifier")
    user_id: str = Field(description="ID of the owning user")
    name: str = Field(description="Agent's wrestling name")
    role: str = Field(description="Agent's role in matches")
    gimmick_description: str = Field(description="Description of the agent's wrestling character")
    llm_config: Dict[str, Any] = Field(description="LLM configuration for this agent")
    federation_id: Optional[str] = Field(description="Federation this agent belongs to")
    current_heat: int = Field(default=0, description="Current crowd heat level")
    momentum: int = Field(default=0, description="Current momentum in match")
    created_at: datetime = Field(description="When the agent was created")
    updated_at: datetime = Field(description="When the agent was last updated")

    model_config = ConfigDict(from_attributes=True)


# Federation CRUD Models
class FederationCreateData(BaseModel):
    """Data required to create a new federation."""
    name: str = Field(description="Federation name")
    description: str = Field(description="Federation description")
    tier: str = Field(default="independent", description="Federation tier level")
    owner_user_id: str = Field(description="ID of the user who owns this federation")


class FederationUpdateData(BaseModel):
    """Data for updating an existing federation."""
    name: Optional[str] = Field(default=None, description="Updated federation name")
    description: Optional[str] = Field(default=None, description="Updated description")
    tier: Optional[str] = Field(default=None, description="Updated tier level")


class Federation(BaseModel):
    """Full federation model for API responses."""
    federation_id: str = Field(description="Unique federation identifier")
    name: str = Field(description="Federation name")
    description: str = Field(description="Federation description")
    tier: str = Field(description="Federation tier level")
    owner_user_id: str = Field(description="ID of the owning user")
    created_at: datetime = Field(description="When the federation was created")
    updated_at: datetime = Field(description="When the federation was last updated")

    model_config = ConfigDict(from_attributes=True)


# Promoter Hint Request
class PrompterHintRequest(BaseModel):
    """Request to provide promoter hints for match guidance."""
    context: EventContext = Field(description="Current event context")
    hints: Dict[str, Any] = Field(description="Hints to guide the match")