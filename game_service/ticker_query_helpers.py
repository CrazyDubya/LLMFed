"""
Reusable query helpers for world_ticker and related tick modules.

These eliminate repeated filter patterns that appear throughout the
ticker pipeline (active wrestlers, NPC federations, etc.).
"""

from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB, GameFederationDB, ContractDB, GimmickHistoryDB,
)


def get_wrestler_federation(db: Session, wrestler_id: str):
    """Return the federation a wrestler currently holds an active contract with."""
    contract = db.query(ContractDB).filter(
        ContractDB.wrestler_id == wrestler_id,
        ContractDB.status == "active",
    ).first()
    if not contract:
        return None
    return db.query(GameFederationDB).filter(
        GameFederationDB.id == contract.federation_id,
    ).first()


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


def get_active_gimmick(db: Session, wrestler_id: str):
    """Return a wrestler's current active gimmick, if any."""
    return db.query(GimmickHistoryDB).filter(
        GimmickHistoryDB.wrestler_id == wrestler_id,
        GimmickHistoryDB.is_active == True,
    ).first()


def get_active_federations(db: Session, world_id: str):
    """Return all active federations (player + NPC) in the given world."""
    return db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world_id,
        GameFederationDB.is_active == True,
    ).all()
