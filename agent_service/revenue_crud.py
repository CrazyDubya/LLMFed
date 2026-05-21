"""CRUD for card revenue (gate, PPV, concessions)."""

from __future__ import annotations

from typing import Optional

from models.db_models import CardRevenueDB
from models.revenue import RevenueResult, compute_card_revenue


def persist_card_revenue(db, result: RevenueResult, federation_id: str) -> int:
    """Persist RevenueResult to CardRevenueDB. Returns row id."""
    row = CardRevenueDB(
        card_id=result.card_id,
        federation_id=federation_id,
        gate_revenue=int(result.gate_revenue),
        ppv_revenue=int(result.ppv_revenue),
        concession_revenue=int(result.concession_revenue),
        attendance=result.attendance,
        total_revenue=int(result.total_revenue),
        metadata_json=result.metadata,
    )
    db.add(row)
    return row.id


def compute_and_persist_card_revenue(
    db,
    card_id: str,
    federation_id: str,
    venue_row,
    show_type: Optional[str] = None,
    is_ppv: bool = False,
) -> RevenueResult:
    """Compute revenue for a card and persist. Returns RevenueResult."""
    capacity = getattr(venue_row, "capacity", 5000) or 5000
    ppv_capable = getattr(venue_row, "ppv_capable", False)
    concessions = getattr(venue_row, "concessions_available", True)
    result = compute_card_revenue(
        card_id=card_id,
        capacity=capacity,
        show_type=show_type,
        is_ppv=is_ppv,
        ppv_capable=ppv_capable,
        concessions_available=concessions,
    )
    persist_card_revenue(db, result, federation_id)
    return result
