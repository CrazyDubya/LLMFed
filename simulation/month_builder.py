"""
Build a Month with 4-5 weeks from templates. PPV week = last week (Sunday PPV).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Optional

from models.calendar import Month, Week, Season
from models.week_schedule import (
    WeekTemplate,
    default_standard_week_template,
    default_ppv_week_template,
)
from simulation.week_builder import build_week_from_template

logger = logging.getLogger(__name__)


def _first_monday_of_month(year: int, month: int) -> date:
    from datetime import timedelta
    first = date(year, month, 1)
    # Monday = 0; if first is Tuesday (1), we need to go back 1; if Sunday (6), back 6
    weekday = first.weekday()
    if weekday == 0:
        return first
    if weekday <= 6:
        return first - timedelta(days=weekday)
    return first


def _last_sunday_of_month(year: int, month: int) -> date:
    from calendar import monthrange
    last_day = monthrange(year, month)[1]
    d = date(year, month, last_day)
    from datetime import timedelta
    # Go back to Sunday
    weekday = d.weekday()  # Monday=0, Sunday=6
    # If last day is Sunday (6), no change. If Monday (0), go back 1, etc.
    days_back = (weekday + 1) % 7
    if days_back == 0:
        days_back = 7
    return d - timedelta(days=days_back)


def build_month(
    db,
    federation_id: str,
    year: int,
    month_number: int,
    standard_template: Optional[WeekTemplate] = None,
    ppv_template: Optional[WeekTemplate] = None,
    default_venue_id: Optional[str] = None,
    ppv_name: Optional[str] = None,
) -> Month:
    """
    Build a Month with 4-5 weeks. Weeks start Monday. Last week that contains
    the month's last Sunday is PPV week (uses ppv_template); others use standard_template.
    """
    from datetime import timedelta

    first_monday = _first_monday_of_month(year, month_number)
    last_sunday = _last_sunday_of_month(year, month_number)
    std_tpl = standard_template or default_standard_week_template(federation_id)
    ppv_tpl = ppv_template or default_ppv_week_template(federation_id)

    month_id = str(uuid.uuid4())
    start_date = date(year, month_number, 1)
    from calendar import monthrange
    end_date = date(year, month_number, monthrange(year, month_number)[1])
    weeks: list[Week] = []
    week_start = first_monday
    week_index = 0
    while week_start.month == month_number or (week_start <= end_date and week_index < 6):
        week_end = week_start + timedelta(days=6)
        is_ppv_week = last_sunday >= week_start and last_sunday <= week_end
        template = ppv_tpl if is_ppv_week else std_tpl
        week = build_week_from_template(
            db,
            federation_id,
            week_start,
            template,
            default_venue_id=default_venue_id,
            ppv_name=ppv_name,
        )
        week.month_id = month_id  # type: ignore
        weeks.append(week)
        week_start = week_end + timedelta(days=1)
        week_index += 1
        if week_index >= 5:
            break

    # Attach PPV to last week's Sunday card (PPV week)
    ppv_card = None
    for week in reversed(weeks):
        for c in reversed(week.cards or []):
            if getattr(c, "show_type", None) == "ppv" and c.card_date:
                from models.calendar import PPV
                ppv_card = PPV(
                    ppv_id=str(uuid.uuid4()),
                    card=c,
                    title=ppv_name or f"PPV {year}-{month_number:02d}",
                    month_id=month_id,
                )
                break
        if ppv_card:
            break

    return Month(
        month_id=month_id,
        federation_id=federation_id,
        season_id="",  # Caller can set
        year_number=year,
        month_number=month_number,
        start_date=start_date,
        end_date=end_date,
        weeks=weeks,
        ppv=ppv_card,
    )


def build_season(
    db,
    federation_id: str,
    year: int,
    month_numbers: Optional[list] = None,
    standard_template: Optional[WeekTemplate] = None,
    ppv_template: Optional[WeekTemplate] = None,
    default_venue_id: Optional[str] = None,
    ppv_names: Optional[dict] = None,
) -> Season:
    """
    Build a season (e.g. first 4 months of year). Default: months 1-4.
    Returns Season with months.
    """
    import uuid
    months_to_build = month_numbers or [1, 2, 3, 4]
    season_id = str(uuid.uuid4())
    months: list[Month] = []
    for i, mn in enumerate(months_to_build):
        ppv_name = None
        if ppv_names and mn in ppv_names:
            ppv_name = ppv_names[mn]
        month = build_month(
            db,
            federation_id,
            year,
            mn,
            standard_template=standard_template,
            ppv_template=ppv_template,
            default_venue_id=default_venue_id,
            ppv_name=ppv_name,
        )
        month.season_id = season_id  # type: ignore
        months.append(month)
    return Season(
        season_id=season_id,
        federation_id=federation_id,
        year_id="",
        season_number=1,
        months=months,
    )
