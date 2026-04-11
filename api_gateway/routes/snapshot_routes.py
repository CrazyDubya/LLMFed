"""Snapshot / replay API routes.

Allows creating, listing, comparing, and restoring world-state snapshots
for "what-if" branching, undo, and replay features.
"""

import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent_service.database import get_db
from game_service.snapshot_service import (
    create_snapshot,
    restore_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game/snapshots", tags=["game-snapshots"])

# In-memory snapshot store (production would use a DB table)
_snapshots: dict = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SnapshotCreate(BaseModel):
    world_id: str
    description: str = ""
    snapshot_type: str = "manual"


class SnapshotMeta(BaseModel):
    snapshot_id: str
    world_id: str
    world_name: str = ""
    game_date: str = ""
    tick: int = 0
    description: str = ""
    snapshot_type: str = "manual"
    created_at: str = ""
    size_bytes: int = 0
    table_counts: dict = {}


class SnapshotRestore(BaseModel):
    snapshot_id: str
    create_new_world: bool = True


class SnapshotDiff(BaseModel):
    table: str
    snapshot_a_count: int
    snapshot_b_count: int
    difference: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=SnapshotMeta, status_code=201)
def api_create_snapshot(body: SnapshotCreate, db: Session = Depends(get_db)):
    """Create a snapshot of the current world state."""
    try:
        result = create_snapshot(
            db,
            world_id=body.world_id,
            description=body.description,
            snapshot_type=body.snapshot_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    meta = result["metadata"]
    sid = meta["snapshot_id"]
    _snapshots[sid] = result  # stash for later restore
    return SnapshotMeta(
        snapshot_id=sid,
        world_id=meta["world_id"],
        world_name=meta.get("world_name", ""),
        game_date=str(meta.get("game_date", "")),
        tick=meta.get("tick", 0),
        description=meta.get("description", ""),
        snapshot_type=meta.get("snapshot_type", "manual"),
        created_at=meta.get("created_at", ""),
        size_bytes=result.get("size_bytes", 0),
        table_counts=meta.get("table_counts", {}),
    )


@router.get("", response_model=List[SnapshotMeta])
def api_list_snapshots(world_id: Optional[str] = Query(None)):
    """List all saved snapshots, optionally filtered by world_id."""
    results = []
    for sid, snap in _snapshots.items():
        meta = snap["metadata"]
        if world_id and meta["world_id"] != world_id:
            continue
        results.append(SnapshotMeta(
            snapshot_id=sid,
            world_id=meta["world_id"],
            world_name=meta.get("world_name", ""),
            game_date=str(meta.get("game_date", "")),
            tick=meta.get("tick", 0),
            description=meta.get("description", ""),
            snapshot_type=meta.get("snapshot_type", "manual"),
            created_at=meta.get("created_at", ""),
            size_bytes=snap.get("size_bytes", 0),
            table_counts=meta.get("table_counts", {}),
        ))
    return results


@router.post("/restore")
def api_restore_snapshot(body: SnapshotRestore, db: Session = Depends(get_db)):
    """Restore a world from a previously saved snapshot."""
    snap = _snapshots.get(body.snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    result = restore_snapshot(
        db,
        snapshot_data=snap["data"],
        create_new_world=body.create_new_world,
    )
    return result


@router.get("/compare", response_model=List[SnapshotDiff])
def api_compare_snapshots(
    snapshot_a: str = Query(..., description="First snapshot ID"),
    snapshot_b: str = Query(..., description="Second snapshot ID"),
):
    """Compare table counts between two snapshots to visualize divergence."""
    a = _snapshots.get(snapshot_a)
    b = _snapshots.get(snapshot_b)
    if a is None or b is None:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")

    counts_a = a["metadata"].get("table_counts", {})
    counts_b = b["metadata"].get("table_counts", {})
    all_tables = sorted(set(counts_a) | set(counts_b))

    diffs = []
    for table in all_tables:
        ca = counts_a.get(table, 0)
        cb = counts_b.get(table, 0)
        diffs.append(SnapshotDiff(
            table=table,
            snapshot_a_count=ca,
            snapshot_b_count=cb,
            difference=cb - ca,
        ))
    return diffs
