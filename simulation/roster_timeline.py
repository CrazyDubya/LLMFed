"""
Roster over time: who is on the roster at a given date, tenure mix, injuries, anchor-card composition.

Supports depth: veterans (there from early), rising (joined mid-build), newcomers (joined recently);
injuries and surprise returns; so the marquee show is not "everyone who was there day 1."
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Dict, Any

from models.roster import TenureTier
from models.world_anchor import WorldAnchor


def _to_date(d) -> date:
    if d is None:
        return None
    if hasattr(d, "date"):
        return d.date()
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    return d


def get_roster_at_date(
    db,
    federation_id: str,
    as_of: date,
    role_filter: Optional[str] = "participant",
) -> List[Dict[str, Any]]:
    """
    Agents active on roster at as_of: contract start <= as_of and (end_date is null or end_date >= as_of).
    Optionally filter by role (participant = wrestlers only).
    """
    from models.db_models import ContractDB, AgentDB
    from sqlalchemy import and_

    as_of_dt = datetime.combine(as_of, datetime.min.time())
    q = (
        db.query(AgentDB.agent_id, AgentDB.name, AgentDB.role, ContractDB.start_date, ContractDB.end_date)
        .join(ContractDB, ContractDB.agent_id == AgentDB.agent_id)
        .filter(
            ContractDB.federation_id == federation_id,
            ContractDB.status == "active",
            ContractDB.start_date <= as_of_dt,
            (ContractDB.end_date.is_(None)) | (ContractDB.end_date >= as_of_dt),
        )
    )
    if role_filter:
        q = q.filter(AgentDB.role == role_filter)
    rows = q.all()
    if rows:
        return [
            {
                "agent_id": r.agent_id,
                "name": r.name,
                "role": r.role,
                "join_date": _to_date(r.start_date),
                "end_date": _to_date(r.end_date),
            }
            for r in rows
        ]
    # Fallback: no contracts table populated; use agents by federation_id, join_date = created_at
    agents = db.query(AgentDB).filter(
        AgentDB.federation_id == federation_id,
        (role_filter is None) or (AgentDB.role == role_filter),
    ).all()
    return [
        {
            "agent_id": a.agent_id,
            "name": a.name,
            "role": a.role,
            "join_date": _to_date(getattr(a, "created_at", None)) or as_of,
            "end_date": None,
        }
        for a in agents
    ]


def get_available_at_date(
    db,
    federation_id: str,
    as_of: date,
    role_filter: Optional[str] = "participant",
) -> List[str]:
    """Roster at date minus anyone injured (out on as_of). Returns list of agent_ids."""
    from models.db_models import InjuryDB

    roster = get_roster_at_date(db, federation_id, as_of, role_filter)
    agent_ids = [r["agent_id"] for r in roster]
    injured = set()
    as_of_dt = datetime.combine(as_of, datetime.min.time())
    for row in db.query(InjuryDB).filter(
        InjuryDB.federation_id == federation_id,
        InjuryDB.agent_id.in_(agent_ids),
        InjuryDB.out_from <= as_of_dt,
    ).all():
        if row.out_until is None or row.out_until >= as_of_dt:
            injured.add(row.agent_id)
    return [aid for aid in agent_ids if aid not in injured]


def tenure_tier_for(
    join_date: date,
    reference_date: date,
    months_veteran: int = 12,
    months_rising_min: int = 12,
    months_rising_max: int = 24,
) -> TenureTier:
    """
    Compute tenure tier relative to reference_date (e.g. anchor date).
    - Veteran: joined >= months_rising_max before reference (e.g. 24+ months before anchor).
    - Rising: joined between months_rising_min and months_rising_max before reference (e.g. 12-24 months).
    - Newcomer: joined within months_rising_min of reference (e.g. last 12 months) or after.
    """
    try:
        delta_months = (reference_date.year - join_date.year) * 12 + (reference_date.month - join_date.month)
        if join_date.day > reference_date.day:
            delta_months -= 1
    except Exception:
        delta_months = 24
    if delta_months >= months_rising_max:
        return TenureTier.VETERAN
    if delta_months >= months_rising_min:
        return TenureTier.RISING
    return TenureTier.NEWCOMER


def get_tenure_mix_at_date(
    db,
    federation_id: str,
    as_of: date,
    anchor: Optional[WorldAnchor] = None,
) -> Dict[str, List[str]]:
    """Return { veteran: [ids], rising: [ids], newcomer: [ids] } for roster at as_of."""
    roster = get_roster_at_date(db, federation_id, as_of, "participant")
    reference = anchor.get_anchor_date() if anchor else as_of
    mix: Dict[str, List[str]] = {"veteran": [], "rising": [], "newcomer": []}
    for r in roster:
        join_date = r.get("join_date") or as_of
        if isinstance(join_date, datetime):
            join_date = join_date.date()
        tier = tenure_tier_for(join_date, reference)
        mix[tier.value].append(r["agent_id"])
    return mix


def get_anchor_card_composition(
    db,
    federation_id: str,
    anchor: WorldAnchor,
) -> Dict[str, Any]:
    """
    Composition vision for the marquee show: tenure mix, who's injured, who's just returned (surprise).
    Enables crafting a card with veterans, rising stars, newcomers—not everyone from day 1.
    """
    from models.db_models import InjuryDB

    anchor_date = anchor.get_anchor_date()
    roster = get_roster_at_date(db, federation_id, anchor_date, "participant")
    available = get_available_at_date(db, federation_id, anchor_date, "participant")
    tenure_mix = get_tenure_mix_at_date(db, federation_id, anchor_date, anchor)

    # Who is out (injured) on anchor night?
    out_ids = [r["agent_id"] for r in roster if r["agent_id"] not in available]

    # Who returned recently (e.g. out_until in last 30 days) or surprise return?
    just_returned = []
    for row in db.query(InjuryDB).filter(
        InjuryDB.federation_id == federation_id,
        InjuryDB.out_until.isnot(None),
        InjuryDB.out_until <= datetime.combine(anchor_date, datetime.min.time()),
    ).all():
        out_until = _to_date(row.out_until)
        if out_until:
            from datetime import timedelta
            if (anchor_date - out_until).days <= 30:
                just_returned.append({"agent_id": row.agent_id, "return_surprise": row.return_surprise})

    return {
        "anchor_date": anchor_date.isoformat(),
        "anchor_event": anchor.anchor_event_name,
        "roster_count": len(roster),
        "available_count": len(available),
        "tenure_mix": {k: len(v) for k, v in tenure_mix.items()},
        "tenure_agent_ids": tenure_mix,
        "out_injured": out_ids,
        "just_returned": just_returned,
    }
