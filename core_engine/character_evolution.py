"""
Dynamic character development (ENHANCEMENT_PROPOSAL Phase 2.3).

Agents evolve based on performance and storylines:
- Stats: wins, losses, momentum
- Personality traits: confidence, etc.
- Storyline involvement
"""

from __future__ import annotations

import logging
import random
from typing import Optional, Any, Dict

from models.wrestling import MatchResult
from models.roster import WrestlerStats, WrestlerPersonality
from core_engine.heat import update_wrestler_heat

logger = logging.getLogger(__name__)


class CharacterEvolution:
    """Update agent stats and personality after matches."""

    def __init__(self, db_session_factory=None):
        from agent_service.database import SessionLocal
        self._get_db = db_session_factory or SessionLocal

    def update_agent_after_match(
        self,
        agent_id: str,
        federation_id: str,
        match_result: Any,
        won: bool,
        was_decisive: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Adjust stats and personality based on match outcome.

        match_result: MatchResult or dict with winner_id, participant_ids.
        Returns optional character_moment if triggered.
        """
        db = self._get_db()
        try:
            from agent_service.crud import get_agent_by_id
            from agent_service.wrestling_crud import get_current_champion
            from models.db_models import WrestlerStatsDB, WrestlerPersonalityDB, AgentDB

            agent = get_agent_by_id(db, agent_id)
            if not agent:
                return None

            # Update WrestlerStats
            stats_row = db.query(WrestlerStatsDB).filter(
                WrestlerStatsDB.agent_id == agent_id,
                WrestlerStatsDB.federation_id == federation_id,
            ).first()

            if not stats_row:
                from datetime import datetime, timezone
                stats_row = WrestlerStatsDB(
                    agent_id=agent_id,
                    federation_id=federation_id,
                    wins=0, losses=0, draws=0, no_contests=0,
                    title_reigns=0, total_matches=0, main_events=0, ppv_matches=0,
                )
                db.add(stats_row)

            stats_row.total_matches = (stats_row.total_matches or 0) + 1
            if won:
                stats_row.wins = (stats_row.wins or 0) + 1
                momentum_delta = random.randint(5, 15)
            else:
                stats_row.losses = (stats_row.losses or 0) + 1
                momentum_delta = -random.randint(3, 10)

            # Update agent momentum, heat, win/loss streaks
            agent.momentum = (getattr(agent, "momentum", 0) or 0) + momentum_delta
            agent.momentum = max(0, min(100, agent.momentum))
            heat_delta = 3 if won else -1
            new_heat = update_wrestler_heat(agent, heat_delta)
            agent.current_heat = max(0, min(100, new_heat))
            win_streak = getattr(agent, "win_streak", 0) or 0
            loss_streak = getattr(agent, "loss_streak", 0) or 0
            if won:
                win_streak += 1
                loss_streak = 0
            else:
                loss_streak += 1
                win_streak = 0
            if hasattr(agent, "win_streak"):
                agent.win_streak = win_streak
            if hasattr(agent, "loss_streak"):
                agent.loss_streak = loss_streak

            # Update personality (gimmick/personal traits)
            personality_row = db.query(WrestlerPersonalityDB).filter(
                WrestlerPersonalityDB.agent_id == agent_id
            ).first()

            if not personality_row:
                personality_row = WrestlerPersonalityDB(
                    agent_id=agent_id,
                    gimmick_traits={},
                    personal_traits={"confidence": 50},
                )
                db.add(personality_row)

            personal = dict(personality_row.personal_traits or {})
            confidence = personal.get("confidence", 50)
            if was_decisive and won:
                confidence = min(100, confidence + 5)
            elif was_decisive and not won:
                confidence = max(0, confidence - 3)
            personal["confidence"] = confidence
            personality_row.personal_traits = personal

            db.commit()

            if self._should_trigger_character_moment(agent, won, was_decisive):
                return self._generate_character_moment(agent, won)
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"Character evolution failed for {agent_id}: {e}")
            return None
        finally:
            db.close()

    def _should_trigger_character_moment(self, agent, won: bool, was_decisive: bool) -> bool:
        """Decide if a character development moment should trigger."""
        win_streak = getattr(agent, "win_streak", 0) or 0
        loss_streak = getattr(agent, "loss_streak", 0) or 0
        if was_decisive and won and win_streak >= 3:
            return True
        if was_decisive and not won and loss_streak >= 3:
            return True
        return False

    def _generate_character_moment(self, agent, won: bool) -> Dict[str, Any]:
        """Generate a character development moment."""
        return {
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "type": "momentum_shift" if won else "low_point",
            "description": f"{agent.name} {'builds momentum' if won else 'seeks redemption'}",
        }
