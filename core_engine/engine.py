"""Core simulation engine for LLMFed.

Advances the federation simulation in discrete ticks. Each public method
does one thing; the inner loop is decomposed into private helpers so each
fits on a screen (Rule 1) and can be tested in isolation.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
from pydantic import BaseModel, ValidationError
from models.entities import VALID_ROLES
from models.card_structure import SEGMENT_ROLES
from models.calendar import (
    ROLE_TICK_CADENCE,
    PRE_MATCH_ROLES,
    POST_MATCH_ROLES,
    EventPhase,
)
from models.entities import (
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
from core_engine.move_engine import MoveEngine, _cycle_position, _infer_style
from core_engine.rulebook import RuleBook
from core_engine.prompt_builder import PromptBuilder
from llm_abstraction.unified import get_unified_llm
from models.db_models import EngineRequestDB, NarrativeLogDB
from agent_service.database import SessionLocal, init_db
from agent_service.crud import get_agents, get_agent_by_id

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

    def reset(self) -> None:
        """Reset tick counter to 0 (used when starting a new match)."""
        self._counter = 0


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
    "valet": lambda data: _parse_backstage(data),
    "manager": lambda data: _parse_backstage(data),
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
        self.llm_client = get_unified_llm()
        init_db()
        self.promoter_hints: Dict[str, Any] = {}
        self._last_finisher_agent_id: Optional[str] = None  # Set when finisher ends match
        self._last_fan_reaction: Optional[Dict[str, Any]] = None  # From FanEngagement after participant action
        self._match_participant_ids: List[str] = []  # Set via set_match_context
        self._segment_type: Optional[str] = None  # e.g. "match", "opening"
        self._card_type: Optional[str] = None  # e.g. "major_tv", "ppv"

    def set_hints(self, hints: Dict[str, Any]) -> None:
        """Store promoter hints for use in prompt building."""
        self.promoter_hints = hints

    def set_match_context(self, participant_ids: Optional[List[str]] = None) -> None:
        """Set current match participants for opponent context. Call before run_full_match."""
        self._match_participant_ids = participant_ids or []
        self._last_fan_reaction = None  # Reset at match start

    def set_segment_context(
        self,
        segment_type: Optional[str] = None,
        card_type: Optional[str] = None,
    ) -> None:
        """Set current segment/card context for POV state. Call before run_full_match if using full cards."""
        self._segment_type = segment_type
        self._card_type = card_type

    def get_last_finisher_agent_id(self) -> Optional[str]:
        """Return agent who hit the finisher, or None if match ended by max_ticks."""
        return getattr(self, "_last_finisher_agent_id", None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_pre_match(self) -> List[TickResult]:
        """Run pre_match phase once: promoter sets story/hints, backstage prepares.

        Call before run_ticks to set promoter hints for the match.
        """
        return self._run_phase(EventPhase.PRE_MATCH, phase_tick=0)

    def run_post_match(self, match_result: Optional[Dict[str, Any]] = None) -> List[TickResult]:
        """Run post_match phase once: promoter reacts, backstage plans next.

        Call after run_ticks returns None (finisher ended match).
        """
        return self._run_phase(EventPhase.POST_MATCH, phase_tick=-1, match_result=match_result)

    def run_one_segment_tick(
        self,
        segment_type: str,
        card_type: str,
        card_run_state: Dict[str, Any],
        hints: Dict[str, Any],
    ) -> List[TickResult]:
        """Run one tick for a non-match segment (opening, promo, backstage, closing, etc.).

        Runs each role that sees this segment (from SEGMENT_ROLES), builds segment-only
        context (no match state), calls LLM, persists narrative. Returns TickResults.
        """
        self.set_hints(hints)
        roles = list(SEGMENT_ROLES.get(segment_type, []))
        results: List[TickResult] = []
        db = SessionLocal()
        try:
            agents = get_agents(db)
            if not agents:
                agents = [_DefaultAgent()]
            tick_id = str(uuid.uuid4())
            segment_tick = 0
            for role in roles:
                role_agents = [a for a in agents if getattr(a, "role", "participant") == role]
                for agent_db in role_agents:
                    context = self._build_segment_context(
                        agent_db, role, segment_type, card_type, card_run_state
                    )
                    result = self._process_agent_for_segment_tick(
                        db, agent_db, role, tick_id, segment_tick, context
                    )
                    if result:
                        results.append(result)
            # Promo segment with wrestlers cutting the promo
            if segment_type == "promo":
                promo_ids = hints.get("promo_participant_ids") or []
                for pid in promo_ids:
                    agent_db = get_agent_by_id(db, pid)
                    if agent_db:
                        promo_state = dict(card_run_state) if isinstance(card_run_state, dict) else card_run_state
                        promo_state = {**promo_state, "promo_cutter": True}
                        context = self._build_segment_context(
                            agent_db, "participant", segment_type, card_type, promo_state
                        )
                        context = context.model_copy(
                            update={"description": "You are cutting a promo. React in character."}
                        )
                        result = self._process_agent_for_segment_tick(
                            db, agent_db, "participant", tick_id, segment_tick, context
                        )
                        if result:
                            results.append(result)
        finally:
            db.close()
        return results

    def run_full_match(self, max_ticks: int = 500) -> List[TickResult]:
        """Run full match flow: pre_match → match ticks (until finisher) → post_match.

        Returns all TickResults from pre_match, match, and post_match phases.
        Resets tick scheduler so each full match starts from tick 1.
        """
        self.scheduler.reset()
        results: List[TickResult] = []
        results.extend(self.run_pre_match())

        db = SessionLocal()
        try:
            for _ in range(max_ticks):
                tick_results = self._process_one_tick(db)
                if tick_results is None:
                    break
                results.extend(tick_results)
            else:
                logger.warning("Match ended by max_ticks limit, no finisher")
            # Run post_match after match ends (finisher or max_ticks)
            match_result = {"current_tick": self.state.current_tick} if self.state else None
        finally:
            db.close()

        results.extend(self.run_post_match(match_result))
        return results

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
    # Private: phase execution (pre_match, post_match)
    # ------------------------------------------------------------------

    def _run_phase(
        self,
        phase: EventPhase,
        phase_tick: int,
        match_result: Optional[Dict[str, Any]] = None,
    ) -> List[TickResult]:
        """Run promoter + backstage for pre_match or post_match phase."""
        event_type = "PreMatchEvent" if phase == EventPhase.PRE_MATCH else "PostMatchEvent"
        desc = (
            "Pre-match: promoter sets story, backstage prepares"
            if phase == EventPhase.PRE_MATCH
            else "Post-match: promoter reacts to outcome, backstage plans next"
        )
        roles = PRE_MATCH_ROLES if phase == EventPhase.PRE_MATCH else POST_MATCH_ROLES

        results: List[TickResult] = []
        db = SessionLocal()
        try:
            agents = get_agents(db)
            if not agents:
                agents = [_DefaultAgent()]
            tick_id = str(uuid.uuid4())

            for role in roles:
                role_agents = [a for a in agents if getattr(a, "role", "participant") == role]
                for agent_db in role_agents:
                    context = self._build_context(
                        agent_db,
                        role,
                        phase_tick,
                        db=db,
                        event_type=event_type,
                        description=desc,
                        match_result=match_result,
                    )
                    result = self._process_agent_for_phase(
                        db, agent_db, role, tick_id, phase_tick, context
                    )
                    if result:
                        results.append(result)
        finally:
            db.close()
        return results

    def _process_agent_for_phase(
        self,
        db,
        agent_db,
        role: str,
        tick_id: str,
        phase_tick: int,
        context: EventContext,
    ) -> Optional[TickResult]:
        """Process promoter or backstage for pre/post phase (no finisher check)."""
        agent_id = agent_db.agent_id
        request_id = str(uuid.uuid4())
        llm_config = getattr(agent_db, "llm_config", None) or {}
        agent_model = llm_config.get("model") if isinstance(llm_config, dict) else None

        try:
            prompt_payload = PromptBuilder.build_prompt(context, self.promoter_hints)
            action_data = self.llm_client.send_prompt(prompt_payload, model=agent_model)
        except Exception as e:
            logger.error(f"LLM send_prompt error for {agent_id}: {e}")
            action_data = {"action_id": "noop", "description": "Stub action", "meta": {}}

        self._persist_engine_request(db, request_id, agent_id, phase_tick, context)
        action_id, description, meta = self._parse_action_data(role, action_data)
        applied_action = RuleBook.validate(action_id, description, meta)
        self._apply_game_effects(role, applied_action, meta, action_data)
        self._persist_narrative_log(db, tick_id, phase_tick, agent_id, role, description)

        return TickResult(
            tick_id=tick_id,
            time_index=phase_tick,
            agent_id=agent_id,
            role=role,
            applied_actions=[applied_action],
            state_snapshot=self.state.snapshot(),
        )

    # ------------------------------------------------------------------
    # Private: one tick
    # ------------------------------------------------------------------

    def _process_one_tick(self, db) -> Optional[List[TickResult]]:
        """Process a single tick across all roles.

        Uses ROLE_TICK_CADENCE: participant/ref every tick; announcer every 4;
        crowd every 6; backstage every 12; promoter every 20. Roles that don't
        run this tick are skipped (no LLM call).
        """
        tick_index = self.scheduler.next_tick()
        self.state.current_tick = tick_index
        tick_id = str(uuid.uuid4())

        agents = get_agents(db)
        if not agents:
            agents = [_DefaultAgent()]

        results: List[TickResult] = []
        participant_agents = [a for a in agents if getattr(a, "role", "participant") == "participant"]
        use_parallel = len(participant_agents) >= 2 and (tick_index - 1) % ROLE_TICK_CADENCE.get("participant", 1) == 0

        for role in self.ROLE_ORDER:
            cadence = ROLE_TICK_CADENCE.get(role, 1)
            if (tick_index - 1) % cadence != 0:
                continue
            role_agents = [a for a in agents if getattr(a, "role", "participant") == role]
            if role == "participant" and use_parallel and len(role_agents) >= 2:
                part_results = self._process_participants_parallel(db, role_agents, tick_id, tick_index)
                if part_results is None:
                    return None
                results.extend(part_results)
            else:
                for agent_db in role_agents:
                    result = self._process_agent(db, agent_db, role, tick_id, tick_index)
                    if result is None:
                        return None
                    results.append(result)
        return results

    def _process_participants_parallel(
        self, db, role_agents: List, tick_id: str, tick_index: int
    ) -> Optional[List[TickResult]]:
        """Run participant LLM calls in parallel, then apply effects sequentially."""
        def _call_llm(agent_db):
            context = self._build_context(agent_db, "participant", tick_index, db=db)
            prompt = PromptBuilder.build_prompt(context, self.promoter_hints)
            llm_config = getattr(agent_db, "llm_config", None) or {}
            model = llm_config.get("model") if isinstance(llm_config, dict) else None
            try:
                return agent_db, self.llm_client.send_prompt(prompt, model=model)
            except Exception as e:
                logger.error(f"LLM send_prompt error for {agent_db.agent_id}: {e}")
                return agent_db, {"action_id": "noop", "description": "Stub action", "meta": {}}

        with ThreadPoolExecutor(max_workers=len(role_agents)) as ex:
            futures = {ex.submit(_call_llm, a): a for a in role_agents}
            agent_to_action: Dict[str, tuple] = {}
            for fut in as_completed(futures):
                agent_db, action_data = fut.result()
                agent_to_action[agent_db.agent_id] = (agent_db, action_data)

        results: List[TickResult] = []
        for agent_db in role_agents:
            agent_id = agent_db.agent_id
            _, action_data = agent_to_action.get(agent_id, (agent_db, {"action_id": "noop", "description": "", "meta": {}}))
            context = self._build_context(agent_db, "participant", tick_index, db=db)
            request_id = str(uuid.uuid4())
            self._persist_engine_request(db, request_id, agent_id, tick_index, context)
            action_id, description, meta = self._parse_action_data("participant", action_data)
            applied_action = RuleBook.validate(action_id, description, meta)
            self._apply_game_effects("participant", applied_action, meta, action_data)
            if applied_action.action_id != "noop":
                self._update_fan_reaction(agent_db, action_id, meta, db)
            self._persist_narrative_log(db, tick_id, tick_index, agent_id, "participant", description)
            if action_id == "finisher" or meta.get("move_type") == "finisher" or MoveEngine.is_finisher(action_id):
                logger.info(f"Finisher executed by {agent_id}, ending match")
                self._last_finisher_agent_id = agent_id
                return None
            results.append(TickResult(
                tick_id=tick_id,
                time_index=tick_index,
                agent_id=agent_id,
                role="participant",
                applied_actions=[applied_action],
                state_snapshot=self.state.snapshot(),
            ))
        return results

    # ------------------------------------------------------------------
    # Private: one agent in one role
    # ------------------------------------------------------------------

    def _process_agent(
        self, db, agent_db, role: str, tick_id: str, tick_index: int
    ) -> Optional[TickResult]:
        """Process a single agent for a single role in a tick.

        Returns TickResult, or None if a finisher ended the match.
        """
        agent_id = agent_db.agent_id
        context = self._build_context(agent_db, role, tick_index, db=db)
        request_id = str(uuid.uuid4())

        # Call LLM (use per-agent model from llm_config if present)
        prompt_payload = PromptBuilder.build_prompt(context, self.promoter_hints)
        llm_config = getattr(agent_db, "llm_config", None) or {}
        agent_model = llm_config.get("model") if isinstance(llm_config, dict) else None
        try:
            action_data = self.llm_client.send_prompt(prompt_payload, model=agent_model)
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

        # FanReaction: after participant action, generate crowd reaction for next crowd tick
        if role == "participant" and applied_action.action_id != "noop" and db:
            self._update_fan_reaction(agent_db, action_id, meta, db)

        # Persist narrative log
        self._persist_narrative_log(db, tick_id, tick_index, agent_id, role, description)

        # Check for match-ending finisher
        if role == "participant" and (
            action_id == "finisher"
            or meta.get("move_type") == "finisher"
            or MoveEngine.is_finisher(action_id)
        ):
            logger.info(f"Finisher executed by {agent_id}, ending match")
            self._last_finisher_agent_id = agent_id  # For orchestrator to set winner_id
            return None

        return TickResult(
            tick_id=tick_id,
            time_index=tick_index,
            agent_id=agent_id,
            role=role,
            applied_actions=[applied_action],
            state_snapshot=self.state.snapshot(),
        )

    def _build_segment_context(
        self,
        agent_db,
        role: str,
        segment_type: str,
        card_type: str,
        card_run_state: Dict[str, Any],
    ) -> EventContext:
        """Build EventContext for a non-match segment tick (opening, promo, backstage, closing)."""
        _role_to_pov = {
            "participant": "ring",
            "referee": "ring",
            "announcer": "tv",
            "crowd": "crowd",
            "valet": "ring",
            "manager": "ring",
            "backstage": "backstage",
            "promoter": "promoter",
        }
        pov = _role_to_pov.get(role, "ring")
        state_payload: Dict[str, Any] = {
            "mode": "segment",
            "segment_type": segment_type,
            "card_type": card_type,
            "pov": pov,
            "card_run_state": card_run_state,
            "current_spot": {"segment_type": segment_type},
        }
        available_actions = [
            PossibleAction(action_id=aid, name=aid, description=desc)
            for aid, desc in self.dispatcher._ACTIONS
        ]
        desc = f"Segment: {segment_type}. Card type: {card_type}. Respond in character."
        return EventContext(
            event_id=str(uuid.uuid4()),
            event_type="SegmentEvent",
            role=role,
            description=desc,
            requesting_agent_id=agent_db.agent_id,
            available_actions=available_actions,
            state=state_payload,
        )

    def _process_agent_for_segment_tick(
        self,
        db,
        agent_db,
        role: str,
        tick_id: str,
        segment_tick: int,
        context: EventContext,
    ) -> Optional[TickResult]:
        """Process one agent for a segment tick (no match, no finisher check)."""
        agent_id = agent_db.agent_id
        request_id = str(uuid.uuid4())
        llm_config = getattr(agent_db, "llm_config", None) or {}
        agent_model = llm_config.get("model") if isinstance(llm_config, dict) else None
        try:
            prompt_payload = PromptBuilder.build_prompt(context, self.promoter_hints)
            action_data = self.llm_client.send_prompt(prompt_payload, model=agent_model)
        except Exception as e:
            logger.error("LLM send_prompt error for %s (segment): %s", agent_id, e)
            action_data = {"action_id": "noop", "description": "Stub action", "meta": {}}
        self._persist_engine_request(db, request_id, agent_id, segment_tick, context)
        action_id, description, meta = self._parse_action_data(role, action_data)
        applied_action = RuleBook.validate(action_id, description, meta)
        self._apply_game_effects(role, applied_action, meta, action_data)
        self._persist_narrative_log(db, tick_id, segment_tick, agent_id, role, description)
        return TickResult(
            tick_id=tick_id,
            time_index=segment_tick,
            agent_id=agent_id,
            role=role,
            applied_actions=[applied_action],
            state_snapshot=self.state.snapshot() if self.state else {},
        )

    # ------------------------------------------------------------------
    # Private: context building
    # ------------------------------------------------------------------

    def _build_context(
        self,
        agent_db,
        role: str,
        tick_index: int,
        *,
        db=None,
        event_type: str = "TickEvent",
        description: str = "Engine tick event",
        match_result: Optional[Dict[str, Any]] = None,
    ) -> EventContext:
        """Build an EventContext for an agent at a given tick or phase."""
        gimmick = getattr(agent_db, "gimmick_description", "")
        momentum = getattr(agent_db, "momentum", self.state.momentum) or self.state.momentum
        position = _cycle_position(tick_index)
        style = _infer_style(gimmick)
        participant_ids = getattr(self, "_match_participant_ids", None) or []
        opponent_id: Optional[str] = None
        opponent_style: Optional[str] = None
        if len(participant_ids) == 2 and role == "participant" and db:
            other = [p for p in participant_ids if p != agent_db.agent_id]
            if other:
                opponent_id = other[0]
                opp_agent = get_agent_by_id(db, opponent_id)
                if opp_agent:
                    opponent_style = _infer_style(getattr(opp_agent, "gimmick_description", ""))
        # POV: role → temporal stream (ring, tv, crowd, backstage, promoter)
        _role_to_pov = {
            "participant": "ring",
            "referee": "ring",
            "announcer": "tv",
            "crowd": "crowd",
            "valet": "ring",
            "manager": "ring",
            "backstage": "backstage",
            "promoter": "promoter",
        }
        pov = _role_to_pov.get(role, "ring")

        state_payload: Dict[str, Any] = {
            "current_tick": tick_index,
            "gimmick_description": gimmick,
            "heat": getattr(agent_db, "current_heat", self.state.heat),
            "momentum": momentum,
            "opponent_id": opponent_id,
            "opponent_style": opponent_style,
            "stipulation": "StandardMatch",
            "current_spot": {"segment": tick_index},
            "current_position": position,
            "style": style,
            "mode": "tick",
            "pov": pov,
        }
        if getattr(self, "_segment_type", None):
            state_payload["segment_type"] = self._segment_type
        if getattr(self, "_card_type", None):
            state_payload["card_type"] = self._card_type
        if match_result is not None:
            state_payload["match_result"] = match_result
        if role == "crowd":
            lfr = getattr(self, "_last_fan_reaction", None)
            if lfr:
                state_payload["last_fan_reaction"] = lfr
        if role == "participant":
            moves = MoveEngine.get_available_moves(
                position=position,
                tick=tick_index,
                momentum=momentum,
                style=style,
                opponent_style=opponent_style,
                include_finishers=True,
            )
            available_actions = [
                PossibleAction(action_id=aid, name=aid, description=desc)
                for aid, desc in moves
            ]
        else:
            available_actions = [
                PossibleAction(action_id=aid, name=aid, description=desc)
                for aid, desc in self.dispatcher._ACTIONS
            ]
        return EventContext(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            role=role,
            description=description,
            requesting_agent_id=agent_db.agent_id,
            available_actions=available_actions,
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

    def _update_fan_reaction(
        self,
        agent_db,
        action_id: str,
        meta: dict,
        db,
    ) -> None:
        """Generate FanReaction after participant action; store for next crowd tick."""
        try:
            from core_engine.fan_engagement import FanEngagement
            heat = getattr(agent_db, "current_heat", 50) or 50
            move_quality = 8 if MoveEngine.is_finisher(action_id) else (6 if meta.get("move_type") == "signature" else 5)
            storyline_sig = 7 if self.promoter_hints.get("storyline") else 5
            event = {"action_id": action_id, "agent_id": agent_db.agent_id, "heat": heat}
            fe = FanEngagement()
            reaction = fe.generate_fan_reaction(
                event,
                agent_popularity={"heat": heat},
                move_quality=move_quality,
                storyline_significance=storyline_sig,
                surprise_factor=0,
            )
            self._last_fan_reaction = reaction.model_dump()
        except Exception as e:
            logger.debug("FanReaction update skipped: %s", e)

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
