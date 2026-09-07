"""
PPV Calendar Service — manages the yearly PPV schedule and build cycles.

PPVs are the destination; weekly TV exists to build toward them.
Federations get a calendar based on prestige:
  - High prestige (70+): 8-12 PPVs/year
  - Mid prestige (40-69): 4-6 PPVs/year
  - Low prestige (<40): 2-3 PPVs/year

Each PPV has:
  - A name, theme, and scheduled date
  - One designated "crown jewel" (the WrestleMania equivalent)
  - Penciled-in matches that become ink as the build progresses
  - A build cycle window (typically 4-6 weeks of weekly TV before the PPV)
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from models.game_models import (
    PPVEventDB,
    BookingVisionDB,
    GameFederationDB,
    WrestlerPushDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PPV name pools by theme
# ---------------------------------------------------------------------------

PPV_NAMES_CROWN_JEWEL = [
    "WrestleRama",
    "Clash of Champions",
    "FinalDestination",
    "The Grand Spectacle",
    "Championship Showcase",
    "Legends Night",
    "SuperClash",
    "The Main Event",
    "GloryBound",
]

PPV_NAMES_GENERAL = [
    "Bad Blood",
    "No Mercy",
    "Backlash",
    "Vengeance",
    "Breaking Point",
    "Judgment Day",
    "Battleground",
    "Collision Course",
    "Showdown",
    "Payback",
    "No Way Out",
    "Lockdown",
    "Overdrive",
    "Breakdown",
    "King of the Ring",
    "Night of Champions",
    "Street Fight",
    "Extreme Rules",
    "Money in the Bank",
    "Steel Cage Chaos",
    "Last Stand",
    "Uprising",
]

PPV_THEMES = [
    "grudge_matches",  # Blowoff feuds
    "tournament",  # King of the Ring style
    "showcase",  # Best matches possible
    "extreme",  # Gimmick matches
    "championship",  # Every title defended
    "grudge_matches",  # More feuds (weighted higher)
]


# ---------------------------------------------------------------------------
# Calendar generation
# ---------------------------------------------------------------------------


def generate_ppv_calendar(
    db: Session,
    federation: GameFederationDB,
    year_start_date: str,
) -> List[PPVEventDB]:
    """Generate a full year of PPV events for a federation.

    Number of PPVs scales with prestige:
      70+: 8-12
      40-69: 4-6
      <40: 2-3

    Returns created PPVEventDB records.
    """
    prestige = federation.prestige or 50

    if prestige >= 70:
        num_ppvs = random.randint(8, 12)
    elif prestige >= 40:
        num_ppvs = random.randint(4, 6)
    else:
        num_ppvs = random.randint(2, 3)

    # Spread PPVs roughly evenly across the year
    start = datetime.strptime(year_start_date, "%Y-%m-%d")
    year_days = 365
    spacing = year_days // max(num_ppvs, 1)

    # Pick PPV names (no duplicates)
    crown_jewel_name = random.choice(PPV_NAMES_CROWN_JEWEL)
    available_names = list(PPV_NAMES_GENERAL)
    random.shuffle(available_names)
    ppv_names = available_names[: num_ppvs - 1]  # Reserve slot for crown jewel

    # Crown jewel goes near end of year (last quarter)
    crown_jewel_month = random.randint(10, 12)

    ppvs = []
    name_idx = 0

    for i in range(num_ppvs):
        # Calculate date
        ppv_date = start + timedelta(days=spacing * i + random.randint(-7, 7))
        date_str = ppv_date.strftime("%Y-%m-%d")

        # Crown jewel is the last or second-to-last PPV
        if i == num_ppvs - 1:
            name = crown_jewel_name
            is_crown_jewel = True
            theme = "showcase"
            # Crown jewel gets biggest venue
            capacity = (
                random.randint(15000, 50000)
                if prestige >= 60
                else random.randint(8000, 20000)
            )
        else:
            name = (
                ppv_names[name_idx]
                if name_idx < len(ppv_names)
                else f"Special Event {i + 1}"
            )
            name_idx += 1
            is_crown_jewel = False
            theme = random.choice(PPV_THEMES)
            capacity = (
                random.randint(5000, 20000)
                if prestige >= 50
                else random.randint(2000, 8000)
            )

        ppv = PPVEventDB(
            world_id=federation.world_id,
            federation_id=federation.id,
            name=f"{federation.short_name or federation.name} {name}",
            theme=theme,
            scheduled_date=date_str,
            is_crown_jewel=is_crown_jewel,
            capacity=capacity,
            venue=f"{federation.home_region} Arena"
            if not is_crown_jewel
            else f"{federation.home_region} Stadium",
            planned_main_event={},
            planned_matches=[],
        )
        db.add(ppv)
        ppvs.append(ppv)

    db.flush()
    logger.info(
        "Generated %d PPV events for %s (crown jewel: %s)",
        len(ppvs),
        federation.short_name or federation.name,
        crown_jewel_name,
    )
    return ppvs


# ---------------------------------------------------------------------------
# Build cycle management
# ---------------------------------------------------------------------------


def get_next_ppv(
    db: Session, federation_id: str, current_date: str
) -> Optional[PPVEventDB]:
    """Get the next upcoming PPV for a federation."""
    return (
        db.query(PPVEventDB)
        .filter(
            PPVEventDB.federation_id == federation_id,
            PPVEventDB.scheduled_date > current_date,
            PPVEventDB.is_completed == False,
        )
        .order_by(PPVEventDB.scheduled_date)
        .first()
    )


def get_weeks_until_ppv(current_date: str, ppv_date: str) -> int:
    """Calculate weeks between two dates."""
    current = datetime.strptime(current_date, "%Y-%m-%d")
    ppv = datetime.strptime(ppv_date, "%Y-%m-%d")
    delta = ppv - current
    return max(0, delta.days // 7)


def is_build_window(current_date: str, ppv_date: str) -> bool:
    """Check if we're in the build window (6 weeks or fewer) for a PPV."""
    return get_weeks_until_ppv(current_date, ppv_date) <= 6


def is_go_home_week(current_date: str, ppv_date: str) -> bool:
    """Check if this is the final week before a PPV (go-home show)."""
    return get_weeks_until_ppv(current_date, ppv_date) <= 1


# ---------------------------------------------------------------------------
# PPV card planning
# ---------------------------------------------------------------------------


def pencil_in_ppv_match(
    db: Session,
    ppv: PPVEventDB,
    wrestler_ids: List[str],
    match_type: str = "singles",
    title_id: str = None,
    storyline_id: str = None,
    is_main_event: bool = False,
):
    """Pencil in a match for a PPV card."""
    match_plan = {
        "wrestler_ids": wrestler_ids,
        "match_type": match_type,
        "title_id": title_id,
        "storyline_id": storyline_id,
        "status": "penciled",
    }

    if is_main_event:
        ppv.planned_main_event = match_plan
    else:
        matches = list(ppv.planned_matches or [])
        matches.append(match_plan)
        ppv.planned_matches = matches

    db.add(ppv)


def ink_ppv_match(ppv: PPVEventDB, wrestler_ids: List[str]):
    """Convert a penciled match to ink (publicly announced/building toward it)."""
    # Check main event
    me = ppv.planned_main_event or {}
    if set(me.get("wrestler_ids", [])) == set(wrestler_ids):
        me["status"] = "ink"
        ppv.planned_main_event = me
        return

    # Check undercard
    matches = list(ppv.planned_matches or [])
    for m in matches:
        if set(m.get("wrestler_ids", [])) == set(wrestler_ids):
            m["status"] = "ink"
            break
    ppv.planned_matches = matches


def plan_ppv_card_from_vision(
    db: Session,
    ppv: PPVEventDB,
    vision: BookingVisionDB,
):
    """Auto-plan a PPV card from the booking vision.

    Uses title pipelines, push tiers, and planned storylines to build
    a full card. Called when entering the build window for a PPV.
    """
    # Main event: title match with top challenger from pipeline
    pipelines = vision.title_pipelines or {}
    main_event_set = False

    for champ_id, pipeline in pipelines.items():
        holder = pipeline.get("current_holder")
        challengers = pipeline.get("next_challengers", [])

        if holder and challengers:
            challenger = challengers[0]
            pencil_in_ppv_match(
                db,
                ppv,
                wrestler_ids=[holder, challenger],
                match_type="singles",
                title_id=champ_id,
                is_main_event=not main_event_set,
            )
            main_event_set = True

    # Add matches from planned storylines at climax
    planned_sls = vision.planned_storylines or []
    for sl in planned_sls:
        if sl.get("status") == "cancelled":
            continue
        wrestler_ids = sl.get("wrestler_ids", [])
        if len(wrestler_ids) >= 2:
            pencil_in_ppv_match(
                db,
                ppv,
                wrestler_ids=wrestler_ids,
                match_type="singles",
                storyline_id=sl.get("storyline_id"),
            )

    # Fill remaining card with upper midcard matches
    used = set()
    for m in ppv.planned_matches or []:
        used.update(m.get("wrestler_ids", []))
    me = ppv.planned_main_event or {}
    used.update(me.get("wrestler_ids", []))

    # Get upper midcard and midcard wrestlers for undercard
    upper = (
        db.query(WrestlerPushDB)
        .filter(
            WrestlerPushDB.federation_id == ppv.federation_id,
            WrestlerPushDB.push_tier.in_(["upper_midcard", "midcard"]),
        )
        .all()
    )

    available = [p.wrestler_id for p in upper if p.wrestler_id not in used]
    random.shuffle(available)

    # Add 2-3 more matches
    for i in range(0, min(len(available) - 1, 6), 2):
        pencil_in_ppv_match(
            db,
            ppv,
            wrestler_ids=[available[i], available[i + 1]],
            match_type="singles",
        )

    db.add(ppv)
    db.flush()
    logger.info(
        "Planned card for PPV %s: %d matches",
        ppv.name,
        len(ppv.planned_matches or []) + (1 if ppv.planned_main_event else 0),
    )


# ---------------------------------------------------------------------------
# Annual rollover
# ---------------------------------------------------------------------------


def rollover_ppv_calendar(
    db: Session,
    federation: GameFederationDB,
    new_year_start: str,
):
    """Generate next year's PPV calendar. Called when current year's events are done."""
    # Check if next year's PPVs already exist
    next_year = datetime.strptime(new_year_start, "%Y-%m-%d").year
    existing = (
        db.query(PPVEventDB)
        .filter(
            PPVEventDB.federation_id == federation.id,
            PPVEventDB.scheduled_date >= new_year_start,
        )
        .count()
    )

    if existing > 0:
        return  # Already have next year planned

    return generate_ppv_calendar(db, federation, new_year_start)
