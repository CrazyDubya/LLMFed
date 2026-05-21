"""
Travel squad: who is on which show. Roster pools (TV, house, PPV) and loop A/B.

Given federation, date, show_type, and optional loop (for house), returns
agent_ids that can be booked on that card (respects availability and fatigue).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import List, Optional, Any, Dict

from simulation.roster_timeline import get_available_at_date, get_tenure_mix_at_date

logger = logging.getLogger(__name__)

# Max squad size per show type (so we don't book everyone)
MAX_SQUAD_HOUSE = 14
MAX_SQUAD_TV = 22
MAX_SQUAD_PPV = 28


def _contract_type_for(db, agent_id: str, federation_id: str) -> Optional[str]:
    """Return contract_type for agent in federation, or None."""
    from models.db_models import ContractDB
    row = (
        db.query(ContractDB)
        .filter(
            ContractDB.agent_id == agent_id,
            ContractDB.federation_id == federation_id,
            ContractDB.status == "active",
        )
        .first()
    )
    return getattr(row, "contract_type", None) if row else None


def get_tv_roster(
    db,
    federation_id: str,
    as_of: date,
) -> List[str]:
    """
    Agents who appear on TV: full_time (and optionally rising/veteran tenure).
    Falls back to veteran+rising from tenure mix if contracts not populated.
    """
    available = get_available_at_date(db, federation_id, as_of, "participant")
    if not available:
        return []
    # Prefer contract: full_time = TV
    tv_ids = []
    for aid in available:
        ct = _contract_type_for(db, aid, federation_id)
        if ct in ("full_time", "developmental"):
            tv_ids.append(aid)
    if tv_ids:
        return tv_ids[:MAX_SQUAD_TV]
    # Fallback: tenure mix — TV = veteran + rising (most of roster)
    from models.world_anchor import WorldAnchor
    try:
        from models.db_models import WorldAnchorDB
        row = db.query(WorldAnchorDB).filter(WorldAnchorDB.federation_id == federation_id).first()
        anchor = None
        if row and getattr(row, "anchor_date", None):
            ad = row.anchor_date.date() if hasattr(row.anchor_date, "date") else row.anchor_date
            anchor = WorldAnchor(federation_id=federation_id, world_start_date=as_of, anchor_date=ad)
    except Exception:
        anchor = None
    mix = get_tenure_mix_at_date(db, federation_id, as_of, anchor)
    tv_ids = mix.get("veteran", []) + mix.get("rising", [])
    if not tv_ids:
        tv_ids = available[:MAX_SQUAD_TV]
    return tv_ids[:MAX_SQUAD_TV]


def get_house_roster(
    db,
    federation_id: str,
    as_of: date,
) -> List[str]:
    """
    Agents who work house shows: everyone not TV-only, or full roster if no contracts.
    Excludes ppv_appearance-only (they don't do house).
    """
    available = get_available_at_date(db, federation_id, as_of, "participant")
    if not available:
        return []
    house_ids = []
    for aid in available:
        ct = _contract_type_for(db, aid, federation_id)
        if ct == "ppv_appearance":
            continue
        house_ids.append(aid)
    if not house_ids:
        house_ids = list(available)
    return house_ids[:MAX_SQUAD_HOUSE * 2]  # Enough for two loops


def get_ppv_roster(
    db,
    federation_id: str,
    as_of: date,
) -> List[str]:
    """PPV roster = TV roster + ppv_appearance contracts."""
    tv = get_tv_roster(db, federation_id, as_of)
    available = get_available_at_date(db, federation_id, as_of, "participant")
    ppv_ids = list(tv)
    for aid in available:
        if aid in ppv_ids:
            continue
        ct = _contract_type_for(db, aid, federation_id)
        if ct in ("ppv_appearance", "legend"):
            ppv_ids.append(aid)
    return ppv_ids[:MAX_SQUAD_PPV]


def get_travel_squad(
    db,
    federation_id: str,
    card_date: date,
    show_type: str,
    loop: Optional[str] = None,
    max_size: Optional[int] = None,
    exclude_high_fatigue: bool = True,
) -> List[str]:
    """
    Return agent_ids for the travel squad for this card.
    show_type: house, tv, ppv, dark.
    loop: for house only, 'A' or 'B' — splits house roster so A and B alternate nights.
    """
    from core_engine.fatigue import get_fatigue, FATIGUE_THRESHOLD_REST

    if show_type == "tv":
        pool = get_tv_roster(db, federation_id, card_date)
        cap = max_size or MAX_SQUAD_TV
    elif show_type == "ppv":
        pool = get_ppv_roster(db, federation_id, card_date)
        cap = max_size or MAX_SQUAD_PPV
    elif show_type in ("house", "dark"):
        pool = get_house_roster(db, federation_id, card_date)
        cap = max_size or MAX_SQUAD_HOUSE
        if loop and pool:
            # Split into A and B: even index = A, odd = B (or by hash)
            pool_a = [p for i, p in enumerate(pool) if i % 2 == 0]
            pool_b = [p for i, p in enumerate(pool) if i % 2 == 1]
            pool = pool_a if loop.upper() == "A" else pool_b
    else:
        pool = get_available_at_date(db, federation_id, card_date, "participant")
        cap = max_size or MAX_SQUAD_HOUSE

    if exclude_high_fatigue:
        squad = []
        for aid in pool:
            if get_fatigue(db, aid, federation_id, card_date) < FATIGUE_THRESHOLD_REST:
                squad.append(aid)
            if len(squad) >= cap:
                break
        # If everyone is fatigued, take lowest fatigue
        if len(squad) < 2 and pool:
            with_fatigue = [(aid, get_fatigue(db, aid, federation_id, card_date)) for aid in pool]
            with_fatigue.sort(key=lambda x: x[1])
            squad = [aid for aid, _ in with_fatigue[:cap]]
        return squad[:cap]
    return pool[:cap]
