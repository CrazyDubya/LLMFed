"""CRUD for archive tiers and memory. Tier 9 immutables, recall()."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import (
    Tier9ImmutableDB,
    MatchResultDB,
    ReignDB,
    CardRevenueDB,
)
from models.memory import (
    ArchiveTier,
    ImmutableMatchRecord,
    ImmutableTitleChange,
    Tier9CardRecord,
)


def record_tier9_immutable(
    db: Session,
    federation_id: str,
    card_id: str,
    card_date: date,
    card_name: str,
    match_results: List[Dict[str, Any]],
    *,
    attendance: Optional[int] = None,
) -> None:
    """
    Append one Tier 9 immutable record for a card. Never update.
    Captures: card date, attendance, match card/results, title changes.
    """
    # Resolve attendance from CardRevenueDB if not passed
    if attendance is None:
        rev = db.query(CardRevenueDB).filter(
            CardRevenueDB.card_id == card_id
        ).first()
        attendance = rev.attendance if rev else 0

    match_records: List[Dict[str, Any]] = []
    title_changes: List[Dict[str, Any]] = []

    for mr in match_results:
        match_records.append({
            "match_id": mr.get("match_id", ""),
            "participant_ids": mr.get("participant_ids", []),
            "winner_id": mr.get("winner_id"),
            "stipulation": mr.get("stipulation", "StandardMatch"),
            "title_id": mr.get("title_id"),
            "title_changed": bool(mr.get("title_changed", False)),
        })
        if mr.get("title_changed") and mr.get("title_id") and mr.get("winner_id"):
            # Previous champion: reign that just ended for this title
            prev_reign = (
                db.query(ReignDB)
                .filter(
                    ReignDB.title_id == mr["title_id"],
                    ReignDB.end_date.isnot(None),
                )
                .order_by(ReignDB.end_date.desc())
                .first()
            )
            prev_champ = prev_reign.champion_id if prev_reign else None
            title_changes.append({
                "title_id": mr["title_id"],
                "new_champion_id": mr["winner_id"],
                "previous_champion_id": prev_champ,
            })

    card_dt = datetime.combine(card_date, datetime.min.time(), tzinfo=timezone.utc)
    row = Tier9ImmutableDB(
        federation_id=federation_id,
        card_id=card_id,
        card_date=card_dt,
        card_name=card_name,
        attendance=attendance or 0,
        match_records_json=match_records,
        title_changes_json=title_changes,
    )
    db.add(row)


def get_tier9_records(
    db: Session,
    federation_id: str,
    since: Optional[date] = None,
    until: Optional[date] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Return Tier 9 immutable records for a federation, optionally filtered by date."""
    q = db.query(Tier9ImmutableDB).filter(
        Tier9ImmutableDB.federation_id == federation_id
    )
    if since:
        since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
        q = q.filter(Tier9ImmutableDB.card_date >= since_dt)
    if until:
        until_dt = datetime.combine(until, datetime.max.time(), tzinfo=timezone.utc)
        q = q.filter(Tier9ImmutableDB.card_date <= until_dt)
    rows = q.order_by(Tier9ImmutableDB.card_date.desc()).limit(limit).all()
    return [
        {
            "card_id": r.card_id,
            "card_date": r.card_date.date() if hasattr(r.card_date, "date") else r.card_date,
            "card_name": r.card_name,
            "attendance": r.attendance,
            "match_records": r.match_records_json or [],
            "title_changes": r.title_changes_json or [],
        }
        for r in rows
    ]


def recall(
    db: Session,
    federation_id: str,
    tier: int = 9,
    *,
    actor_id: Optional[str] = None,
    since: Optional[date] = None,
    until: Optional[date] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Return bounded historical context for prompts.
    - tier=9: Tier 9 immutables (card dates, attendance, match results, title changes)
    - actor_id: if set, filter to records involving this agent (participant or champion)
    """
    if tier == 9:
        records = get_tier9_records(db, federation_id, since=since, until=until, limit=limit)
        if actor_id:
            filtered = []
            for r in records:
                involves = False
                for m in r.get("match_records", []):
                    if actor_id in (m.get("participant_ids") or []):
                        involves = True
                        break
                    if m.get("winner_id") == actor_id:
                        involves = True
                        break
                for tc in r.get("title_changes", []):
                    if actor_id in (tc.get("new_champion_id"), tc.get("previous_champion_id")):
                        involves = True
                        break
                if involves:
                    filtered.append(r)
            return filtered
        return records

    # Tier 0,1,2,3: use Tier 9 data with appropriate date window
    if tier == 0 and not since:
        since = date.today() - timedelta(days=28)
    elif tier == 1 and not since:
        since = date.today() - timedelta(days=365)
    records = get_tier9_records(db, federation_id, since=since, until=until, limit=limit)
    if actor_id:
        filtered = []
        for r in records:
            involves = False
            for m in r.get("match_records", []):
                if actor_id in (m.get("participant_ids") or []):
                    involves = True
                    break
                if m.get("winner_id") == actor_id:
                    involves = True
                    break
            for tc in r.get("title_changes", []):
                if actor_id in (tc.get("new_champion_id"), tc.get("previous_champion_id")):
                    involves = True
                    break
            if involves:
                filtered.append(r)
        return filtered
    return records


def recall_context_for_prompt(
    db: Session,
    federation_id: str,
    *,
    actor_id: Optional[str] = None,
    tiers: Optional[List[int]] = None,
) -> str:
    """
    Build a human-readable context string from recall for inclusion in prompts.
    """
    tiers = tiers or [9]
    parts = []
    for t in tiers:
        recs = recall(db, federation_id, tier=t, actor_id=actor_id, limit=50)
        if not recs:
            continue
        if t == 9:
            parts.append("**Tier 9 (Immutables — canonical records):**")
            for r in recs[:20]:
                cd = r.get("card_date", "")
                name = r.get("card_name", "?")
                att = r.get("attendance", 0)
                parts.append(f"  - {cd}: {name} (attendance {att})")
                for m in r.get("match_records", []):
                    pids = ", ".join(m.get("participant_ids", []))
                    w = m.get("winner_id", "?")
                    parts.append(f"    Match: {pids} → winner {w}")
                for tc in r.get("title_changes", []):
                    parts.append(f"    Title {tc.get('title_id')}: {tc.get('previous_champion_id')} → {tc.get('new_champion_id')}")
    return "\n".join(parts) if parts else ""
