from typing import Any, Dict

from models.entities import (
    EventContext, 
    AgentActionResponse,
    RefereeCallResponse,
    CrowdReactionResponse,
    AnnouncerCommentaryResponse,
    PromoterHintResponse,
    BackstageActionResponse,
)

from typing import Dict, Any

class PromptBuilder:
    """Builds prompts for LLM interactions based on event context and promoter hints."""

    @staticmethod
    def build_prompt(context: EventContext, hints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constructs a combined prompt payload containing event context and promoter-provided hints.
        """
        # Select response schema by role
        schema_map = {
            "participant": AgentActionResponse,
            "referee": RefereeCallResponse,
            "crowd": CrowdReactionResponse,
            "announcer": AnnouncerCommentaryResponse,
            "promoter": PromoterHintResponse,
            "backstage": BackstageActionResponse,
        }
        ResponseModel = schema_map.get(context.role, AgentActionResponse)
        schema = ResponseModel.model_json_schema()
        # Optional role-specific instruction
        preamble = f"You are acting as the {context.role}. Respond accordingly."
        return {
            "preamble": preamble,
            "event_id": context.event_id,
            "event_type": context.event_type,
            "role": context.role,
            "description": context.description,
            "requesting_agent_id": context.requesting_agent_id,
            # Include full state (e.g., gimmick, heat, momentum, match context)
            "state": context.state,
            # List available actions for agent
            "available_actions": [action.model_dump() for action in context.available_actions],
            "hints": hints,
            # JSON schema reminder for agent to follow when responding
            "response_schema": schema,
        }
