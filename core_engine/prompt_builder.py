from typing import Any, Dict

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

class PromptBuilder:
    """Builds prompts for LLM interactions based on event context and promoter hints."""

    _SCHEMA_MAP: Dict[str, type] = {
        "participant": AgentActionResponse,
        "referee": RefereeCallResponse,
        "crowd": CrowdReactionResponse,
        "announcer": AnnouncerCommentaryResponse,
        "promoter": PromoterHintResponse,
        "backstage": BackstageActionResponse,
        "valet": BackstageActionResponse,
        "manager": BackstageActionResponse,
    }

    @staticmethod
    def build_prompt(context: EventContext, hints: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs a combined prompt payload containing event context and promoter-provided hints."""
        if context.role not in VALID_ROLES:
            raise ValueError(f"Unknown role '{context.role}', expected one of {VALID_ROLES}")

        ResponseModel = PromptBuilder._SCHEMA_MAP[context.role]
        schema = ResponseModel.model_json_schema()
        preamble = f"You are acting as the {context.role}. Respond accordingly."
        if context.role == "promoter" and hints.get("promoter_guidance"):
            preamble = preamble + "\n\n**Guidance for building toward the marquee show:**\n" + hints["promoter_guidance"]
        if context.role == "promoter":
            mc = hints.get("month_context") or {}
            if mc:
                phase = mc.get("phase", "?")
                wk = mc.get("month_week_index", "?")
                is_ppv = mc.get("is_ppv_week", False)
                preamble = preamble + f"\n\n**Month context:** Week {wk} of month. Phase: {phase}. PPV week: {is_ppv}."
        if context.role == "promoter":
            run_state = hints.get("run_state") or {}
            if run_state.get("recent_ripples") or run_state.get("recent_trapdoors"):
                preamble = preamble + "\n\n**Run timeline (recent effects):**"
                for r in (run_state.get("recent_ripples") or [])[:5]:
                    preamble = preamble + f"\n  Ripple: {r.get('cause', '?')} — {r.get('description', '')}"
                for t in (run_state.get("recent_trapdoors") or [])[:3]:
                    preamble = preamble + f"\n  Trapdoor: {t.get('reason', '?')} (from → to)"
            tier9 = hints.get("tier9_recall")
            if tier9:
                preamble = preamble + "\n\n**Tier 9 (canonical immutables):**\n" + tier9[:2000]
        if context.role == "crowd":
            audience = hints.get("audience") or {}
            fav = audience.get("favorite_agent_ids") or []
            hated = audience.get("hated_agent_ids") or []
            if fav or hated:
                parts = []
                if fav:
                    parts.append(f"The crowd strongly favors these wrestlers: {fav}. Cheer and support them.")
                if hated:
                    parts.append(f"The crowd strongly opposes these wrestlers: {hated}. Boo and oppose them.")
                preamble = preamble + "\n\n**Crowd bias:**\n" + " ".join(parts)
            lfr = (context.state or {}).get("last_fan_reaction")
            if lfr:
                intensity = lfr.get("intensity", 5)
                sentiment = lfr.get("sentiment", "mixed")
                chants = lfr.get("chants", [])
                preamble = preamble + f"\n\n**Last in-ring reaction:** intensity={intensity}, sentiment={sentiment}"
                if chants:
                    preamble = preamble + f", chants: {chants}"
                preamble = preamble + ". React accordingly."
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
