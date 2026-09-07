import json
from typing import Any, Dict
from jinja2 import Environment, BaseLoader

from models.entities import (
    VALID_ROLES,
    EventContext,
    AgentActionResponse,
    RefereeCallResponse,
    CrowdReactionResponse,
    AnnouncerCommentaryResponse,
    PromoterHintResponse,
    BackstageActionResponse,
)

# In-memory template strings for Jinja2 (these could be moved to files later)
PROMPT_TEMPLATE = """You are acting as the {{ role }}. Respond accordingly.

Event Details:
Event ID: {{ event_id }}
Event Type: {{ event_type }}
Description: {{ description }}
Requesting Agent ID: {{ requesting_agent_id }}

State:
{{ state | tojson(indent=2) }}

Available Actions:
{% for action in available_actions %}
- {{ action.action_id }}: {{ action.description }}
{% endfor %}

Promoter Hints:
{{ hints | tojson(indent=2) }}

You MUST respond strictly in the following JSON schema:
{{ response_schema | tojson(indent=2) }}
"""


class PromptBuilder:
    """Builds prompts for LLM interactions using Jinja2 templates."""

    _SCHEMA_MAP: Dict[str, type] = {
        "participant": AgentActionResponse,
        "referee": RefereeCallResponse,
        "crowd": CrowdReactionResponse,
        "announcer": AnnouncerCommentaryResponse,
        "promoter": PromoterHintResponse,
        "backstage": BackstageActionResponse,
    }

    _jinja_env = Environment(loader=BaseLoader())
    _jinja_env.filters["tojson"] = lambda obj, indent=None: json.dumps(
        obj, indent=indent
    )

    @classmethod
    def build_prompt(cls, context: EventContext, hints: Dict[str, Any]) -> str:
        """Constructs a rendered string prompt using Jinja2."""
        if context.role not in VALID_ROLES:
            raise ValueError(
                f"Unknown role '{context.role}', expected one of {VALID_ROLES}"
            )

        ResponseModel = cls._SCHEMA_MAP[context.role]
        schema = ResponseModel.model_json_schema()

        template = cls._jinja_env.from_string(PROMPT_TEMPLATE)

        return template.render(
            role=context.role,
            event_id=context.event_id,
            event_type=context.event_type,
            description=context.description,
            requesting_agent_id=context.requesting_agent_id,
            state=context.state,
            available_actions=[
                action.model_dump() for action in context.available_actions
            ],
            hints=hints,
            response_schema=schema,
        )

    @classmethod
    def build_prompt_dict(
        cls, context: EventContext, hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Legacy method to maintain compatibility with dict-based LLM routing."""
        if context.role not in VALID_ROLES:
            raise ValueError(
                f"Unknown role '{context.role}', expected one of {VALID_ROLES}"
            )

        ResponseModel = cls._SCHEMA_MAP[context.role]
        schema = ResponseModel.model_json_schema()
        preamble = f"You are acting as the {context.role}. Respond accordingly."
        return {
            "preamble": preamble,
            "event_id": context.event_id,
            "event_type": context.event_type,
            "role": context.role,
            "description": context.description,
            "requesting_agent_id": context.requesting_agent_id,
            "state": context.state,
            "available_actions": [
                action.model_dump() for action in context.available_actions
            ],
            "hints": hints,
            "response_schema": schema,
            "rendered_prompt": cls.build_prompt(context, hints),
        }
