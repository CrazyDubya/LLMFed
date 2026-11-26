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

from sqlalchemy import inspect, select
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
    rows = db.query(model_cls).filter(_world_scope(model_cls.__table__, world_id)).all()
    return [_serialize_row(r) for r in rows]


def _world_scope(table, world_id: str):
    """Scope child tables through their owning parent, not incidental links."""
    if "world_id" in table.c:
        return table.c.world_id == world_id
    parent_columns = {
        "wrestler_stats": "wrestler_id", "wrestler_history": "wrestler_id",
        "wrestler_goals": "wrestler_id", "wrestler_backstories": "wrestler_id",
        "gimmick_history": "wrestler_id", "career_highlights": "wrestler_id",
        "show_segments": "show_id", "match_participants": "match_id",
        "match_events": "match_id", "championship_history": "championship_id",
        "storyline_participants": "storyline_id", "stable_members": "stable_id",
    }
    if table.name not in parent_columns:
        raise ValueError(f"No world-scoping parent configured for table '{table.name}'")
    column = table.c[parent_columns[table.name]]
    parent = next(iter(column.foreign_keys)).column
    return column.in_(select(parent).where(_world_scope(parent.table, world_id)))


def create_snapshot(
    db: Session,
    world_id: str,
    description: str = "",
    snapshot_type: str = "manual",
) -> Dict[str, Any]:
    """Serialize the entire world state into a compressed JSON snapshot.

    Returns a dict with snapshot metadata and the compressed data blob.
    """
    from models.game_models import WorldDB

    world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
    if world is None:
        raise ValueError(f"World '{world_id}' not found")

    # Collect all related data
    tables_to_serialize = [cls for cls in _model_classes_by_table().values() if cls is not WorldDB]

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
        "table_counts": {
            name: len(rows) for name, rows in state["tables"].items()
        },
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


def _model_classes_by_table() -> Dict[str, Any]:
    """World-owned models in dependency order; exclude global users/legacy data."""
    from models.game_models import Base, WorldDB

    classes = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
    owned = {WorldDB.__tablename__}
    result = {}
    for table in Base.metadata.sorted_tables:
        if table.name in {"players", "player_actions"}:
            continue
        if (table.name in owned or "world_id" in table.c
                or any(fk.column.table.name in owned for fk in table.foreign_keys)):
            owned.add(table.name)
            result[table.name] = classes[table.name]
    return result


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
    from sqlalchemy import String as StringType, DateTime as DateTimeType

    raw = gzip.decompress(snapshot_data)
    state = json.loads(raw)

    world_data = dict(state["world"])
    old_world_id = world_data.get("id")
    tables = state.get("tables", {})
    model_by_table = _model_classes_by_table()
    unknown_tables = tables.keys() - model_by_table.keys()
    if unknown_tables:
        raise ValueError(f"Unknown snapshot tables: {sorted(unknown_tables)}")

    if create_new_world:
        new_world_id = str(uuid.uuid4())
        world_data["name"] = world_data.get("name", "Restored") + " (branch)"
    else:
        new_world_id = target_world_id or old_world_id

    # Build an old-id -> new-id map for every string-PK row (world included),
    # so foreign keys pointing to a remapped row can be rewritten too.
    # Integer-autoincrement PK tables (MatchParticipantDB, GameNarrativeLogDB,
    # WrestlerRelationshipDB) are left to the DB to assign — nothing else
    # references those rows by id.
    id_map: Dict[str, str] = {old_world_id: new_world_id}
    for table_name, rows in tables.items():
        model_cls = model_by_table.get(table_name)
        if model_cls is None:
            continue
        pk_is_string = isinstance(model_cls.id.type, StringType)
        for row in rows:
            if pk_is_string and "id" in row and row["id"]:
                id_map[row["id"]] = str(uuid.uuid4())

    def _remap(value):
        if isinstance(value, dict):
            return {_remap(key): _remap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_remap(item) for item in value]
        if isinstance(value, str) and value in id_map:
            return id_map[value]
        return value

    # Insert the (possibly-branched) world row first, then every table row,
    # rewriting ids/foreign keys and reviving ISO datetime strings back into
    # real datetime objects for DateTime-typed columns.
    world_data = {k: _remap(v) for k, v in world_data.items() if k != "id"}
    world_data["id"] = new_world_id
    player_links: List[tuple] = []
    if not create_new_world:
        player_links = _detach_player_links(db, new_world_id)
        _delete_existing_world_data(db, new_world_id, model_by_table)
    _upsert_world_row(db, model_by_table["worlds"], world_data, DateTimeType)
    db.flush()

    for table_name, model_cls in model_by_table.items():
        rows = tables.get(table_name, [])
        pk_is_string = isinstance(model_cls.id.type, StringType)
        for row in rows:
            row = {k: _remap(v) for k, v in row.items()}
            if not pk_is_string:
                row.pop("id", None)  # let autoincrement assign
            _insert_row(db, model_cls, row, DateTimeType)
        db.flush()

    if player_links:
        _reattach_player_links(db, player_links, tables, id_map)

    db.commit()

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


def _row_to_kwargs(model_cls, row: dict, datetime_type) -> dict:
    """Convert a plain (already-remapped) dict into ORM constructor kwargs,
    reviving ISO datetime strings back into real datetime objects for
    DateTime-typed columns."""
    mapper = inspect(model_cls)
    kwargs = {}
    for col in mapper.columns:
        if col.key not in row:
            continue
        val = row[col.key]
        if val is not None and isinstance(col.type, datetime_type) and isinstance(val, str):
            val = datetime.fromisoformat(val)
        kwargs[col.key] = val
    return kwargs


def _insert_row(db: Session, model_cls, row: dict, datetime_type) -> None:
    """Construct and stage a fresh ORM row from a plain (already-remapped) dict."""
    db.add(model_cls(**_row_to_kwargs(model_cls, row, datetime_type)))


def _upsert_world_row(db: Session, model_cls, row: dict, datetime_type) -> None:
    """Insert the restored world row, or update it in place if its id
    already exists (the overwrite path keeps the original world id, so a
    delete+insert here would collide with any already-loaded ORM object
    for that row still sitting in the session's identity map)."""
    kwargs = _row_to_kwargs(model_cls, row, datetime_type)
    existing = db.query(model_cls).filter(model_cls.id == kwargs["id"]).first()
    if existing:
        for key, val in kwargs.items():
            setattr(existing, key, val)
    else:
        db.add(model_cls(**kwargs))


def _detach_player_links(db: Session, world_id: str) -> List[tuple]:
    """Record and clear world players' federation/wrestler links before overwrite."""
    from models.core_models import PlayerDB

    players = db.query(PlayerDB).filter(PlayerDB.world_id == world_id).all()
    links = [(player, player.federation_id, player.wrestler_id) for player in players]
    for player in players:
        player.federation_id = None
        player.wrestler_id = None
    if players:
        db.flush()
    return links


def _reattach_player_links(
    db: Session,
    player_links: List[tuple],
    tables: Dict[str, List[Dict[str, Any]]],
    id_map: Dict[str, str],
) -> None:
    """Restore world players' federation/wrestler links to remapped snapshot rows."""
    fed_ids = {
        row["id"]: id_map[row["id"]]
        for row in tables.get("game_federations", [])
        if row.get("id") in id_map
    }
    wrestler_ids = {
        row["id"]: id_map[row["id"]]
        for row in tables.get("game_wrestlers", [])
        if row.get("id") in id_map
    }
    for player, old_fed_id, old_wrestler_id in player_links:
        player.federation_id = fed_ids.get(old_fed_id) if old_fed_id else None
        player.wrestler_id = wrestler_ids.get(old_wrestler_id) if old_wrestler_id else None
    db.flush()


def _delete_existing_world_data(db: Session, world_id: str, model_by_table: dict) -> None:
    """Clear out a world's child-table rows before overwriting it in place.

    The world row itself is left alone here — see _upsert_world_row, which
    updates it rather than deleting and recreating it.
    """
    from models.core_models import WorldDB

    for model_cls in reversed(list(model_by_table.values())):
        if model_cls is WorldDB:
            continue
        db.query(model_cls).filter(_world_scope(model_cls.__table__, world_id)).delete(synchronize_session=False)
    db.flush()


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
