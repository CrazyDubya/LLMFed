"""
Event sourcing audit log — records every state mutation for traceability.

Each row captures who changed what, when, and the old/new values so that
game-state changes can be reviewed, debugged, or replayed.
"""

from sqlalchemy import Column, String, DateTime, JSON, Text, Index
from datetime import datetime, timezone
import uuid

from models.db_models import Base


def _utc_now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class AuditLogDB(Base):
    """Immutable audit log entry for a game-state change."""

    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=_uuid)
    timestamp = Column(DateTime, nullable=False, default=_utc_now, index=True)

    # What changed
    entity_type = Column(
        String(50), nullable=False, index=True
    )  # e.g. "wrestler", "federation", "contract"
    entity_id = Column(String, nullable=False, index=True)  # PK of the affected row
    field_name = Column(
        String(100), nullable=False
    )  # e.g. "popularity", "alignment", "salary_weekly"
    action = Column(
        String(20), nullable=False, default="update"
    )  # "create", "update", "delete"

    # Old and new values (JSON-encoded for flexibility)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    # Who caused the change
    actor_type = Column(String(30), nullable=True)  # "system", "player", "ai", "admin"
    actor_id = Column(String, nullable=True)  # player_id, agent_id, or None
    world_id = Column(String, nullable=True, index=True)

    # Optional context
    reason = Column(Text, nullable=True)  # human-readable reason / event name

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_world_ts", "world_id", "timestamp"),
    )
