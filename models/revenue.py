"""
Revenue: gate, PPV, concessions (from world_bubbles).

- Gate: attendance * avg_ticket_price
- PPV: buys * price_per_buy (when is_ppv and ppv_capable)
- Concessions: attendance * per_capita * house_cut (when concessions_available)
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


# Default fill rates by show type (attendance = capacity * fill_rate)
FILL_RATE_BY_SHOW_TYPE: Dict[str, float] = {
    "house": 0.55,
    "tv": 0.75,
    "ppv": 0.90,
    "dark": 0.40,
}


# Base prices (simplified; can be overridden per venue/federation)
DEFAULT_AVG_TICKET_PRICE = 50
DEFAULT_PPV_PRICE_PER_BUY = 50
DEFAULT_PPV_BASE_BUYS = 15000
DEFAULT_CONCESSION_PER_CAP = 5
DEFAULT_HOUSE_CUT_CONCESSION = 0.30


class RevenueResult(BaseModel):
    """Revenue breakdown for a card."""
    card_id: str = Field(description="Card this revenue is for")
    gate_revenue: float = Field(default=0, description="Ticket sales")
    ppv_revenue: float = Field(default=0, description="PPV buys (when applicable)")
    concession_revenue: float = Field(default=0, description="House cut of concessions")
    attendance: int = Field(default=0, description="Estimated attendance")
    total_revenue: float = Field(default=0, description="Sum of gate + ppv + concession")
    metadata: Dict[str, Any] = Field(default_factory=dict)


def compute_card_revenue(
    card_id: str,
    capacity: int,
    show_type: Optional[str] = None,
    is_ppv: bool = False,
    ppv_capable: bool = False,
    concessions_available: bool = True,
    *,
    fill_rate: Optional[float] = None,
    avg_ticket_price: float = DEFAULT_AVG_TICKET_PRICE,
    ppv_price: float = DEFAULT_PPV_PRICE_PER_BUY,
    ppv_buys: Optional[int] = None,
    concession_per_cap: float = DEFAULT_CONCESSION_PER_CAP,
    house_cut: float = DEFAULT_HOUSE_CUT_CONCESSION,
) -> RevenueResult:
    """
    Compute revenue for a card at a venue.

    Gate = capacity * fill_rate * avg_ticket_price
    PPV = ppv_buys * ppv_price (only when is_ppv and ppv_capable)
    Concessions = attendance * concession_per_cap * house_cut (when concessions_available)
    """
    st = (show_type or "tv").lower()
    rate = fill_rate if fill_rate is not None else FILL_RATE_BY_SHOW_TYPE.get(st, 0.70)
    attendance = int(capacity * rate)
    gate = attendance * avg_ticket_price
    ppv = 0.0
    if is_ppv and ppv_capable:
        buys = ppv_buys if ppv_buys is not None else DEFAULT_PPV_BASE_BUYS
        ppv = buys * ppv_price
    conc = 0.0
    if concessions_available and attendance > 0:
        conc = attendance * concession_per_cap * house_cut
    total = gate + ppv + conc
    return RevenueResult(
        card_id=card_id,
        gate_revenue=round(gate, 2),
        ppv_revenue=round(ppv, 2),
        concession_revenue=round(conc, 2),
        attendance=attendance,
        total_revenue=round(total, 2),
        metadata={
            "fill_rate": rate,
            "show_type": st,
            "capacity": capacity,
        },
    )
