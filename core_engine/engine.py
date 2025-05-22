"""Core simulation engine skeleton for LLMFed.

This module defines the minimal data structures and runtime loop required to
advance the federation simulation in discrete *ticks*.  It will be expanded
incrementally following the roadmap in `codebase.md`.
"""
from __future__ import annotations

import uuid
import logging
import random
from dataclasses import dataclass, field
from typing import Any, List, Dict
from pydantic import BaseModel
from models.entities import EventContext, PossibleAction
from core_engine.dispatcher import LLMDispatcher
from core_engine.rulebook import RuleBook
from core_engine.prompt_builder import PromptBuilder
from core_engine.llm_client import LLMClient
from sqlalchemy.orm import Session
from models.db_models import EngineRequestDB, NarrativeLogDB
from agent_service.database import SessionLocal, init_db
from agent_service.crud import get_agents, get_agent_by_id
import datetime
from types import SimpleNamespace  # for default dummy agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes (early minimal versions)
# ---------------------------------------------------------------------------

@dataclass
class AppliedAction:
    """Placeholder representing a validated and processed action within a tick."""

    action_id: str
    description: str = "No-op"
    effects: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TickResult:
    """Result returned by the engine for each processed role within a tick."""

    tick_id: str
    time_index: int
    agent_id: str  # which agent acted
    role: str  # role of the agent
    applied_actions: List[AppliedAction]
    state_snapshot: Dict[str, Any]


@dataclass
class GameState:
    """Global game state (very minimal for now)."""

    current_tick: int = 0
    heat: int = 0  # crowd energy
    momentum: int = 0  # match momentum

    def snapshot(self) -> Dict[str, Any]:
        """Return a lightweight snapshot of the current state."""
        return {
            "current_tick": self.current_tick,
            "heat": self.heat,
            "momentum": self.momentum,
        }


@dataclass
class TickScheduler:
    """Very simple round-robin scheduler placeholder."""

    def __init__(self) -> None:
        self._counter: int = 0

    def next_tick(self) -> int:
        self._counter += 1
        return self._counter


# ---------------------------------------------------------------------------
# Engine Request Schema
# ---------------------------------------------------------------------------
class EngineRequest(BaseModel):
    """Schema representing a queued engine request."""
    request_id: str
    agent_id: str
    due_tick: int
    context: EventContext


class Engine:
    """Main simulation engine that coordinates ticks."""

    def __init__(self) -> None:
        self.state = GameState()
        self.scheduler = TickScheduler()
        self.dispatcher = LLMDispatcher()
        self.llm_client = LLMClient()
        
        # Ensure tables exist
        init_db()

        # Store latest promoter hints
        self.promoter_hints: Dict[str, Any] = {}
        # Define execution order of roles per tick
        self.role_order = ["promoter", "participant", "referee", "crowd", "announcer", "backstage"]

    def set_hints(self, hints: Dict[str, Any]) -> None:
        """Store promoter hints for use in prompt building."""
        self.promoter_hints = hints

    def _parse_action_data(self, role: str, data: dict) -> tuple[str, str, dict]:
        """Validate and translate raw LLM response into action_id, description, meta."""
        from pydantic import ValidationError
        from models.entities import (
            AgentActionResponse, RefereeCallResponse, CrowdReactionResponse,
            AnnouncerCommentaryResponse, PromoterHintResponse, BackstageActionResponse
        )
        # Skip validation for stub fallback (noop or dispatcher stub)
        if set(data.keys()) <= {"action_id", "description", "meta"}:
            return data.get("action_id", "noop"), data.get("description", ""), data.get("meta", {})
        try:
            if role == "participant":
                resp = AgentActionResponse(**data)
                return resp.chosen_action_id, resp.commentary or "", {k: v for k,v in resp.dict().items() if k not in ("event_id","chosen_action_id","commentary")}
            if role == "referee":
                resp = RefereeCallResponse(**data)
                aid = f"referee_{resp.call}"
                return aid, resp.call, {"call": resp.call, "reason": resp.reason}
            if role == "crowd":
                resp = CrowdReactionResponse(**data)
                return resp.reaction, resp.reaction, {"heat_adjustment": resp.heat_adjustment}
            if role == "announcer":
                resp = AnnouncerCommentaryResponse(**data)
                return "announce", resp.commentary, {}
            if role == "promoter":
                resp = PromoterHintResponse(**data)
                return "promoter_hint", "", {"new_hints": resp.new_hints}
            if role == "backstage":
                resp = BackstageActionResponse(**data)
                return resp.action, resp.description or "", {}
        except ValidationError as e:
            logging.error(f"Response validation failed for role {role}: {e}")
        return data.get("action_id", "noop"), data.get("description", ""), data.get("meta", {})

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def run_ticks(self, n: int = 1) -> List[TickResult]:
        """Advance the simulation *n* ticks with proper DB session handling."""
        results: List[TickResult] = []
        db = SessionLocal()
        try:
            for _ in range(max(1, n)):
                tick_index = self.scheduler.next_tick()
                self.state.current_tick = tick_index
                tick_id = str(uuid.uuid4())
                agents = get_agents(db)
                if not agents:
                    agents = [SimpleNamespace(agent_id="agent_default", role="participant", gimmick_description="")]
                for role in self.role_order:
                    for agent_db in [a for a in agents if getattr(a, 'role', 'participant') == role]:
                        agent_id = agent_db.agent_id
                        state_payload = {
                            "current_tick": tick_index,
                            "gimmick_description": getattr(agent_db, "gimmick_description", ""),
                            "heat": getattr(agent_db, "current_heat", self.state.heat),
                            "momentum": getattr(agent_db, "momentum", self.state.momentum),
                            "opponent_id": None,
                            "stipulation": "StandardMatch",
                            "current_spot": {"segment": tick_index},
                            "mode": "tick",
                        }
                        context = EventContext(
                            event_id=str(uuid.uuid4()),
                            event_type="TickEvent",
                            role=role,
                            description="Engine tick event",
                            requesting_agent_id=agent_id,
                            available_actions=[PossibleAction(action_id=aid, name=aid, description=desc) for aid, desc in self.dispatcher._ACTIONS],
                            state=state_payload,
                        )
                        request = EngineRequest(
                            request_id=str(uuid.uuid4()),
                            agent_id=agent_id,
                            due_tick=tick_index,
                            context=context
                        )
                        prompt_payload = PromptBuilder.build_prompt(context, self.promoter_hints)
                        try:
                            action_data = self.llm_client.send_prompt(prompt_payload)
                        except Exception as e:
                            logger.error(f"LLM send_prompt error for {agent_id}: {e}")
                            action_data = {"action_id": "noop", "description": "Stub action", "meta": {}}
                        db.add(EngineRequestDB(
                            request_id=request.request_id,
                            agent_id=agent_id,
                            due_tick=tick_index,
                            context_json=context.json(),
                            status="processed"
                        ))
                        db.commit()
                        action_id, description, meta = self._parse_action_data(role, action_data)
                        applied_action = RuleBook.validate(action_id, description, meta)
                        if role == "participant" and applied_action.action_id != "noop":
                            self.state.momentum += 2
                        elif role == "referee" and meta.get("call") == "pinfall":
                            self.state.momentum = 0
                            self.state.heat += 1
                        elif role == "announcer":
                            self.state.heat += 2
                        elif role == "promoter" and meta.get("new_hints"):
                            self.promoter_hints.update(meta.get("new_hints"))
                        elif role == "backstage" and meta.get("action") == "interfere":
                            self.state.heat += 1
                            self.state.momentum += 1
                        if role == "crowd":
                            adj = action_data.get("heat_adjustment")
                            if isinstance(adj, int):
                                self.state.heat += adj
                        db.add(NarrativeLogDB(
                            tick_id=tick_id,
                            time_index=tick_index,
                            agent_id=agent_id,
                            role=role,
                            description=description
                        ))
                        db.commit()
                        if role == "participant" and (action_id == "finisher" or meta.get("move_type") == "finisher"):
                            logger.info("Finisher executed, ending match")
                            return results
                        results.append(TickResult(
                            tick_id=tick_id,
                            time_index=tick_index,
                            agent_id=agent_id,
                            role=role,
                            applied_actions=[applied_action],
                            state_snapshot=self.state.snapshot(),
                        ))
            return results
        finally:
            db.close()

    def get_pending_requests(self) -> list:
        """Get pending requests from database."""
        db = SessionLocal()
        try:
            return db.query(EngineRequestDB).filter(
                EngineRequestDB.status == "pending"
            ).all()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Singleton instance for easy import by FastAPI
# ---------------------------------------------------------------------------
engine_instance = Engine()

__all__ = [
    "AppliedAction",
    "TickResult",
    "GameState",
    "TickScheduler",
    "Engine",
    "EngineRequest",
    "engine_instance",
]
