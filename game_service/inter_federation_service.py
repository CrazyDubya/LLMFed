"""
Inter-Federation Service — extracted from WorldTicker.

Handles market share dynamics, talent offers between federations,
federation momentum, and TV deal adjustments.

All functions take (db, world, events) where *events* is a list to
which human-readable event strings are appended.  The caller is
responsible for persisting narrative log entries via a callback.
"""

import logging
import random
from typing import Callable, List

from sqlalchemy.orm import Session

from models.game_models import (
    WorldDB, GameFederationDB, GameWrestlerDB,
    ContractDB, ShowDB, TalentOfferDB,
)
from game_service.player_action_handler import get_active_contract

logger = logging.getLogger(__name__)

# Lazy import to avoid circular deps
_news_service = None


def _get_news_service():
    global _news_service
    if _news_service is None:
        from game_service import news_service as _ns
        _news_service = _ns
    return _news_service


def advance_game_date(date_str: str, days: int = 1) -> str:
    """Advance a YYYY-MM-DD date string by N days."""
    from datetime import datetime, timedelta
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt += timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def get_day_of_week(date_str: str) -> int:
    """Get day of week (0=Monday, 6=Sunday) from date string."""
    from datetime import datetime
    return datetime.strptime(date_str, "%Y-%m-%d").weekday()


# -----------------------------------------------------------------
# Public API — each function mirrors the old WorldTicker method
# -----------------------------------------------------------------

def update_federation_momentum(db: Session, world: WorldDB, events: List[str],
                               log_event: Callable, game_date: str):
    """Daily federation momentum adjustment."""
    feds = db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world.id,
        GameFederationDB.is_active == True,
    ).all()

    for fed in feds:
        momentum = fed.momentum or 50

        # Recent show quality (check last show)
        last_show = db.query(ShowDB).filter(
            ShowDB.federation_id == fed.id,
            ShowDB.is_completed == True,
            ShowDB.game_date == game_date,
        ).first()

        if last_show and last_show.overall_rating:
            if last_show.overall_rating >= 4.0:
                momentum += 3
            elif last_show.overall_rating >= 3.0:
                momentum += 1
            elif last_show.overall_rating < 2.0:
                momentum -= 2

        # Roster morale check
        contracts = db.query(ContractDB).filter(
            ContractDB.federation_id == fed.id,
            ContractDB.status == "active",
        ).all()
        if contracts:
            wrestler_ids = [c.wrestler_id for c in contracts]
            wrestlers = db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id.in_(wrestler_ids),
            ).all()
            if wrestlers:
                avg_morale = sum(w.morale for w in wrestlers) / len(wrestlers)
                if avg_morale < 40:
                    momentum -= 3  # Scandal/low morale

        # Natural regression toward 50
        if momentum > 50:
            momentum -= 1
        elif momentum < 50:
            momentum += 1

        fed.momentum = max(0, min(100, momentum))


def redistribute_market_share(db: Session, world: WorldDB, events: List[str],
                              log_event: Callable):
    """Redistribute market share based on momentum and show quality."""
    feds = db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world.id,
        GameFederationDB.is_active == True,
    ).all()

    if not feds:
        return

    total_momentum = sum(f.momentum or 50 for f in feds)
    if total_momentum == 0:
        return

    for fed in feds:
        # Market share proportional to momentum
        target_share = ((fed.momentum or 50) / total_momentum) * 100
        current = fed.market_share or 0
        # Gradual shift toward target (10% per week)
        fed.market_share = round(current + (target_share - current) * 0.1, 1)


def generate_talent_offers(db: Session, world: WorldDB, events: List[str],
                           log_event: Callable, game_date: str):
    """NPC feds make talent offers to rivals' wrestlers."""
    npc_feds = db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world.id,
        GameFederationDB.is_npc == True,
        GameFederationDB.is_active == True,
        GameFederationDB.budget > 50000,
    ).all()

    for fed in npc_feds:
        if random.random() > 0.15:  # 15% chance per week
            continue

        # Find targets: popular wrestlers from other feds with low morale
        targets = db.query(GameWrestlerDB).join(ContractDB).filter(
            GameWrestlerDB.world_id == world.id,
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.is_npc == True,
            ContractDB.federation_id != fed.id,
            ContractDB.status == "active",
        ).filter(
            (GameWrestlerDB.popularity > 60) | (GameWrestlerDB.morale < 40)
        ).all()

        if not targets:
            continue

        target = random.choice(targets)

        # Check no existing pending offer
        existing = db.query(TalentOfferDB).filter(
            TalentOfferDB.wrestler_id == target.id,
            TalentOfferDB.status == "pending",
        ).first()
        if existing:
            continue

        salary = max(1500, target.popularity * 30 + random.randint(-500, 500))
        expires = advance_game_date(game_date, 14)

        db.add(TalentOfferDB(
            world_id=world.id,
            federation_id=fed.id,
            wrestler_id=target.id,
            salary_offered=salary,
            contract_length_weeks=52,
            offered_date=game_date,
            expires_date=expires,
        ))
        log_event(
            "talent_offer",
            f"{fed.short_name or fed.name} makes an offer to {target.name}",
            [fed.id, target.id], importance=5,
        )


def process_talent_offers(db: Session, world: WorldDB, events: List[str],
                          log_event: Callable, game_date: str):
    """Process pending talent offers -- NPC wrestlers decide."""
    offers = db.query(TalentOfferDB).filter(
        TalentOfferDB.world_id == world.id,
        TalentOfferDB.status == "pending",
    ).all()

    for offer in offers:
        # Expired?
        if offer.expires_date and offer.expires_date <= game_date:
            offer.status = "expired"
            continue

        wrestler = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == offer.wrestler_id
        ).first()
        if not wrestler or not wrestler.is_npc:
            continue

        # Current contract
        current = get_active_contract(db, wrestler.id)

        accept_chance = 0.1  # Base 10%
        if wrestler.morale < 30:
            accept_chance += 0.3
        if current and offer.salary_offered > current.salary_weekly * 1.5:
            accept_chance += 0.2
        if wrestler.popularity > 70:
            accept_chance -= 0.1  # Popular wrestlers are pickier

        if random.random() < accept_chance:
            # Accept: end old contract, create new one
            if current:
                current.status = "terminated"
                current.end_date = game_date

            new_contract = ContractDB(
                world_id=world.id,
                wrestler_id=wrestler.id,
                federation_id=offer.federation_id,
                salary_weekly=offer.salary_offered,
                start_date=game_date,
                is_exclusive=True,
            )
            db.add(new_contract)
            offer.status = "accepted"

            fed = db.query(GameFederationDB).filter(
                GameFederationDB.id == offer.federation_id
            ).first()
            fed_name = fed.short_name or fed.name if fed else "Unknown"
            log_event(
                "talent_signing",
                f"BREAKING: {wrestler.name} signs with {fed_name}!",
                [wrestler.id, offer.federation_id], importance=8,
            )
            events.append(f"{wrestler.name} signs with {fed_name}!")
            _get_news_service().generate_signing_news(
                db, world.id, wrestler.name, fed_name, game_date,
            )

            # Momentum shifts
            if fed:
                fed.momentum = min(100, (fed.momentum or 50) + 3)
        else:
            offer.status = "rejected"


def adjust_tv_deals(db: Session, world: WorldDB, events: List[str],
                    log_event: Callable):
    """Quarterly TV deal adjustments based on performance."""
    # Only adjust on first Sunday of each quarter-ish (every ~13 weeks)
    if world.current_tick % 91 != 0:
        return

    feds = db.query(GameFederationDB).filter(
        GameFederationDB.world_id == world.id,
        GameFederationDB.is_active == True,
    ).all()

    for fed in feds:
        momentum = fed.momentum or 50
        if momentum > 70:
            # Hot fed: TV deal increases
            increase = fed.tv_deal_value * random.uniform(0.10, 0.20)
            fed.tv_deal_value += increase
        elif momentum < 30 and fed.tv_deal_value > 5000:
            # Cold fed: TV deal shrinks
            decrease = fed.tv_deal_value * random.uniform(0.05, 0.15)
            fed.tv_deal_value = max(5000, fed.tv_deal_value - decrease)
