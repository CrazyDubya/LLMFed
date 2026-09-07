"""
Backstage Politics & Locker Room Power Service — Group 3.

Extracted from wrestler_lifecycle_service.py.
"""

import logging
import random
from typing import List, Optional

from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB,
    WrestlerStatsDB,
    GameFederationDB,
    ContractDB,
)
from game_service.lifecycle_constants import (
    MAX_STAT_CAP,
    TENURE_MULTIPLIER,
    TENURE_CAP,
    POPULARITY_DIVISOR,
    LEADER_POLITICS,
    LEADER_POP,
    RESPECTED_POLITICS,
    RESPECTED_WORK_ETHIC,
    DISLIKED_POLITICS,
    DISLIKED_WORK_ETHIC,
    TOXIC_POLITICS,
    TOXIC_WORK_ETHIC,
    LEADER_MORALE_BASELINE,
    LEADER_MORALE_DIVISOR,
    CREATIVE_CONTROL_THRESHOLD,
    CREATIVE_CONTROL_FINISHES,
    CREATIVE_CONTROL_ALTERNATIVES,
    CREATIVE_CONTROL_DIVISOR,
)

logger = logging.getLogger(__name__)


def _get_wrestler_stats(db: Session, wrestler_id: str) -> Optional[WrestlerStatsDB]:
    """Fetch a wrestler's stats row (returns None if missing)."""
    return (
        db.query(WrestlerStatsDB)
        .filter(WrestlerStatsDB.wrestler_id == wrestler_id)
        .first()
    )


def _active_roster_ids(db: Session, federation_id: str) -> List[str]:
    """Return wrestler IDs with active contracts in a federation."""
    contracts = (
        db.query(ContractDB)
        .filter(
            ContractDB.federation_id == federation_id,
            ContractDB.status == "active",
        )
        .all()
    )
    return [c.wrestler_id for c in contracts]


def _classify_locker_room_standing(politics: int, work: int, popularity: int) -> str:
    """Determine locker room standing from stats."""
    if politics > LEADER_POLITICS and popularity > LEADER_POP:
        return "leader"
    if politics > RESPECTED_POLITICS and work > RESPECTED_WORK_ETHIC:
        return "respected"
    if politics < DISLIKED_POLITICS and work < DISLIKED_WORK_ETHIC:
        return "disliked"
    if politics > TOXIC_POLITICS and work < TOXIC_WORK_ETHIC:
        return "toxic"
    return "neutral"


def update_locker_room_dynamics(
    db: Session, federation: GameFederationDB, game_date: str
):
    """Weekly locker room standing/influence calculation and morale contagion."""
    wrestler_ids = _active_roster_ids(db, federation.id)
    if not wrestler_ids:
        return

    wrestlers = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.id.in_(wrestler_ids),
            GameWrestlerDB.is_active == True,
        )
        .all()
    )

    leaders = []
    toxic_count = 0

    for w in wrestlers:
        stats = _get_wrestler_stats(db, w.id)
        if not stats:
            continue

        politics = stats.backstage_politics or 50
        tenure = min((w.experience_years or 0) * TENURE_MULTIPLIER, TENURE_CAP)
        pop = (w.popularity or 50) // POPULARITY_DIVISOR
        w.creative_influence = min(MAX_STAT_CAP, politics + tenure + pop)

        work = stats.work_ethic or 50
        standing = _classify_locker_room_standing(politics, work, w.popularity or 0)
        w.locker_room_standing = standing

        if standing == "leader":
            leaders.append(w)
        elif standing == "toxic":
            toxic_count += 1

    # Morale contagion
    if leaders:
        avg_leader_morale = sum(l.morale or 50 for l in leaders) / len(leaders)
        shift = int(
            (avg_leader_morale - LEADER_MORALE_BASELINE) / LEADER_MORALE_DIVISOR
        )
        for w in wrestlers:
            if w not in leaders and shift != 0:
                w.morale = max(0, min(MAX_STAT_CAP, (w.morale or 50) + shift))

    if toxic_count > 0:
        for w in wrestlers:
            if (w.locker_room_standing or "neutral") != "toxic":
                w.morale = max(0, (w.morale or 50) - toxic_count)


def apply_politics_to_booking(
    db: Session, wrestler: GameWrestlerDB, planned_finish: str
) -> str:
    """Creative control: high-influence veterans may refuse clean losses.
    Returns potentially modified finish type."""
    influence = wrestler.creative_influence or 0
    if (
        influence > CREATIVE_CONTROL_THRESHOLD
        and planned_finish in CREATIVE_CONTROL_FINISHES
    ):
        if random.random() < influence / CREATIVE_CONTROL_DIVISOR:
            return random.choice(CREATIVE_CONTROL_ALTERNATIVES)
    return planned_finish
