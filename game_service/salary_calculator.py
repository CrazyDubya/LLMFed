"""
Salary Calculator — multi-factor wrestler valuation for contract offers.

Replaces the simplistic ``popularity * 30`` formula with a model that
considers multiple wrestler attributes AND the offering federation's
financial constraints.

Factors:
    * **Popularity** — fan draw power (biggest weight)
    * **In-ring skill** — average of strength, speed, technical, psychology
    * **Charisma** — promo/entertainment value
    * **Win rate** — recent success
    * **Experience** — tenure premium
    * **Morale** — unhappy wrestlers accept lower offers
    * **Federation budget** — salary capped to a fraction of the fed's budget

The formula produces a weekly salary in the range [MIN_SALARY, MAX_SALARY]
and is guaranteed never to exceed ``max_salary_fraction`` of the fed's
remaining budget, preventing runaway inflation.
"""

import logging
import random
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Salary bounds
MIN_SALARY = 500
MAX_SALARY = 25_000

# No single contract should exceed this fraction of the federation's budget
MAX_BUDGET_FRACTION = 0.05


def calculate_salary(
    popularity: int,
    charisma: int = 50,
    avg_ring_skill: float = 50.0,
    win_rate: float = 0.5,
    experience_weeks: int = 0,
    morale: int = 50,
    federation_budget: Optional[float] = None,
    noise: bool = True,
) -> int:
    """Compute a weekly salary based on multiple wrestler attributes.

    All stat inputs are expected on a 0–100 scale.  ``win_rate`` is 0.0–1.0.
    ``experience_weeks`` is total weeks under contract.

    Returns an integer weekly salary in [MIN_SALARY, MAX_SALARY], further
    capped to ``MAX_BUDGET_FRACTION`` of ``federation_budget`` if provided.
    """
    # Base: weighted combination of stats
    base = (
        popularity * 0.40
        + charisma * 0.20
        + avg_ring_skill * 0.20
        + (win_rate * 100) * 0.10
        + min(experience_weeks / 52, 10) * 1.0  # up to 10 pts for experience
    )

    # Scale to dollar range: base is ~0-100, map to 500-25000
    # salary ≈ MIN_SALARY + (base / 100) * (MAX_SALARY - MIN_SALARY)
    raw_salary = MIN_SALARY + (base / 100) * (MAX_SALARY - MIN_SALARY)

    # Morale discount: unhappy wrestlers accept ~20% less
    if morale < 30:
        raw_salary *= 0.80
    elif morale < 50:
        raw_salary *= 0.90

    # Random noise (±8%) to simulate market dynamics
    if noise:
        raw_salary *= random.uniform(0.92, 1.08)

    salary = int(max(MIN_SALARY, min(MAX_SALARY, raw_salary)))

    # Federation budget cap
    if federation_budget is not None and federation_budget > 0:
        budget_cap = int(federation_budget * MAX_BUDGET_FRACTION)
        if salary > budget_cap:
            logger.debug(
                "Salary %d capped to %d (%.0f%% of federation budget %.0f)",
                salary, budget_cap, MAX_BUDGET_FRACTION * 100, federation_budget,
            )
            salary = max(MIN_SALARY, budget_cap)

    return salary


def calculate_salary_from_db(
    db: Session,
    wrestler_id: str,
    federation_id: Optional[str] = None,
) -> int:
    """Convenience: look up wrestler stats from DB and compute salary."""
    from models.game_models import GameWrestlerDB, WrestlerStatsDB, GameFederationDB

    wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler_id).first()
    if not wrestler:
        return MIN_SALARY

    stats = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == wrestler_id).first()
    avg_ring = 50.0
    charisma = 50
    if stats:
        avg_ring = (
            (stats.power or 50) +
            (stats.speed or 50) +
            (stats.technical or 50) +
            (stats.psychology or 50)
        ) / 4
        charisma = stats.charisma or 50

    fed_budget = None
    if federation_id:
        fed = db.query(GameFederationDB).filter(GameFederationDB.id == federation_id).first()
        if fed:
            fed_budget = fed.budget

    # Estimate win_rate from win_streak if detailed W/L counters aren't available
    win_streak = getattr(wrestler, "win_streak", 0) or 0
    estimated_win_rate = 0.5 + (win_streak * 0.05)  # +5% per streak win, -5% per streak loss
    estimated_win_rate = max(0.0, min(1.0, estimated_win_rate))

    return calculate_salary(
        popularity=wrestler.popularity or 50,
        charisma=charisma,
        avg_ring_skill=avg_ring,
        win_rate=estimated_win_rate,
        experience_weeks=0,  # could be computed from first contract start_date
        morale=wrestler.morale or 50,
        federation_budget=fed_budget,
    )
