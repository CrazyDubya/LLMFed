"""
World Ticker - advances the game world by one game day.

Each tick processes player actions, AI decisions, scheduled shows,
storyline progression, economy, and world events.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from models.game_models import (
    WorldDB, WorldStateDB, PlayerActionDB, GameFederationDB,
    GameWrestlerDB, WrestlerStatsDB, ContractDB, ShowDB, ShowSegmentDB,
    MatchDB, MatchParticipantDB,
    StorylineDB, StorylineParticipantDB, GameNarrativeLogDB,
    WorldNewsDB, WrestlerHistoryDB, ChampionshipDB,
)

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_match_engine = None
_show_service = None
_storyline_service = None


def _get_match_engine():
    global _match_engine
    if _match_engine is None:
        from core_engine import match_engine as _me
        _match_engine = _me
    return _match_engine


def _get_show_service():
    global _show_service
    if _show_service is None:
        from game_service import show_service as _ss
        _show_service = _ss
    return _show_service


def _get_storyline_service():
    global _storyline_service
    if _storyline_service is None:
        from game_service import storyline_service as _sls
        _storyline_service = _sls
    return _storyline_service


def advance_game_date(date_str: str, days: int = 1) -> str:
    """Advance a YYYY-MM-DD date string by N days."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt += timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def get_day_of_week(date_str: str) -> int:
    """Get day of week (0=Monday, 6=Sunday) from date string."""
    return datetime.strptime(date_str, "%Y-%m-%d").weekday()


class WorldTicker:
    """Advances a game world by one day per tick."""

    def __init__(self, db: Session, world_id: str):
        self.db = db
        self.world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
        if not self.world:
            raise ValueError(f"World {world_id} not found")
        self.events: List[str] = []

    def tick(self, days: int = 1) -> dict:
        """Advance the world by N game days. Returns a summary."""
        results = []
        for _ in range(days):
            day_result = self._tick_one_day()
            results.append(day_result)
        return {
            "world_id": self.world.id,
            "new_game_date": self.world.current_game_date,
            "new_tick": self.world.current_tick,
            "days_advanced": days,
            "day_results": results,
        }

    def _tick_one_day(self) -> dict:
        """Process one game day."""
        self.events = []
        old_date = self.world.current_game_date
        new_date = advance_game_date(old_date)

        self.world.current_game_date = new_date
        self.world.current_tick += 1
        tick = self.world.current_tick

        # 1. Process player actions
        self._process_player_actions()

        # 2. NPC AI decisions
        self._npc_decisions()

        # 3. Simulate any shows scheduled for today
        self._simulate_shows(new_date)

        # 4. Advance storylines
        self._advance_storylines()

        # 5. Economy tick
        self._economy_tick()

        # 6. Random world events
        self._world_events(new_date)

        # 7. Contract management
        self._check_contracts(new_date)

        # 8. Wrestler condition recovery
        self._recover_conditions()

        self.db.commit()

        return {
            "game_date": new_date,
            "tick": tick,
            "events": self.events,
        }

    # ------------------------------------------------------------------
    # Phase 1: Process player action queue
    # ------------------------------------------------------------------

    def _process_player_actions(self):
        """Process pending player actions."""
        pending = self.db.query(PlayerActionDB).filter(
            PlayerActionDB.world_id == self.world.id,
            PlayerActionDB.status == "pending",
        ).all()

        for action in pending:
            try:
                action.status = "processing"
                result = self._execute_player_action(action)
                action.status = "completed"
                action.result = result
                action.processed_at = datetime.utcnow()
                self.events.append(f"Processed action: {action.action_type}")
            except Exception as e:
                action.status = "failed"
                action.result = {"error": str(e)}
                logger.warning(f"Player action {action.id} failed: {e}")

    def _execute_player_action(self, action: PlayerActionDB) -> dict:
        """Execute a single player action. Returns result dict."""
        action_type = action.action_type
        data = action.action_data

        if action_type == "sign_wrestler":
            return self._action_sign_wrestler(data)
        elif action_type == "book_show":
            return self._action_book_show(data)
        elif action_type == "train":
            return self._action_train(data)
        elif action_type == "cut_promo":
            return self._action_cut_promo(data)
        else:
            return {"message": f"Action '{action_type}' acknowledged"}

    def _action_sign_wrestler(self, data: dict) -> dict:
        """Promoter signs a free agent."""
        wrestler_id = data.get("wrestler_id")
        federation_id = data.get("federation_id")
        salary = data.get("salary_weekly", 1000)

        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id
        ).first()
        if not wrestler:
            raise ValueError("Wrestler not found")

        # Check not already signed
        active_contract = self.db.query(ContractDB).filter(
            ContractDB.wrestler_id == wrestler_id,
            ContractDB.status == "active",
        ).first()
        if active_contract:
            raise ValueError("Wrestler already under contract")

        contract = ContractDB(
            world_id=self.world.id,
            wrestler_id=wrestler_id,
            federation_id=federation_id,
            salary_weekly=salary,
            start_date=self.world.current_game_date,
            is_exclusive=True,
        )
        self.db.add(contract)
        self._log_event("signing", f"{wrestler.name} signed with federation", [wrestler_id, federation_id])
        return {"contract_id": contract.id, "wrestler": wrestler.name}

    def _action_book_show(self, data: dict) -> dict:
        """Promoter books a show."""
        show = ShowDB(
            world_id=self.world.id,
            federation_id=data["federation_id"],
            name=data.get("name", "Live Event"),
            show_type=data.get("show_type", "weekly"),
            venue=data.get("venue", "Local Arena"),
            capacity=data.get("capacity", 5000),
            game_date=data.get("game_date", self.world.current_game_date),
        )
        self.db.add(show)
        self.db.flush()
        return {"show_id": show.id, "name": show.name, "date": show.game_date}

    def _action_train(self, data: dict) -> dict:
        """Wrestler trains a stat."""
        wrestler_id = data.get("wrestler_id")
        stat_name = data.get("stat", "stamina")

        stats = self.db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == wrestler_id
        ).first()
        if not stats:
            raise ValueError("Wrestler stats not found")

        if not hasattr(stats, stat_name):
            raise ValueError(f"Invalid stat: {stat_name}")

        current = getattr(stats, stat_name)
        # Training gain decreases as stat gets higher
        gain = max(1, random.randint(1, 3) - (current // 40))
        new_val = min(100, current + gain)
        setattr(stats, stat_name, new_val)

        # Training fatigues the wrestler slightly
        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id
        ).first()
        if wrestler:
            wrestler.condition = max(0, wrestler.condition - random.randint(2, 5))

        return {"stat": stat_name, "old": current, "new": new_val, "gain": new_val - current}

    def _action_cut_promo(self, data: dict) -> dict:
        """Wrestler cuts a promo (processed by LLM later)."""
        # For now, return acknowledgement. Full LLM promo generation
        # will be in the storyline engine.
        return {"message": "Promo direction noted", "direction": data.get("direction", "")}

    # ------------------------------------------------------------------
    # Phase 2: NPC AI decisions
    # ------------------------------------------------------------------

    def _npc_decisions(self):
        """AI-controlled federations and wrestlers make decisions."""
        day_of_week = get_day_of_week(self.world.current_game_date)

        # NPC federations book weekly shows on specific days
        npc_feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_npc == True,
            GameFederationDB.is_active == True,
        ).all()

        for fed in npc_feds:
            # Each fed has a weekly show day (based on name hash)
            show_day = hash(fed.name) % 7
            if day_of_week == show_day:
                self._npc_book_weekly_show(fed)

    def _npc_book_weekly_show(self, fed: GameFederationDB):
        """NPC federation auto-books a weekly show with a full match card."""
        show_svc = _get_show_service()
        show = show_svc.create_show(
            self.db, self.world.id, fed.id,
            name=f"{fed.short_name or fed.name} Weekly",
            show_type="weekly",
            venue=f"{fed.home_region} Arena",
            capacity=random.randint(2000, 10000),
            game_date=self.world.current_game_date,
        )
        # Auto-book a match card
        segments = show_svc.npc_book_card(self.db, show)
        self.events.append(
            f"{fed.short_name or fed.name} airs weekly show ({len(segments)} matches)"
        )

    # ------------------------------------------------------------------
    # Phase 3: Simulate shows
    # ------------------------------------------------------------------

    def _simulate_shows(self, game_date: str):
        """Simulate all shows scheduled for today."""
        shows = self.db.query(ShowDB).filter(
            ShowDB.world_id == self.world.id,
            ShowDB.game_date == game_date,
            ShowDB.is_completed == False,
        ).all()

        for show in shows:
            self._simulate_show(show)

    def _simulate_show(self, show: ShowDB):
        """Simulate a single show, running each match through the match engine."""
        me = _get_match_engine()
        sl_svc = _get_storyline_service()

        fed = self.db.query(GameFederationDB).filter(
            GameFederationDB.id == show.federation_id
        ).first()

        prestige_factor = (fed.prestige if fed else 50) / 100

        # Simulate each match segment through the engine
        segments = self.db.query(ShowSegmentDB).filter(
            ShowSegmentDB.show_id == show.id,
        ).order_by(ShowSegmentDB.position).all()

        match_ratings = []
        for seg in segments:
            if seg.segment_type == "match" and seg.match_id:
                match = self.db.query(MatchDB).filter(
                    MatchDB.id == seg.match_id
                ).first()
                if match and not match.is_completed:
                    try:
                        result = me.simulate_match_from_db(self.db, match)
                        seg.is_completed = True
                        seg.rating = result.match_rating
                        seg.crowd_reaction = "pop" if result.crowd_heat > 60 else "mixed"
                        seg.actual_duration_minutes = result.duration_ticks
                        match_ratings.append(result.match_rating)

                        # Check for storyline triggers from match result
                        sl_svc.check_match_storyline_triggers(
                            self.db, match, self.world.current_game_date
                        )
                    except Exception as e:
                        logger.warning(f"Match simulation failed: {e}")
                        seg.is_completed = True
                        seg.rating = round(random.uniform(2.0, 4.0), 1)
                        match_ratings.append(seg.rating)
            elif seg.segment_type == "promo":
                seg.is_completed = True
                seg.rating = round(random.uniform(2.0, 4.5), 1)

        # Calculate show-level stats
        attendance = int(show.capacity * random.uniform(0.3, 1.0) * prestige_factor)
        ticket_price = random.uniform(15, 75) * prestige_factor
        gate = attendance * ticket_price

        show.attendance = attendance
        show.gate_revenue = round(gate, 2)
        show.is_completed = True

        if match_ratings:
            show.overall_rating = round(sum(match_ratings) / len(match_ratings), 1)
        else:
            show.overall_rating = round(random.uniform(2.0, 4.0) * prestige_factor, 1)

        if show.show_type == "weekly" and fed:
            show.tv_rating = round(random.uniform(0.5, 3.0) * prestige_factor, 2)

        # Update federation finances
        if fed:
            fed.weekly_revenue += gate
            if show.show_type == "ppv":
                ppv_buys = int(random.uniform(50000, 500000) * prestige_factor)
                show.ppv_buys = ppv_buys
                fed.weekly_revenue += ppv_buys * 49.99

        self._log_event(
            "show",
            f"{show.name} drew {attendance} fans (Rating: {show.overall_rating})",
            [show.federation_id],
            importance=6,
        )
        self.events.append(f"Show completed: {show.name} ({attendance} attendance)")

    # ------------------------------------------------------------------
    # Phase 4: Storyline advancement
    # ------------------------------------------------------------------

    def _advance_storylines(self):
        """Progress active storylines and periodically generate new ones."""
        sl_svc = _get_storyline_service()

        active = self.db.query(StorylineDB).filter(
            StorylineDB.world_id == self.world.id,
            StorylineDB.status.in_(["brewing", "active", "climax"]),
        ).all()

        for storyline in active:
            # Storylines heat decays if not progressed
            if random.random() < 0.1:  # 10% chance per day
                storyline.heat = max(0, storyline.heat - 1)

            # Storylines can naturally escalate
            if storyline.status == "brewing" and storyline.heat > 60:
                storyline.status = "active"
            elif storyline.status == "active" and storyline.heat > 85:
                storyline.status = "climax"

            # Long-running climax storylines auto-resolve
            if storyline.status == "climax" and storyline.heat < 30:
                sl_svc.resolve_storyline(self.db, storyline, "Fizzled out")

        # Weekly storyline generation (on Wednesdays)
        if get_day_of_week(self.world.current_game_date) == 2:
            new_sls = sl_svc.auto_generate_storylines(
                self.db, self.world.id, self.world.current_game_date
            )
            for sl in new_sls:
                self.events.append(f"New storyline: {sl.name}")

    # ------------------------------------------------------------------
    # Phase 5: Economy
    # ------------------------------------------------------------------

    def _economy_tick(self):
        """Weekly financial processing (on Sundays)."""
        if get_day_of_week(self.world.current_game_date) != 6:  # Sunday
            return

        feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_active == True,
        ).all()

        for fed in feds:
            # Calculate weekly expenses (salaries)
            contracts = self.db.query(ContractDB).filter(
                ContractDB.federation_id == fed.id,
                ContractDB.status == "active",
            ).all()
            total_salary = sum(c.salary_weekly for c in contracts)

            # Add TV deal income
            income = fed.tv_deal_value + fed.weekly_revenue
            expenses = total_salary + random.uniform(5000, 20000)  # Operating costs

            fed.budget += income - expenses
            fed.weekly_expenses = round(expenses, 2)
            fed.weekly_revenue = 0  # Reset for next week

            # Prestige adjusts slowly based on finances and show quality
            if fed.budget < 0:
                fed.prestige = max(0, fed.prestige - 1)
            elif fed.budget > 200000:
                fed.prestige = min(100, fed.prestige + random.randint(0, 1))

    # ------------------------------------------------------------------
    # Phase 6: World events
    # ------------------------------------------------------------------

    def _world_events(self, game_date: str):
        """Random events: injuries, retirements, etc."""
        # Small chance of random events per day
        if random.random() < 0.05:  # 5% per day
            self._random_injury(game_date)

        if random.random() < 0.01:  # 1% per day
            self._random_retirement(game_date)

    def _random_injury(self, game_date: str):
        """Random wrestler injury."""
        wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.is_injured == False,
        ).all()

        if not wrestlers:
            return

        # Weight by injury_prone stat
        victim = random.choice(wrestlers)
        stats = self.db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == victim.id
        ).first()

        injury_chance = (stats.injury_prone if stats else 30) / 100
        if random.random() > injury_chance:
            return

        weeks_out = random.randint(2, 26)
        return_date = advance_game_date(game_date, weeks_out * 7)
        victim.is_injured = True
        victim.injury_return_date = return_date
        victim.condition = max(0, victim.condition - random.randint(20, 50))

        self._log_event(
            "injury",
            f"{victim.name} suffers injury, out {weeks_out} weeks",
            [victim.id],
            importance=7,
        )
        self.events.append(f"INJURY: {victim.name} (out {weeks_out} weeks)")

    def _random_retirement(self, game_date: str):
        """Random wrestler retirement (older wrestlers)."""
        old_wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.age >= 38,
        ).all()

        if not old_wrestlers:
            return

        retiree = random.choice(old_wrestlers)
        if random.random() < 0.3:  # 30% of selected old wrestlers
            retiree.is_active = False
            retiree.retirement_date = game_date
            self._log_event(
                "retirement",
                f"{retiree.name} announces retirement after {retiree.experience_years} years",
                [retiree.id],
                importance=8,
            )
            self.events.append(f"RETIREMENT: {retiree.name}")

    # ------------------------------------------------------------------
    # Phase 7: Contract management
    # ------------------------------------------------------------------

    def _check_contracts(self, game_date: str):
        """Check for expiring contracts."""
        expiring = self.db.query(ContractDB).filter(
            ContractDB.world_id == self.world.id,
            ContractDB.status == "active",
            ContractDB.end_date != None,
            ContractDB.end_date <= game_date,
        ).all()

        for contract in expiring:
            contract.status = "expired"
            wrestler = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id == contract.wrestler_id
            ).first()
            if wrestler:
                self.events.append(f"Contract expired: {wrestler.name}")

    # ------------------------------------------------------------------
    # Phase 8: Recovery
    # ------------------------------------------------------------------

    def _recover_conditions(self):
        """Wrestlers recover condition daily."""
        wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
        ).all()

        for w in wrestlers:
            if w.is_injured:
                # Check if injury is healed
                if w.injury_return_date and w.injury_return_date <= self.world.current_game_date:
                    w.is_injured = False
                    w.injury_return_date = None
                    w.condition = 70
                    self.events.append(f"{w.name} returns from injury")
            else:
                # Natural condition recovery
                w.condition = min(100, w.condition + random.randint(1, 3))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, description: str,
                   involved: list = None, importance: int = 5):
        """Log a narrative event."""
        self.db.add(GameNarrativeLogDB(
            world_id=self.world.id,
            game_date=self.world.current_game_date,
            tick=self.world.current_tick,
            event_type=event_type,
            description=description,
            involved_entities=involved or [],
            importance=importance,
        ))
