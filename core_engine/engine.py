"""Core simulation engine for LLMFed.

Advances the federation simulation in discrete ticks. Each public method
does one thing; the inner loop is decomposed into private helpers so each
fits on a screen (Rule 1) and can be tested in isolation.
"""
from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
from pydantic import BaseModel, ValidationError
from models.entities import (
    VALID_ROLES,
    EventContext,
    PossibleAction,
    AgentActionResponse,
    RefereeCallResponse,
    CrowdReactionResponse,
    AnnouncerCommentaryResponse,
    PromoterHintResponse,
    BackstageActionResponse,
)
from core_engine.dispatcher import LLMDispatcher
from core_engine.rulebook import RuleBook
from core_engine.prompt_builder import PromptBuilder
from core_engine.llm_client import LLMClient
from models.db_models import EngineRequestDB, NarrativeLogDB
from agent_service.database import SessionLocal, init_db
from agent_service.crud import get_agents

logger = logging.getLogger(__name__)

# Defensive upper bound for run_ticks (Rule 7)
MAX_TICKS_PER_CALL = 1000

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AppliedAction:
    """A validated and processed action within a tick."""
    action_id: str
    description: str = "No-op"
    effects: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TickResult:
    """Result returned by the engine for each processed role within a tick."""
    tick_id: str
    time_index: int
    agent_id: str
    role: str
    applied_actions: List[AppliedAction]
    state_snapshot: Dict[str, Any]


@dataclass
class GameState:
    """Global game state."""
    current_tick: int = 0
    heat: int = 0
    momentum: int = 0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "current_tick": self.current_tick,
            "heat": self.heat,
            "momentum": self.momentum,
        }


@dataclass
class TickScheduler:
    """Simple monotonic tick counter."""

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


# ---------------------------------------------------------------------------
# Response-parsing dispatch table (avoids long if/elif chain)
# ---------------------------------------------------------------------------
_ROLE_PARSERS = {
    "participant": lambda data: _parse_participant(data),
    "referee": lambda data: _parse_referee(data),
    "crowd": lambda data: _parse_crowd(data),
    "announcer": lambda data: _parse_announcer(data),
    "promoter": lambda data: _parse_promoter(data),
    "backstage": lambda data: _parse_backstage(data),
}


def _parse_participant(data: dict) -> tuple:
    resp = AgentActionResponse(**data)
    meta = {k: v for k, v in resp.model_dump().items()
            if k not in ("event_id", "chosen_action_id", "commentary")}
    return resp.chosen_action_id, resp.commentary or "", meta


def _parse_referee(data: dict) -> tuple:
    resp = RefereeCallResponse(**data)
    return f"referee_{resp.call}", resp.call, {"call": resp.call, "reason": resp.reason}


def _parse_crowd(data: dict) -> tuple:
    resp = CrowdReactionResponse(**data)
    return resp.reaction, resp.reaction, {"heat_adjustment": resp.heat_adjustment}


def _parse_announcer(data: dict) -> tuple:
    resp = AnnouncerCommentaryResponse(**data)
    return "announce", resp.commentary, {}


def _parse_promoter(data: dict) -> tuple:
    resp = PromoterHintResponse(**data)
    return "promoter_hint", "", {"new_hints": resp.new_hints}


def _parse_backstage(data: dict) -> tuple:
    resp = BackstageActionResponse(**data)
    return resp.action, resp.description or "", {}


# ---------------------------------------------------------------------------
# Default agent placeholder (replaces SimpleNamespace — Rule 9)
# ---------------------------------------------------------------------------
@dataclass
class _DefaultAgent:
    """Minimal stand-in when no agents exist in the database."""
    agent_id: str = "agent_default"
    role: str = "participant"
    gimmick_description: str = ""
    current_heat: int = 0
    momentum: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class Engine:
    """Main simulation engine that coordinates ticks."""

    ROLE_ORDER = tuple(VALID_ROLES)

    def __init__(self) -> None:
        self.state = GameState()
        self.scheduler = TickScheduler()
        self.dispatcher = LLMDispatcher()
        self.llm_client = LLMClient()
        init_db()
        self.promoter_hints: Dict[str, Any] = {}

    def set_hints(self, hints: Dict[str, Any]) -> None:
        """Store promoter hints for use in prompt building."""
        self.promoter_hints = hints

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_ticks(self, n: int = 1) -> List[TickResult]:
        """Advance the simulation by *n* ticks.

        Raises ValueError if n < 1 or n > MAX_TICKS_PER_CALL (Rule 2, 7).
        """
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if n > MAX_TICKS_PER_CALL:
            raise ValueError(f"n must be <= {MAX_TICKS_PER_CALL}, got {n}")

        results: List[TickResult] = []
        db = SessionLocal()
        try:
            for _ in range(n):
                tick_results = self._process_one_tick(db)
                if tick_results is None:
                    # Finisher ended the match
                    break
                results.extend(tick_results)
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

    # ------------------------------------------------------------------
    # Private: one tick
    # ------------------------------------------------------------------

    def _process_one_tick(self, db) -> Optional[List[TickResult]]:
        """Process a single tick across all roles.

        Returns the list of TickResults, or None if a finisher ended the match.
        """
        tick_index = self.scheduler.next_tick()
        self.state.current_tick = tick_index
        tick_id = str(uuid.uuid4())

        agents = get_agents(db)
        if not agents:
            agents = [_DefaultAgent()]

        results: List[TickResult] = []
        for role in self.ROLE_ORDER:
            role_agents = [a for a in agents if getattr(a, "role", "participant") == role]
            for agent_db in role_agents:
                result = self._process_agent(db, agent_db, role, tick_id, tick_index)
                if result is None:
                    # Finisher — match over
                    return None
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Private: one agent in one role
    # ------------------------------------------------------------------

    def _process_agent(self, db, agent_db, role: str, tick_id: str, tick_index: int) -> Optional[TickResult]:
        """Process a single agent for a single role in a tick.

        Returns TickResult, or None if a finisher ended the match.
        """
        agent_id = agent_db.agent_id
        context = self._build_context(agent_db, role, tick_index)
        request_id = str(uuid.uuid4())

        # Call LLM
        prompt_payload = PromptBuilder.build_prompt(context, self.promoter_hints)
        try:
            action_data = self.llm_client.send_prompt(prompt_payload)
        except Exception as e:
            logger.error(f"LLM send_prompt error for {agent_id}: {e}")
            action_data = {"action_id": "noop", "description": "Stub action", "meta": {}}

        # Persist engine request
        self._persist_engine_request(db, request_id, agent_id, tick_index, context)

        # Parse + validate
        action_id, description, meta = self._parse_action_data(role, action_data)
        applied_action = RuleBook.validate(action_id, description, meta)

        # Apply game-state effects
        self._apply_game_effects(role, applied_action, meta, action_data)

        # Persist narrative log
        self._persist_narrative_log(db, tick_id, tick_index, agent_id, role, description)

        # Check for match-ending finisher
        if role == "participant" and (action_id == "finisher" or meta.get("move_type") == "finisher"):
            logger.info("Finisher executed, ending match")
            return None

        return TickResult(
            tick_id=tick_id,
            time_index=tick_index,
            agent_id=agent_id,
            role=role,
            applied_actions=[applied_action],
            state_snapshot=self.state.snapshot(),
        )

    # ------------------------------------------------------------------
    # Private: context building
    # ------------------------------------------------------------------

    def _build_context(self, agent_db, role: str, tick_index: int) -> EventContext:
        """Build an EventContext for an agent at a given tick."""
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
        return EventContext(
            event_id=str(uuid.uuid4()),
            event_type="TickEvent",
            role=role,
            description="Engine tick event",
            requesting_agent_id=agent_db.agent_id,
            available_actions=[
                PossibleAction(action_id=aid, name=aid, description=desc)
                for aid, desc in self.dispatcher._ACTIONS
            ],
            state=state_payload,
        )

    # ------------------------------------------------------------------
    # Private: response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_action_data(role: str, data: dict) -> tuple:
        """Validate and translate raw LLM response into (action_id, description, meta)."""
        # Stub fallback responses pass through without schema validation
        if set(data.keys()) <= {"action_id", "description", "meta"}:
            return data.get("action_id", "noop"), data.get("description", ""), data.get("meta", {})

        parser = _ROLE_PARSERS.get(role)
        if parser is None:
            logger.warning(f"Unknown role '{role}' in _parse_action_data, using noop")
            return "noop", "", {}

        try:
            return parser(data)
        except ValidationError as e:
            logger.warning(f"Response validation failed for role {role}: {e}")
            return data.get("action_id", "noop"), data.get("description", ""), data.get("meta", {})

    # ------------------------------------------------------------------
    # Private: game-state effects
    # ------------------------------------------------------------------

    def _apply_game_effects(self, role: str, applied_action: AppliedAction, meta: dict, raw_data: dict) -> None:
        """Mutate self.state based on the role and action outcome."""
        if role == "participant" and applied_action.action_id != "noop":
            self.state.momentum += 2
        elif role == "referee" and meta.get("call") == "pinfall":
            self.state.momentum = 0
            self.state.heat += 1
        elif role == "announcer":
            self.state.heat += 2
        elif role == "promoter" and meta.get("new_hints"):
            self.promoter_hints.update(meta["new_hints"])
        elif role == "backstage" and meta.get("action") == "interfere":
            self.state.heat += 1
            self.state.momentum += 1

        if role == "crowd":
            adj = raw_data.get("heat_adjustment")
            if isinstance(adj, int):
                self.state.heat += adj

    # ------------------------------------------------------------------
    # Private: persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _persist_engine_request(db, request_id: str, agent_id: str, tick_index: int, context: EventContext) -> None:
        """Write an EngineRequestDB row and commit."""
        db.add(EngineRequestDB(
            request_id=request_id,
            agent_id=agent_id,
            due_tick=tick_index,
            context_json=context.model_dump_json(),
            status="processed",
        ))
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _persist_narrative_log(db, tick_id: str, tick_index: int, agent_id: str, role: str, description: str) -> None:
        """Write a NarrativeLogDB row and commit."""
        db.add(NarrativeLogDB(
            tick_id=tick_id,
            time_index=tick_index,
            agent_id=agent_id,
            role=role,
            description=description,
        ))
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise


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
    "MAX_TICKS_PER_CALL",
]
