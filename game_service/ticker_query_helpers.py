"""
Reusable query helpers for world_ticker and related tick modules.

These eliminate repeated filter patterns that appear throughout the
ticker pipeline (active wrestlers, NPC federations, etc.).
"""

from sqlalchemy.orm import Session

from models.game_models import GameWrestlerDB, GameFederationDB


def get_active_wrestlers(db: Session, world_id: str):
    """Return all active wrestlers in the given world."""
    return db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == True,
    ).all()


def get_npc_federations(db: Session, world_id: str):
    """Return all active NPC-controlled federations in the given world."""
    return db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world_id,
        GameFederationDB.is_npc == True,
        GameFederationDB.is_active == True,
    ).all()


def get_active_federations(db: Session, world_id: str):
    """Return all active federations (player + NPC) in the given world."""
    return db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world_id,
        GameFederationDB.is_active == True,
    ).all()
