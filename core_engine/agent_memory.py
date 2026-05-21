"""
Agent memory (ENHANCEMENT_PROPOSAL Phase 4.1).

Recall relevant events for context.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class AgentMemory:
    """Agent memory: recall relevant events."""

    def __init__(self, db_session_factory=None):
        from agent_service.database import SessionLocal
        self._get_db = db_session_factory or SessionLocal

    def recall_relevant_events(self, agent_id: str, context: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Recall events relevant to current context."""
        db = self._get_db()
        try:
            from models.db_models import NarrativeLogDB
            logs = (
                db.query(NarrativeLogDB)
                .filter(NarrativeLogDB.agent_id == agent_id)
                .order_by(NarrativeLogDB.time_index.desc())
                .limit(limit)
                .all()
            )
            out = []
            for log in logs:
                out.append({
                    "tick": log.time_index,
                    "role": log.role,
                    "description": log.description,
                    "created_at": log.created_at.isoformat() if hasattr(log.created_at, "isoformat") else str(log.created_at),
                })
            return out
        except Exception as e:
            logger.warning("Memory recall failed: %s", e)
            return []
        finally:
            db.close()
