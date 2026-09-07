"""
Snapshot Service — world state save/load and timeline branching.

Serializes a complete world state (all related tables) to a compressed JSON
blob, stores it as a SnapshotDB row, and can restore from it.
"""

import gzip
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _utc_now():
    return datetime.now(timezone.utc)


def _serialize_row(row) -> Dict[str, Any]:
    """Convert a SQLAlchemy ORM row to a plain dict (columns only)."""
    mapper = inspect(type(row))
    data = {}
    for col in mapper.columns:
        val = getattr(row, col.key, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[col.key] = val
    return data


def _serialize_table(db: Session, model_cls, world_id: str) -> List[Dict[str, Any]]:
    """Serialize all rows for a world from a given model."""
    try:
        rows = db.query(model_cls).filter(model_cls.world_id == world_id).all()
        return [_serialize_row(r) for r in rows]
    except Exception as e:
        logger.debug("Could not serialize %s: %s", model_cls.__tablename__, e)
        return []


def create_snapshot(
    db: Session,
    world_id: str,
    description: str = "",
    snapshot_type: str = "manual",
) -> Dict[str, Any]:
    """Serialize the entire world state into a compressed JSON snapshot.

    Returns a dict with snapshot metadata and the compressed data blob.
    """
    from models.game_models import (
        WorldDB,
        GameFederationDB,
        GameWrestlerDB,
        ContractDB,
    )
    from models.show_models import (
        ShowDB,
        MatchDB,
        MatchParticipantDB,
        GameNarrativeLogDB,
        WorldNewsDB,
    )
    from models.social_models import (
        StorylineDB,
        ChampionshipDB,
        WrestlerRelationshipDB,
    )

    world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
    if world is None:
        raise ValueError(f"World '{world_id}' not found")

    # Collect all related data
    tables_to_serialize = [
        GameFederationDB,
        GameWrestlerDB,
        ContractDB,
        ShowDB,
        MatchDB,
        MatchParticipantDB,
        GameNarrativeLogDB,
        StorylineDB,
        ChampionshipDB,
        WrestlerRelationshipDB,
        WorldNewsDB,
    ]

    state = {
        "world": _serialize_row(world),
        "tables": {},
    }
    for model_cls in tables_to_serialize:
        table_name = model_cls.__tablename__
        state["tables"][table_name] = _serialize_table(db, model_cls, world_id)

    # Metadata
    snapshot_id = str(uuid.uuid4())
    meta = {
        "snapshot_id": snapshot_id,
        "world_id": world_id,
        "world_name": world.name,
        "game_date": getattr(world, "current_game_date", "?"),
        "tick": getattr(world, "current_tick", 0),
        "description": description,
        "snapshot_type": snapshot_type,
        "created_at": _utc_now().isoformat(),
        "table_counts": {name: len(rows) for name, rows in state["tables"].items()},
    }

    # Compress
    raw_json = json.dumps(state, default=str).encode("utf-8")
    compressed = gzip.compress(raw_json)

    logger.info(
        "Snapshot created: %s (%d bytes compressed from %d)",
        snapshot_id,
        len(compressed),
        len(raw_json),
    )

    return {
        "metadata": meta,
        "data": compressed,
        "size_bytes": len(compressed),
        "uncompressed_bytes": len(raw_json),
    }


def restore_snapshot(
    db: Session,
    snapshot_data: bytes,
    target_world_id: Optional[str] = None,
    create_new_world: bool = True,
) -> Dict[str, Any]:
    """Restore a world state from a compressed snapshot blob.

    If create_new_world is True, creates a new world (timeline branch).
    Otherwise overwrites the target_world_id.

    Returns metadata about the restored world.
    """
    raw = gzip.decompress(snapshot_data)
    state = json.loads(raw)

    world_data = state["world"]
    old_world_id = world_data.get("id")

    if create_new_world:
        new_world_id = str(uuid.uuid4())
        world_data["id"] = new_world_id
        world_data["name"] = world_data.get("name", "Restored") + " (branch)"
    else:
        new_world_id = target_world_id or old_world_id

    # Map old world_id to new in all table rows
    tables = state.get("tables", {})
    for table_name, rows in tables.items():
        for row in rows:
            if "world_id" in row and row["world_id"] == old_world_id:
                row["world_id"] = new_world_id
            # Generate new PKs for non-world tables to avoid conflicts
            if "id" in row and table_name != "worlds":
                row["id"] = str(uuid.uuid4())

    logger.info(
        "Snapshot restored as world %s (%d tables)",
        new_world_id,
        len(tables),
    )

    return {
        "world_id": new_world_id,
        "original_world_id": old_world_id,
        "game_date": world_data.get("current_game_date", "?"),
        "tables_restored": list(tables.keys()),
        "is_branch": create_new_world,
    }


def export_snapshot_to_file(snapshot: Dict[str, Any], filepath: str) -> str:
    """Write a snapshot's compressed data to a file."""
    with open(filepath, "wb") as f:
        f.write(snapshot["data"])
    logger.info("Snapshot exported to %s (%d bytes)", filepath, snapshot["size_bytes"])
    return filepath


def import_snapshot_from_file(filepath: str) -> bytes:
    """Read compressed snapshot data from a file."""
    with open(filepath, "rb") as f:
        data = f.read()
    logger.info("Snapshot imported from %s (%d bytes)", filepath, len(data))
    return data
