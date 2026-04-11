"""
Audit Service — convenience helpers for recording game-state changes.

Usage::

    from game_service.audit_service import record_change

    record_change(
        db, entity_type="wrestler", entity_id=wrestler.id,
        field_name="popularity", old_value=70, new_value=75,
        actor_type="system", world_id=world.id,
        reason="show_performance_boost",
    )
"""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.audit_models import AuditLogDB

logger = logging.getLogger(__name__)


def record_change(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    field_name: str,
    old_value: Any = None,
    new_value: Any = None,
    action: str = "update",
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    world_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Append an audit-log entry to the current DB session.

    The entry is staged (``db.add``) but NOT committed — the caller is
    responsible for committing as part of its own transaction.
    """
    db.add(AuditLogDB(
        entity_type=entity_type,
        entity_id=str(entity_id),
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        action=action,
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id else None,
        world_id=str(world_id) if world_id else None,
        reason=reason,
    ))


def record_creation(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    new_value: Any = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    world_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Shorthand for recording a CREATE event."""
    record_change(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name="*",
        new_value=new_value,
        action="create",
        actor_type=actor_type,
        actor_id=actor_id,
        world_id=world_id,
        reason=reason,
    )


def record_deletion(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    old_value: Any = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    world_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Shorthand for recording a DELETE event."""
    record_change(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name="*",
        old_value=old_value,
        action="delete",
        actor_type=actor_type,
        actor_id=actor_id,
        world_id=world_id,
        reason=reason,
    )
