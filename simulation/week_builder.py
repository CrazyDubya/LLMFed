"""
Build a Week from a template: cards per day with show_type, travel_squad, prep_date.

Does not fill matches; that is done by MatchScheduler or anchor logic when running.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import List, Optional, Any, Dict

from models.calendar import Week, Card
from models.week_schedule import WeekTemplate, ShowType, ShowSlot
from simulation.travel_squad import get_travel_squad

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _slot_for_day(slots: List[ShowSlot], day_of_week: int) -> Optional[ShowSlot]:
    for s in slots:
        if s.day_of_week == day_of_week:
            return s
    return None


def build_week_from_template(
    db,
    federation_id: str,
    week_start_date: date,
    template: WeekTemplate,
    default_venue_id: Optional[str] = None,
    tv_name: str = "Weekly TV",
    house_name: str = "House Show",
    ppv_name: Optional[str] = None,
) -> Week:
    """
    Build a Week with one Card per slot that has a show (house/tv/ppv/dark).
    Each card gets card_date, show_type, prep_date (day before), travel_squad_ids.
    Matches are left empty; caller can fill via MatchScheduler.
    """
    week_id = str(uuid.uuid4())
    end_date = week_start_date + timedelta(days=6)
    cards: List[Card] = []

    for day in range(7):
        slot = _slot_for_day(template.slots, day)
        if not slot or slot.show_type == ShowType.OFF:
            continue
        card_date = week_start_date + timedelta(days=day)
        show_type = slot.show_type.value
        loop = getattr(slot, "loop", None)
        travel_squad_ids = get_travel_squad(
            db,
            federation_id,
            card_date,
            show_type,
            loop=loop,
            exclude_high_fatigue=True,
        )
        prep_date = card_date - timedelta(days=1)
        if show_type == "tv":
            name = f"{tv_name} ({DAY_NAMES[day]})"
        elif show_type == "ppv":
            name = ppv_name or f"PPV ({DAY_NAMES[day]})"
        else:
            name = f"{house_name} ({DAY_NAMES[day]})"
        card_id = str(uuid.uuid4())
        is_ppv = show_type == "ppv"
        cards.append(Card(
            card_id=card_id,
            federation_id=federation_id,
            name=name,
            card_date=card_date,
            week_id=week_id,
            venue_id=default_venue_id,
            show_type=show_type,
            prep_date=prep_date,
            travel_squad_ids=travel_squad_ids,
            is_ppv=is_ppv,
            matches=[],
        ))
    return Week(
        week_id=week_id,
        federation_id=federation_id,
        start_date=week_start_date,
        end_date=end_date,
        cards=cards,
    )


def fill_week_matches(db, week: Week) -> Week:
    """
    Fill matches for each card in the week using travel_squad_ids as participant pool.
    Uses MatchScheduler._create_optimal_match_card; falls back to get_available_at_date
    if travel_squad_ids is empty.
    """
    from models.calendar import Card, Match
    from core_engine.scheduling.match_scheduler import MatchScheduler
    from simulation.travel_squad import get_available_at_date
    from agent_service.wrestling_crud import get_storylines

    scheduler = MatchScheduler(lambda: db)
    for card in week.cards:
        participant_ids = card.travel_squad_ids or []
        if len(participant_ids) < 2 and card.card_date:
            participant_ids = get_available_at_date(db, card.federation_id, card.card_date, "participant")
        if len(participant_ids) < 2:
            continue
        active_storylines = [
            s for s in get_storylines(db, federation_id=card.federation_id, status="active", limit=5)
            if s and getattr(s, "participant_ids", None)
        ]
        matches = scheduler._create_optimal_match_card(
            participant_ids=participant_ids,
            federation_id=card.federation_id,
            title_id=None,
            active_storylines=active_storylines,
            db=db,
        )
        # Update match card_ids to this card
        for m in matches:
            m.card_id = card.card_id  # type: ignore
        card.matches = matches  # type: ignore
    return week
