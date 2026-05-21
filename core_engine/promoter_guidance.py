"""
Promoter guidance: prompts and hints for building toward the anchor card.

When in build_up phase, the promoter gets guidance so they can plan cards
toward the 2-year marquee show. Conceptual targets, stakes, and pacing.
Includes month/season context for conducting cards through Week → Month → Season → Annual.
"""

from __future__ import annotations

from datetime import date
from calendar import monthrange
from typing import Dict, Any, Optional


def _last_sunday_of_month(year: int, month: int) -> date:
    last_day = monthrange(year, month)[1]
    d = date(year, month, last_day)
    from datetime import timedelta
    weekday = d.weekday()
    days_back = (weekday + 1) % 7
    if days_back == 0:
        days_back = 7
    return d - timedelta(days=days_back)


def build_month_context(card_date: date) -> Dict[str, Any]:
    """
    Build month-level context for promoter: where we are in the month,
    build-up vs PPV week vs fallout.
    """
    year, month = card_date.year, card_date.month
    last_sun = _last_sunday_of_month(year, month)
    from datetime import timedelta
    ppv_week_start = last_sun - timedelta(days=6)  # Monday of PPV week
    ppv_week_end = last_sun
    month_start = date(year, month, 1)
    days_in = (card_date - month_start).days
    week_index = (days_in // 7) + 1
    is_ppv_week = ppv_week_start <= card_date <= ppv_week_end
    if card_date < ppv_week_start:
        phase = "build_up_to_ppv"
    elif is_ppv_week:
        phase = "ppv_week"
    else:
        phase = "post_ppv_fallout"
    return {
        "month_week_index": week_index,
        "is_ppv_week": is_ppv_week,
        "phase": phase,
        "ppv_week_sunday": str(last_sun),
    }


def build_season_context(card_date: date, season_months: int = 4) -> Dict[str, Any]:
    """Build season-level context (season = first N months of year for simplicity)."""
    month_index = card_date.month
    return {
        "season_month_index": month_index,
        "year": card_date.year,
    }


def build_promoter_guidance(
    world_anchor: Dict[str, Any],
    conceptual_target: Optional[Dict[str, Any]] = None,
    composition: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build promoter guidance text for LLM context.

    Used when phase is build_up or anchor: remind promoter of stakes,
    target main event, planned storylines, tenure mix.
    """
    parts = []
    phase = world_anchor.get("phase", "build_up")
    anchor_event = world_anchor.get("anchor_event", "Grandstand")
    weeks_until = world_anchor.get("weeks_until_marquee")
    weeks_since = world_anchor.get("weeks_since_marquee")

    parts.append(f"**Anchor show**: {anchor_event} (marquee annual event).")
    if phase == "build_up" and weeks_until is not None:
        if weeks_until > 0:
            parts.append(f"We are {weeks_until} weeks from {anchor_event}. Build toward it: roster, storylines, heat, title picture.")
        else:
            parts.append(f"We are in the build-up phase. Plan cards that develop toward {anchor_event}.")
    elif phase == "anchor":
        parts.append(f"Tonight is {anchor_event}. Main event, title matches, and storyline payoffs matter.")
    elif phase == "aftermath" and weeks_since is not None:
        parts.append(f"We are {weeks_since} weeks past {anchor_event}. New champions, new feuds, new arcs.")

    if conceptual_target:
        main = conceptual_target.get("main_event_target")
        if main and isinstance(main, dict):
            ids = main.get("participant_ids", [])
            if ids:
                parts.append(f"**Target main event** (conceptual): build toward {len(ids)} participants for the marquee.")
        title_matches = conceptual_target.get("title_matches_target", [])
        if title_matches:
            parts.append(f"**Target title matches** (conceptual): {len(title_matches)} title bouts planned for {anchor_event}.")
        payoffs = conceptual_target.get("planned_storyline_payoffs", [])
        if payoffs:
            parts.append(f"**Planned storyline payoffs** at anchor: {len(payoffs)} storylines should climax at {anchor_event}.")

    if composition:
        tenure = composition.get("tenure_mix", {})
        if tenure:
            v = tenure.get("veteran", 0)
            r = tenure.get("rising", 0)
            n = tenure.get("newcomer", 0)
            parts.append(f"**Tenure mix** (veterans/rising/newcomer): {v}/{r}/{n}. Use veterans for main event, rising for title matches, newcomers for opener.")
        out = composition.get("out_injured", [])
        if out:
            parts.append(f"**Out injured** on anchor night: {len(out)} talent. Plan alternatives.")
        just_ret = composition.get("just_returned", [])
        if just_ret:
            surprises = [j for j in just_ret if j.get("return_surprise")]
            if surprises:
                parts.append(f"**Surprise returns** possible: {len(surprises)} talent may return unadvertised.")

    return "\n".join(parts) if parts else ""


def build_anchor_stakes_hint(world_anchor: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact hint dict for promoter context."""
    return {
        "anchor_event": world_anchor.get("anchor_event", "Grandstand"),
        "phase": world_anchor.get("phase", "build_up"),
        "weeks_until_marquee": world_anchor.get("weeks_until_marquee"),
        "weeks_since_marquee": world_anchor.get("weeks_since_marquee"),
        "years_from_anchor": world_anchor.get("years_from_anchor"),
    }
