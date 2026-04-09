"""
World Ticker - advances the game world by one game day.

Each tick processes player actions, AI decisions, scheduled shows,
storyline progression, economy, and world events.
"""

import logging
import os
import random
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

# LLM integration gate — set LLMFED_USE_LLM=1 to enable LLM-generated narrative
USE_LLM = os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes")


def _llm_generate(prompt: str, fallback: str, system_msg: str = None) -> str:
    """Generate text via LLM if enabled, otherwise return fallback.

    Never raises — any failure returns the fallback text silently.
    """
    if not USE_LLM:
        return fallback
    try:
        from llm_abstraction.provider import get_llm
        llm = get_llm()
        response = llm.generate(prompt, system_message=system_msg, max_tokens=200)
        if response and response.content:
            return response.content.strip()
    except Exception as e:
        logging.getLogger(__name__).debug("LLM generation failed, using fallback: %s", e)
    return fallback

from models.game_models import (
    WorldDB, WorldStateDB, PlayerActionDB, GameFederationDB,
    GameWrestlerDB, WrestlerStatsDB, ContractDB, ShowDB, ShowSegmentDB,
    MatchDB, MatchParticipantDB,
    StorylineDB, StorylineParticipantDB, GameNarrativeLogDB,
    WorldNewsDB, WrestlerHistoryDB, ChampionshipDB,
    WrestlerRelationshipDB, TagTeamDB, TalentOfferDB,
    PromoDB,
)

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_match_engine = None
_show_service = None
_storyline_service = None
_match_aftermath = None
_news_service = None
_viewership_service = None


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


def _get_match_aftermath():
    global _match_aftermath
    if _match_aftermath is None:
        from core_engine import match_aftermath as _ma
        _match_aftermath = _ma
    return _match_aftermath


def _get_news_service():
    global _news_service
    if _news_service is None:
        from game_service import news_service as _ns
        _news_service = _ns
    return _news_service


def _get_viewership_service():
    global _viewership_service
    if _viewership_service is None:
        from game_service import viewership_service as _vs
        _viewership_service = _vs
    return _viewership_service


_stable_service = None
_manager_service = None


def _get_stable_service():
    global _stable_service
    if _stable_service is None:
        from game_service import stable_service as _stbs
        _stable_service = _stbs
    return _stable_service


def _get_manager_service():
    global _manager_service
    if _manager_service is None:
        from game_service import manager_service as _mgrs
        _manager_service = _mgrs
    return _manager_service


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

        # 9. Morale processing
        self._process_morale(new_date)

        # 10. Tag team management (Tuesdays)
        self._manage_tag_teams(new_date)

        # 11. Inter-federation dynamics
        self._inter_federation_dynamics(new_date)

        # 12. Weekly news generation (Sundays)
        self._generate_weekly_news(new_date)

        # 13. Wrestler lifecycle (Groups 1-6)
        self._wrestler_lifecycle(new_date)

        # 14. Persona & social media (Group 7)
        self._persona_tick(new_date)

        # 15. Stable/faction internal dynamics (Wednesdays + Saturdays)
        self._stable_dynamics_tick(new_date)

        # 16. Manager effectiveness tracking (Thursdays)
        self._manager_tick(new_date)

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
        elif action_type == "form_stable":
            return self._action_form_stable(data)
        elif action_type == "join_stable":
            return self._action_join_stable(data)
        elif action_type == "leave_stable":
            return self._action_leave_stable(data)
        elif action_type == "dissolve_stable":
            return self._action_dissolve_stable(data)
        elif action_type == "assign_manager":
            return self._action_assign_manager(data)
        elif action_type == "create_manager":
            return self._action_create_manager(data)
        elif action_type == "remove_manager":
            return self._action_remove_manager(data)
        elif action_type == "create_storyline":
            return self._action_create_storyline(data)
        elif action_type == "advance_storyline":
            return self._action_advance_storyline(data)
        elif action_type == "request_match":
            return self._action_request_match(data)
        elif action_type == "open_challenge":
            return self._action_open_challenge(data)
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

        # Mentor bonus (Group 4)
        try:
            from game_service.wrestler_lifecycle_service import training_with_mentor
            gain += training_with_mentor(self.db, wrestler_id, stat_name)
        except (ValueError, AttributeError) as e:
            logger.debug("Mentor bonus skipped for %s: %s", wrestler_id, e)

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
        """Wrestler cuts a promo — gains popularity, boosts storyline heat."""
        wrestler_id = data.get("wrestler_id")
        target_id = data.get("target_wrestler_id")
        direction = data.get("direction", "")

        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id
        ).first()
        if not wrestler:
            raise ValueError("Wrestler not found")

        stats = self.db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == wrestler_id
        ).first()

        # Promo quality based on charisma + mic skill
        charisma = stats.charisma if stats else 50
        mic = stats.mic_skill if stats else 50
        base_quality = (charisma + mic) / 2
        roll = random.randint(-15, 15)
        quality = max(1, min(100, base_quality + roll))

        # Popularity gain: 1-5 based on quality
        pop_gain = 1
        if quality >= 80:
            pop_gain = random.randint(3, 5)
        elif quality >= 60:
            pop_gain = random.randint(2, 4)
        elif quality >= 40:
            pop_gain = random.randint(1, 3)

        old_pop = wrestler.popularity
        wrestler.popularity = min(100, wrestler.popularity + pop_gain)
        wrestler.morale = min(100, (wrestler.morale or 50) + 2)

        result = {
            "quality": quality,
            "popularity_gain": pop_gain,
            "old_popularity": old_pop,
            "new_popularity": wrestler.popularity,
            "direction": direction,
        }

        # If targeting a rival, boost storyline heat
        if target_id:
            sl_svc = _get_storyline_service()
            existing = sl_svc._find_storyline_between(self.db, wrestler_id, target_id)
            if existing:
                heat_boost = 5 if quality >= 60 else 3
                sl_svc.progress_storyline(
                    self.db, existing, "promo", heat_boost,
                    description=f"{wrestler.name} cut a fiery promo targeting their rival!",
                )
                result["storyline_heat_boost"] = heat_boost

        self._log_event(
            "promo",
            f"{wrestler.name} cuts a promo (quality: {quality}, pop +{pop_gain})",
            [wrestler_id] + ([target_id] if target_id else []),
            importance=5,
        )
        return result

    # --- Match request / open challenge actions ---

    def _action_request_match(self, data: dict) -> dict:
        """Player requests a match on the next show for their federation.

        Books the player into an opening slot on the next weekly show.
        Win = +2-4 popularity, Loss = +1 popularity (exposure value).
        Cooldown: 1 request per game week (7 ticks).
        """
        wrestler_id = data.get("wrestler_id")
        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id
        ).first()
        if not wrestler:
            raise ValueError("Wrestler not found")

        # Find wrestler's federation
        contract = self.db.query(ContractDB).filter(
            ContractDB.wrestler_id == wrestler_id,
            ContractDB.status == "active",
        ).first()
        if not contract:
            raise ValueError("Wrestler has no active contract")

        # Store the request in world metadata for the show booking phase to pick up
        meta = self.world.world_config or {}
        match_requests = meta.get("pending_match_requests", [])

        # Check cooldown — only 1 request per 7 days
        game_date = self.world.current_game_date
        for req in match_requests:
            if req.get("wrestler_id") == wrestler_id:
                last_date = req.get("date", "")
                try:
                    days_since = (datetime.strptime(game_date, "%Y-%m-%d") -
                                  datetime.strptime(last_date, "%Y-%m-%d")).days
                    if days_since < 7:
                        return {"message": f"Match request on cooldown ({7 - days_since} days remaining)"}
                except (ValueError, TypeError):
                    pass

        # Remove old request for this wrestler if any, add new one
        match_requests = [r for r in match_requests if r.get("wrestler_id") != wrestler_id]
        match_requests.append({
            "wrestler_id": wrestler_id,
            "federation_id": contract.federation_id,
            "date": game_date,
            "type": "request_match",
        })
        meta["pending_match_requests"] = match_requests
        self.world.world_config = meta

        self._log_event(
            "match_request",
            f"{wrestler.name} has requested a match on the next show!",
            [wrestler_id], importance=4,
        )
        return {"message": f"{wrestler.name} is booked for a match on the next show", "status": "pending"}

    def _action_open_challenge(self, data: dict) -> dict:
        """Player issues an open challenge — higher risk/reward than request_match.

        Matched against someone ±10 popularity. Win = +4-6 pop, Loss = +0.
        Can spark a storyline if player popularity > 40.
        """
        wrestler_id = data.get("wrestler_id")
        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id
        ).first()
        if not wrestler:
            raise ValueError("Wrestler not found")

        contract = self.db.query(ContractDB).filter(
            ContractDB.wrestler_id == wrestler_id,
            ContractDB.status == "active",
        ).first()
        if not contract:
            raise ValueError("Wrestler has no active contract")

        # Find a suitable opponent: ±10 popularity from same federation
        roster_contracts = self.db.query(ContractDB).filter(
            ContractDB.federation_id == contract.federation_id,
            ContractDB.status == "active",
            ContractDB.wrestler_id != wrestler_id,
        ).all()

        candidates = []
        for c in roster_contracts:
            opp = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id == c.wrestler_id,
                GameWrestlerDB.is_injured == False,
            ).first()
            if opp and abs(opp.popularity - wrestler.popularity) <= 15:
                candidates.append(opp)

        if not candidates:
            # Fallback: anyone on the roster who isn't injured
            for c in roster_contracts:
                opp = self.db.query(GameWrestlerDB).filter(
                    GameWrestlerDB.id == c.wrestler_id,
                    GameWrestlerDB.is_injured == False,
                ).first()
                if opp:
                    candidates.append(opp)

        if not candidates:
            return {"message": "No suitable opponents available for an open challenge"}

        opponent = random.choice(candidates)

        # Store in metadata for show booking
        meta = self.world.world_config or {}
        match_requests = meta.get("pending_match_requests", [])
        match_requests = [r for r in match_requests if r.get("wrestler_id") != wrestler_id]
        match_requests.append({
            "wrestler_id": wrestler_id,
            "federation_id": contract.federation_id,
            "opponent_id": opponent.id,
            "date": self.world.current_game_date,
            "type": "open_challenge",
        })
        meta["pending_match_requests"] = match_requests
        self.world.world_config = meta

        self._log_event(
            "open_challenge",
            f"{wrestler.name} issues an open challenge! {opponent.name} answers!",
            [wrestler_id, opponent.id], importance=6,
        )
        return {
            "message": f"{wrestler.name} issues an open challenge — {opponent.name} has accepted!",
            "opponent": opponent.name,
            "opponent_id": opponent.id,
        }

    # --- Faction / stable actions ---

    def _action_form_stable(self, data: dict) -> dict:
        """Promoter forms a new stable/faction."""
        stable_svc = _get_stable_service()
        name = data.get("name", "New Faction")
        leader_id = data.get("leader_id")
        member_ids = data.get("founding_member_ids", [])
        if not leader_id:
            raise ValueError("leader_id required")
        if leader_id not in member_ids:
            member_ids = [leader_id] + member_ids

        # Find federation from leader's contract
        contract = self.db.query(ContractDB).filter_by(
            wrestler_id=leader_id, status="active"
        ).first()
        if not contract:
            raise ValueError("Leader has no active contract")

        stable = stable_svc.create_stable(
            self.db, self.world.id, contract.federation_id,
            name=name, leader_id=leader_id,
            founding_member_ids=member_ids,
            alignment=data.get("alignment", "heel"),
            short_name=data.get("short_name"),
            catchphrase=data.get("catchphrase"),
            group_finisher_name=data.get("group_finisher_name"),
            manager_id=data.get("manager_id"),
            game_date=self.world.current_game_date,
        )
        self.events.append(f"Stable formed: {stable.name}")
        return {"stable_id": stable.id, "name": stable.name}

    def _action_join_stable(self, data: dict) -> dict:
        """Add a wrestler to an existing stable."""
        stable_svc = _get_stable_service()
        stable_id = data.get("stable_id")
        wrestler_id = data.get("wrestler_id")
        role = data.get("role", "recruit")
        if not stable_id or not wrestler_id:
            raise ValueError("stable_id and wrestler_id required")
        member = stable_svc.add_member(
            self.db, stable_id, wrestler_id, role,
            game_date=self.world.current_game_date,
        )
        wrestler = self.db.query(GameWrestlerDB).filter_by(id=wrestler_id).first()
        self.events.append(f"{wrestler.name if wrestler else wrestler_id} joins stable")
        return {"member_id": member.id, "role": member.role}

    def _action_leave_stable(self, data: dict) -> dict:
        """Remove a wrestler from a stable."""
        stable_svc = _get_stable_service()
        stable_id = data.get("stable_id")
        wrestler_id = data.get("wrestler_id")
        if not stable_id or not wrestler_id:
            raise ValueError("stable_id and wrestler_id required")
        result = stable_svc.remove_member(
            self.db, stable_id, wrestler_id,
            game_date=self.world.current_game_date,
        )
        if not result:
            raise ValueError("Member not found in stable")
        return {"removed": True}

    def _action_dissolve_stable(self, data: dict) -> dict:
        """Dissolve a stable entirely."""
        stable_svc = _get_stable_service()
        stable_id = data.get("stable_id")
        if not stable_id:
            raise ValueError("stable_id required")
        from models.game_models import StableDB
        stable = self.db.query(StableDB).filter_by(id=stable_id).first()
        if not stable:
            raise ValueError("Stable not found")
        stable_svc.dissolve_stable(self.db, stable_id, game_date=self.world.current_game_date)
        self.events.append(f"Stable dissolved: {stable.name}")
        return {"dissolved": True, "name": stable.name}

    # --- Manager actions ---

    def _action_assign_manager(self, data: dict) -> dict:
        """Assign a manager to a wrestler."""
        mgr_svc = _get_manager_service()
        manager_id = data.get("manager_id")
        client_id = data.get("client_wrestler_id")
        if not manager_id or not client_id:
            raise ValueError("manager_id and client_wrestler_id required")
        bond = mgr_svc.assign_manager(
            self.db, self.world.id, manager_id, client_id,
            role=data.get("role", "manager"),
            specialization=data.get("specialization", "all_around"),
            game_date=self.world.current_game_date,
        )
        return {"bond_id": bond.id, "effectiveness": bond.effectiveness}

    def _action_create_manager(self, data: dict) -> dict:
        """Create a new manager character."""
        mgr_svc = _get_manager_service()
        name = data.get("name")
        if not name:
            raise ValueError("name required")
        mgr = mgr_svc.create_manager(
            self.db, self.world.id, name=name,
            alignment=data.get("alignment", "heel"),
            archetype=data.get("archetype", "scheming_manager"),
            federation_id=data.get("federation_id"),
            catchphrase=data.get("catchphrase"),
        )
        self.events.append(f"Manager created: {mgr.name}")
        return {"manager_id": mgr.id, "name": mgr.name}

    def _action_remove_manager(self, data: dict) -> dict:
        """End a manager-client bond."""
        mgr_svc = _get_manager_service()
        bond_id = data.get("bond_id")
        if not bond_id:
            raise ValueError("bond_id required")
        result = mgr_svc.remove_manager(
            self.db, bond_id, game_date=self.world.current_game_date,
        )
        if not result:
            raise ValueError("Bond not found")
        return {"removed": True}

    # --- Storyline actions ---

    def _action_create_storyline(self, data: dict) -> dict:
        """Promoter creates a storyline between wrestlers."""
        sl_svc = _get_storyline_service()
        wrestler_ids = data.get("wrestler_ids", [])
        if len(wrestler_ids) < 2:
            raise ValueError("At least 2 wrestler_ids required")
        federation_id = data.get("federation_id")
        if not federation_id:
            # Infer from first wrestler's contract
            contract = self.db.query(ContractDB).filter_by(
                wrestler_id=wrestler_ids[0], status="active"
            ).first()
            federation_id = contract.federation_id if contract else None
        storyline = sl_svc.create_storyline(
            self.db, self.world.id, federation_id,
            wrestler_ids=wrestler_ids,
            storyline_type=data.get("storyline_type", "feud"),
            name=data.get("name"),
            description=data.get("description"),
            game_date=self.world.current_game_date,
        )
        self.events.append(f"Storyline created: {storyline.name}")
        return {"storyline_id": storyline.id, "name": storyline.name}

    def _action_advance_storyline(self, data: dict) -> dict:
        """Promoter manually advances a storyline's status or heat."""
        storyline_id = data.get("storyline_id")
        if not storyline_id:
            raise ValueError("storyline_id required")
        storyline = self.db.query(StorylineDB).filter_by(id=storyline_id).first()
        if not storyline:
            raise ValueError("Storyline not found")

        new_status = data.get("status")
        heat_boost = data.get("heat_boost", 0)

        if new_status and new_status in ("brewing", "active", "climax", "resolved"):
            old_status = storyline.status
            storyline.status = new_status
            if new_status == "resolved":
                storyline.end_date = self.world.current_game_date
        if heat_boost:
            storyline.heat = max(0, min(100, storyline.heat + heat_boost))

        return {
            "storyline_id": storyline.id,
            "name": storyline.name,
            "status": storyline.status,
            "heat": storyline.heat,
        }

    # ------------------------------------------------------------------
    # Phase 2: NPC AI decisions
    # ------------------------------------------------------------------

    def _npc_decisions(self):
        """AI-controlled federations and wrestlers make decisions.

        Uses the booking vision system to:
        - Book PPV shows when the calendar says so
        - Book weekly TV that builds toward the next PPV
        - Plan PPV cards when entering the build window
        - Adapt vision when circumstances change (hot/cold acts)
        """
        day_of_week = get_day_of_week(self.world.current_game_date)
        game_date = self.world.current_game_date

        npc_feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_npc == True,
            GameFederationDB.is_active == True,
        ).all()

        for fed in npc_feds:
            # Check if today is a PPV day
            ppv = self._check_ppv_today(fed, game_date)
            if ppv:
                self._npc_book_ppv_show(fed, ppv)
            else:
                # Regular weekly show on the fed's designated day
                show_day = hash(fed.name) % 7
                if day_of_week == show_day:
                    self._npc_book_weekly_show(fed)

            # Weekly vision check: plan upcoming PPV cards, adapt to hot/cold acts
            if day_of_week == 0:  # Mondays = planning day
                self._npc_vision_check(fed, game_date)

    def _check_ppv_today(self, fed: GameFederationDB, game_date: str):
        """Check if a PPV is scheduled for today."""
        from models.game_models import PPVEventDB
        return self.db.query(PPVEventDB).filter(
            PPVEventDB.federation_id == fed.id,
            PPVEventDB.scheduled_date == game_date,
            PPVEventDB.is_completed == False,
        ).first()

    def _npc_book_ppv_show(self, fed: GameFederationDB, ppv):
        """Book and create a PPV show from the PPV calendar."""
        show_svc = _get_show_service()
        ppv_capacity = ppv.capacity or 15000
        if not ppv.venue:
            from game_service.world_service import pick_venue
            ppv_venue = pick_venue(fed.home_region or "Northeast", ppv_capacity)
        else:
            ppv_venue = ppv.venue
        show = show_svc.create_show(
            self.db, self.world.id, fed.id,
            name=ppv.name,
            show_type="ppv",
            venue=ppv_venue,
            capacity=ppv_capacity,
            game_date=self.world.current_game_date,
        )
        ppv.show_id = show.id

        # Book the card using planned matches from PPV + vision
        segments = show_svc.npc_book_card(self.db, show, ppv_event=ppv)
        ppv.is_completed = True
        self.db.add(ppv)

        self.events.append(
            f"PPV: {ppv.name} ({len(segments)} matches, capacity {ppv.capacity})"
        )

    def _npc_book_weekly_show(self, fed: GameFederationDB):
        """NPC federation auto-books a weekly show, building toward next PPV."""
        show_svc = _get_show_service()

        # Check if we're in a PPV build window
        from game_service.ppv_calendar_service import get_next_ppv, is_build_window, is_go_home_week
        next_ppv = get_next_ppv(self.db, fed.id, self.world.current_game_date)

        show_name = f"{fed.short_name or fed.name} Weekly"
        if next_ppv and is_go_home_week(self.world.current_game_date, next_ppv.scheduled_date):
            if getattr(next_ppv, 'is_crown_jewel', False):
                show_name = f"{fed.short_name or fed.name} {next_ppv.name} Go-Home Special"
            else:
                show_name = f"{fed.short_name or fed.name} Go-Home Show"
        elif next_ppv and is_build_window(self.world.current_game_date, next_ppv.scheduled_date):
            if getattr(next_ppv, 'is_crown_jewel', False):
                show_name = f"Road to {next_ppv.name}"
            else:
                show_name = f"{fed.short_name or fed.name} Weekly (Building to {next_ppv.name})"

        weekly_cap = random.randint(2000, 10000)
        from game_service.world_service import pick_venue
        weekly_venue = pick_venue(fed.home_region or "Northeast", weekly_cap)
        show = show_svc.create_show(
            self.db, self.world.id, fed.id,
            name=show_name,
            show_type="weekly",
            venue=weekly_venue,
            capacity=weekly_cap,
            game_date=self.world.current_game_date,
        )
        segments = show_svc.npc_book_card(self.db, show, next_ppv=next_ppv)
        self.events.append(
            f"{fed.short_name or fed.name} airs weekly show ({len(segments)} matches)"
        )

    def _npc_vision_check(self, fed: GameFederationDB, game_date: str):
        """Weekly strategic check — plan PPV cards and adapt to hot/cold acts."""
        from models.game_models import BookingVisionDB, PPVEventDB
        from game_service.ppv_calendar_service import (
            get_next_ppv, is_build_window, plan_ppv_card_from_vision,
        )
        from game_service.booking_vision_service import (
            adapt_vision_for_hot_act, adapt_vision_for_cold_act,
        )

        vision = self.db.query(BookingVisionDB).filter(
            BookingVisionDB.federation_id == fed.id,
        ).first()
        if not vision:
            return

        # Plan upcoming PPV card if entering build window
        next_ppv = get_next_ppv(self.db, fed.id, game_date)
        if next_ppv and is_build_window(game_date, next_ppv.scheduled_date):
            # Only plan once (check if matches already penciled)
            if not next_ppv.planned_main_event and not next_ppv.planned_matches:
                plan_ppv_card_from_vision(self.db, next_ppv, vision)
                self.events.append(f"{fed.short_name}: PPV card planned for {next_ppv.name}")

        # Check for hot/cold acts — wrestlers whose popularity diverges from push tier
        from models.game_models import WrestlerPushDB
        pushes = self.db.query(WrestlerPushDB).filter(
            WrestlerPushDB.federation_id == fed.id,
        ).all()

        for push in pushes:
            wrestler = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id == push.wrestler_id,
            ).first()
            if not wrestler:
                continue

            # Hot act: popularity way above their tier
            tier_expectations = {
                "main_event": 70, "upper_midcard": 55,
                "midcard": 40, "lower_card": 25, "jobber": 15,
            }
            expected = tier_expectations.get(push.push_tier, 40)

            if wrestler.popularity > expected + 20 and push.direction != "rising":
                adapt_vision_for_hot_act(self.db, vision, wrestler.id, game_date)
            elif wrestler.popularity < expected - 15 and push.push_tier in ("main_event", "upper_midcard"):
                adapt_vision_for_cold_act(self.db, vision, wrestler.id, game_date)

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
        aftermath = _get_match_aftermath()

        fed = self.db.query(GameFederationDB).filter(
            GameFederationDB.id == show.federation_id
        ).first()

        prestige_factor = (fed.prestige if fed else 50) / 100

        # Simulate each match segment through the engine
        segments = self.db.query(ShowSegmentDB).filter(
            ShowSegmentDB.show_id == show.id,
        ).order_by(ShowSegmentDB.position).all()

        match_segments = [s for s in segments if s.segment_type == "match" and s.match_id]
        total_segments = len(match_segments)

        match_ratings = []
        # Show momentum flows between segments — hot crowd carries forward
        show_momentum = 50  # Neutral start
        for idx, seg in enumerate(segments):
            if seg.segment_type == "match" and seg.match_id:
                match = self.db.query(MatchDB).filter(
                    MatchDB.id == seg.match_id
                ).first()
                if match and not match.is_completed:
                    # Determine card position from segment index
                    match_idx = match_segments.index(seg)
                    if match_idx == 0:
                        card_position = "opener"
                    elif match_idx == total_segments - 1:
                        card_position = "main_event"
                    elif match_idx == total_segments - 2 and total_segments > 2:
                        card_position = "semifinal"
                    else:
                        card_position = "midcard"
                    match.card_position = card_position
                    match.game_date = show.game_date

                    # Pass show momentum to match engine
                    match._show_momentum = show_momentum

                    try:
                        result = me.simulate_match_from_db(self.db, match, game_date=show.game_date)
                        seg.is_completed = True
                        seg.rating = result.match_rating
                        seg.crowd_reaction = "pop" if result.crowd_heat > 60 else "mixed"
                        seg.actual_duration_minutes = result.duration_ticks
                        match_ratings.append(result.match_rating)

                        # Update show momentum from this match's crowd heat
                        # Good matches lift the crowd, bad ones cool them
                        if result.crowd_heat > 60:
                            show_momentum = min(80, show_momentum + 5)
                        elif result.crowd_heat < 35:
                            show_momentum = max(30, show_momentum - 5)

                        # Process post-match consequences
                        aftermath.process_match_aftermath(
                            self.db, match, self.world.current_game_date
                        )

                        # Process stable effects from match result
                        try:
                            stable_svc = _get_stable_service()
                            losers = [p.wrestler_id for p in self.db.query(MatchParticipantDB).filter(
                                MatchParticipantDB.match_id == match.id,
                                MatchParticipantDB.is_winner == False,
                            ).all()]
                            for loser_id in losers:
                                stable_svc.process_match_result_for_stables(
                                    self.db, result.winner_id, loser_id,
                                    self.world.id, self.world.current_game_date,
                                )
                        except (ValueError, AttributeError) as e:
                            logger.debug("Stable match processing skipped: %s", e)

                        # Log post-match angle if one occurred
                        if result.post_match_angle:
                            angle = result.post_match_angle
                            self._log_event(
                                angle["type"],
                                angle["description"],
                                angle.get("attacker_ids", []) + [angle.get("victim_id") or angle.get("saved_id", "")],
                                importance=7,
                            )
                            show_momentum = min(85, show_momentum + 8)  # Angles are hot

                        # Check for storyline triggers from match result
                        sl_svc.check_match_storyline_triggers(
                            self.db, match, self.world.current_game_date
                        )
                    except Exception as e:
                        logger.error(
                            "Match simulation failed for match %s: %s",
                            match.id, e, exc_info=True,
                        )
                        seg.is_completed = True
                        seg.rating = round(random.uniform(2.0, 4.0), 1)
                        match_ratings.append(seg.rating)
            elif seg.segment_type == "promo":
                seg.is_completed = True
                promo_rating = self._evaluate_promo_segment(seg, show)
                seg.rating = promo_rating
                # Good promos build show momentum
                if promo_rating >= 3.5:
                    show_momentum = min(80, show_momentum + 4)
                elif promo_rating < 2.0:
                    show_momentum = max(30, show_momentum - 3)

        # Calculate show overall rating
        show.is_completed = True
        card_bonus = self._calculate_card_psychology_bonus(match_ratings)

        if match_ratings:
            show.overall_rating = round(
                sum(match_ratings) / len(match_ratings) + card_bonus, 1
            )
        else:
            show.overall_rating = round(2.5 * prestige_factor, 1)

        # --- Viewership model ---
        vs = _get_viewership_service()
        card_draw = vs.calculate_card_draw(self.db, show)

        # Attendance & gate revenue
        attendance, ticket_price, gate = vs.calculate_attendance(
            self.db, show, fed, card_draw,
        )
        show.attendance = attendance
        show.gate_revenue = gate

        # TV rating (weekly shows only)
        if show.show_type == "weekly" and fed:
            show.tv_rating = vs.calculate_tv_rating(self.db, show, fed)

        # PPV buys
        if fed:
            fed.weekly_revenue += gate
            if show.show_type == "ppv":
                ppv_buys = vs.calculate_ppv_buys(self.db, show, fed, card_draw)
                show.ppv_buys = ppv_buys
                fed.weekly_revenue += ppv_buys * 49.99

        # Dynamic prestige adjustment based on show performance
        if fed:
            vs.update_federation_fanbase(self.db, fed, show)

        # Update wrestler draw ratings for everyone on the card
        for seg in segments:
            if seg.segment_type == "match" and seg.match_id:
                participants = self.db.query(MatchParticipantDB).filter(
                    MatchParticipantDB.match_id == seg.match_id
                ).all()
                for p in participants:
                    new_draw = vs.calculate_wrestler_draw(self.db, p.wrestler_id)
                    wrestler = self.db.query(GameWrestlerDB).filter(
                        GameWrestlerDB.id == p.wrestler_id
                    ).first()
                    if wrestler:
                        wrestler.draw_rating = round(new_draw, 1)

        # Generate news from show results
        try:
            news_svc = _get_news_service()
            news_svc.generate_show_news(self.db, show, match_ratings, fed)
        except Exception as e:
            logger.error("News generation failed for show %s: %s", show.id, e, exc_info=True)

        self._log_event(
            "show",
            f"{show.name} drew {attendance} fans, TV: {show.tv_rating} (Rating: {show.overall_rating})",
            [show.federation_id],
            importance=6,
        )
        self.events.append(f"Show completed: {show.name} ({attendance} attendance, TV: {show.tv_rating})")

    def _evaluate_promo_segment(self, seg: ShowSegmentDB, show: ShowDB) -> float:
        """Evaluate a promo segment rating using promo_service when a wrestler is identifiable."""
        from game_service.promo_service import _evaluate_promo_quality

        wrestler_id = None

        # Try to get wrestler from linked promo
        if seg.promo_id:
            promo = self.db.query(PromoDB).filter(PromoDB.id == seg.promo_id).first()
            if promo:
                # If the promo already has a quality rating, use it
                if promo.quality_rating is not None:
                    return round(promo.quality_rating, 1)
                wrestler_id = promo.wrestler_id

        if wrestler_id:
            stats = self.db.query(WrestlerStatsDB).filter(
                WrestlerStatsDB.wrestler_id == wrestler_id
            ).first()
            # Use a placeholder content string for template promos
            content = seg.description or "Generic promo segment"
            return _evaluate_promo_quality(stats, content, is_player=False)

        # No identifiable wrestler — fall back to random
        return round(random.uniform(2.0, 4.5), 1)

    def _calculate_card_psychology_bonus(self, ratings: list) -> float:
        """Calculate show rating bonus based on card flow."""
        if len(ratings) < 2:
            return 0.0

        bonus = 0.0

        # Good opener bonus
        if ratings[0] > 3.0:
            bonus += 0.2

        # Main event is highest rated
        if ratings[-1] == max(ratings):
            bonus += 0.3

        # Build: ratings generally increase toward main event
        if len(ratings) >= 3:
            mid_avg = sum(ratings[1:-1]) / len(ratings[1:-1])
            if ratings[-1] > mid_avg > ratings[0]:
                bonus += 0.2

        # Monotony penalty: all ratings within 0.5 of each other
        if max(ratings) - min(ratings) < 0.5 and len(ratings) >= 3:
            bonus -= 0.2

        return round(bonus, 1)

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
            # Storylines heat decays daily — unserviced storylines fade faster
            decay_chance = 0.3  # 30% chance per day (was 10%)
            decay_amount = 1
            if storyline.status == "climax":
                decay_chance = 0.5  # Climax storylines need constant fuel
                decay_amount = 2
            if random.random() < decay_chance:
                storyline.heat = max(0, storyline.heat - decay_amount)

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
        _get_news_service().generate_injury_news(
            self.db, self.world.id, victim, weeks_out, game_date,
        )

    def _random_retirement(self, game_date: str):
        """Pressure-based retirement (replaces flat random)."""
        from game_service.wrestler_lifecycle_service import calculate_retirement_pressure

        wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.age >= 34,
        ).all()

        for w in wrestlers:
            pressure = calculate_retirement_pressure(w)
            if pressure > 0 and random.random() < pressure / 1000:
                w.is_active = False
                w.retirement_date = game_date
                self._log_event(
                    "retirement",
                    f"{w.name} announces retirement after {w.experience_years} years",
                    [w.id],
                    importance=8,
                )
                self.events.append(f"RETIREMENT: {w.name}")
                break  # One retirement per day max

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
                fed = self.db.query(GameFederationDB).filter(
                    GameFederationDB.id == contract.federation_id
                ).first()
                fed_name = (fed.short_name or fed.name) if fed else "Unknown"
                self._log_event(
                    "contract_expired",
                    f"{wrestler.name}'s contract with {fed_name} has expired — now a free agent!",
                    [wrestler.id, contract.federation_id],
                    importance=6,
                )
                self.events.append(f"Contract expired: {wrestler.name} is now a free agent")

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
    # Phase 9: Morale processing
    # ------------------------------------------------------------------

    def _process_morale(self, game_date: str):
        """Update morale based on streaks, booking frequency, salary."""
        wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
            GameWrestlerDB.is_injured == False,
        ).all()

        for w in wrestlers:
            morale_change = 0

            # Losing streak penalty (3+ losses)
            if (w.win_streak or 0) <= -3:
                morale_change -= 5

            # Winning streak bonus (3+ wins)
            if (w.win_streak or 0) >= 3:
                morale_change += 3

            # Not booked recently
            if w.last_booked_date:
                days_since = self._days_between(w.last_booked_date, game_date)
                if days_since >= 14:
                    morale_change -= 3  # Feeling buried

            # Salary relative to popularity
            contract = self.db.query(ContractDB).filter(
                ContractDB.wrestler_id == w.id,
                ContractDB.status == "active",
            ).first()
            if contract and w.popularity > 60 and contract.salary_weekly < 1500:
                morale_change -= 2  # Underpaid

            if morale_change != 0:
                w.morale = max(0, min(100, w.morale + morale_change))

            # Very low morale: wrestler may request release
            if w.morale < 20 and w.is_npc and random.random() < 0.05:
                self._log_event(
                    "release_request",
                    f"{w.name} has requested their release (morale: {w.morale})",
                    [w.id], importance=7,
                )
                self.events.append(f"{w.name} requests release!")

    def _days_between(self, date1: str, date2: str) -> int:
        """Calculate days between two YYYY-MM-DD strings."""
        try:
            d1 = datetime.strptime(date1, "%Y-%m-%d")
            d2 = datetime.strptime(date2, "%Y-%m-%d")
            return abs((d2 - d1).days)
        except (ValueError, TypeError):
            return 0

    # ------------------------------------------------------------------
    # Tag team name generation
    # ------------------------------------------------------------------

    _TAG_TEAM_NAMES = {
        "power": [
            "The Wrecking Crew", "Heavy Artillery", "The Demolition Squad",
            "Iron Curtain", "The Juggernaut Express", "Total Destruction",
            "The War Machine", "Brute Force", "The Colossus Connection",
        ],
        "highflyer": [
            "Air Raid", "Terminal Velocity", "Sky High",
            "The Shooting Stars", "Double Vision", "The Aerials",
            "Freefall", "Altitude Sickness", "The High Wire",
        ],
        "technical": [
            "The Submission Squad", "Chain Reaction", "The Technicians",
            "Master Class", "Precision Strike", "The Chess Club",
            "Clinical Finish", "The Hold Exchange", "Mat Generals",
        ],
        "brawler": [
            "Street Justice", "The Pitfighters", "Knuckle Up",
            "Bar Room Blitz", "The Enforcers", "Concrete Justice",
            "The Roughnecks", "Violent Tendencies", "The Brawl Brothers",
        ],
        "mixed": [
            "Brains & Brawn", "The Odd Couple", "Chaos Theory",
            "Yin & Yang", "The Contrast", "Unlikely Alliance",
            "Controlled Chaos", "Thunder & Lightning", "The Paradox",
        ],
        "generic": [
            "The Alliance", "Double Trouble", "The Partnership",
            "Tandem", "The Foundation", "The Coalition",
            "Second Wind", "The Union", "Full Circle",
        ],
    }

    _TEAM_FINISHER_TEMPLATES = [
        "Double {move}", "The {adj} Bomb", "{adj} Annihilation",
        "Total {move}", "The Grand Finale", "Doomsday {move}",
        "Double Down", "The Crescendo", "Curtain Call",
    ]
    _FINISHER_MOVES = ["Powerbomb", "Suplex", "Slam", "Piledriver", "Cutter", "DDT"]
    _FINISHER_ADJS = ["Midnight", "Thunderous", "Final", "Atomic", "Devastating", "Crimson"]

    def _generate_tag_team_name(self, w1: "GameWrestlerDB", w2: "GameWrestlerDB") -> tuple:
        """Generate a creative tag team name and finisher based on wrestler styles."""
        from models.game_models import GimmickHistoryDB

        # Determine style category for each wrestler from stats
        stats1 = self.db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w1.id).first()
        stats2 = self.db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == w2.id).first()

        def _classify(stats):
            if not stats:
                return "generic"
            top = max(
                ("power", stats.power), ("highflyer", stats.aerial + stats.speed),
                ("technical", stats.technical + stats.submission),
                ("brawler", stats.brawling + stats.toughness),
                key=lambda x: x[1],
            )
            return top[0]

        cat1, cat2 = _classify(stats1), _classify(stats2)
        if cat1 == cat2:
            pool_key = cat1
        else:
            pool_key = "mixed"

        # Pick from pool, avoiding names already used in this world
        existing_names = {
            t.name for t in self.db.query(TagTeamDB).filter(
                TagTeamDB.world_id == self.world.id
            ).all()
        }
        pool = [n for n in self._TAG_TEAM_NAMES.get(pool_key, []) if n not in existing_names]
        if not pool:
            pool = [n for n in self._TAG_TEAM_NAMES["generic"] if n not in existing_names]
        if not pool:
            # Absolute fallback
            team_name = f"{w1.name} & {w2.name}"
        else:
            team_name = random.choice(pool)

        # Generate team finisher name
        template = random.choice(self._TEAM_FINISHER_TEMPLATES)
        finisher_name = template.format(
            move=random.choice(self._FINISHER_MOVES),
            adj=random.choice(self._FINISHER_ADJS),
        )

        return team_name, finisher_name

    # ------------------------------------------------------------------
    # Phase 10: Tag team management
    # ------------------------------------------------------------------

    def _manage_tag_teams(self, game_date: str):
        """NPC feds form/dissolve tag teams (Tuesdays)."""
        if get_day_of_week(game_date) != 1:  # Tuesday
            return

        npc_feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_npc == True,
            GameFederationDB.is_active == True,
        ).all()

        for fed in npc_feds:
            self._npc_form_tag_teams(fed, game_date)
            self._check_tag_team_dissolution(fed, game_date)

    def _npc_form_tag_teams(self, fed: GameFederationDB, game_date: str):
        """Form tag teams from wrestlers with high chemistry."""
        # Get roster
        contracts = self.db.query(ContractDB).filter(
            ContractDB.federation_id == fed.id,
            ContractDB.status == "active",
        ).all()
        wrestler_ids = [c.wrestler_id for c in contracts]

        if len(wrestler_ids) < 4:  # Need at least 4 for tag teams to make sense
            return

        # Check existing teams
        existing_teams = self.db.query(TagTeamDB).filter(
            TagTeamDB.world_id == self.world.id,
            TagTeamDB.is_active == True,
        ).all()
        teamed_ids = set()
        for t in existing_teams:
            teamed_ids.add(t.wrestler1_id)
            teamed_ids.add(t.wrestler2_id)

        # Look for high-chemistry pairs not already teamed
        relationships = self.db.query(WrestlerRelationshipDB).filter(
            WrestlerRelationshipDB.world_id == self.world.id,
            WrestlerRelationshipDB.matches_together >= 3,
            WrestlerRelationshipDB.chemistry_score >= 3.5,
        ).order_by(WrestlerRelationshipDB.chemistry_score.desc()).all()

        for rel in relationships:
            if rel.wrestler1_id in teamed_ids or rel.wrestler2_id in teamed_ids:
                continue
            if rel.wrestler1_id not in wrestler_ids or rel.wrestler2_id not in wrestler_ids:
                continue

            # Check compatible alignment
            w1 = self.db.query(GameWrestlerDB).filter(GameWrestlerDB.id == rel.wrestler1_id).first()
            w2 = self.db.query(GameWrestlerDB).filter(GameWrestlerDB.id == rel.wrestler2_id).first()
            if not w1 or not w2 or w1.is_injured or w2.is_injured:
                continue
            if w1.alignment != w2.alignment and "tweener" not in (w1.alignment, w2.alignment):
                continue

            team_name, finisher_name = self._generate_tag_team_name(w1, w2)
            self.db.add(TagTeamDB(
                world_id=self.world.id,
                name=team_name,
                team_finisher_name=finisher_name,
                wrestler1_id=rel.wrestler1_id,
                wrestler2_id=rel.wrestler2_id,
                formed_date=game_date,
            ))
            teamed_ids.add(rel.wrestler1_id)
            teamed_ids.add(rel.wrestler2_id)
            self._log_event(
                "tag_team_formed",
                f"{team_name} have formed a tag team!",
                [rel.wrestler1_id, rel.wrestler2_id], importance=6,
            )
            self.events.append(f"New tag team: {team_name}")
            break  # One new team per week per fed max

    def _check_tag_team_dissolution(self, fed: GameFederationDB, game_date: str):
        """Dissolve tag teams where members have diverged."""
        teams = self.db.query(TagTeamDB).filter(
            TagTeamDB.world_id == self.world.id,
            TagTeamDB.is_active == True,
        ).all()

        for team in teams:
            w1 = self.db.query(GameWrestlerDB).filter(GameWrestlerDB.id == team.wrestler1_id).first()
            w2 = self.db.query(GameWrestlerDB).filter(GameWrestlerDB.id == team.wrestler2_id).first()
            if not w1 or not w2:
                continue

            dissolve = False
            # Different alignments (after a turn)
            if w1.alignment != w2.alignment and "tweener" not in (w1.alignment, w2.alignment):
                dissolve = True
            # One member injured for 8+ weeks
            if w1.is_injured and w1.injury_return_date:
                weeks_out = self._days_between(game_date, w1.injury_return_date) / 7
                if weeks_out > 8:
                    dissolve = True
            if w2.is_injured and w2.injury_return_date:
                weeks_out = self._days_between(game_date, w2.injury_return_date) / 7
                if weeks_out > 8:
                    dissolve = True

            if dissolve:
                team.is_active = False
                team.dissolved_date = game_date
                self._log_event(
                    "tag_team_dissolved",
                    f"{team.name} have disbanded!",
                    [team.wrestler1_id, team.wrestler2_id], importance=6,
                )
                self.events.append(f"Tag team split: {team.name}")

    # ------------------------------------------------------------------
    # Phase 11: Inter-federation dynamics
    # ------------------------------------------------------------------

    def _inter_federation_dynamics(self, game_date: str):
        """Market share, talent poaching, federation momentum."""
        # Daily: update federation momentum
        self._update_federation_momentum(game_date)

        # Weekly (Sundays): market share redistribution and talent offers
        if get_day_of_week(game_date) == 6:
            self._redistribute_market_share()
            self._process_talent_offers(game_date)
            self._generate_talent_offers(game_date)
            self._adjust_tv_deals()

    def _update_federation_momentum(self, game_date: str):
        """Daily federation momentum adjustment."""
        feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_active == True,
        ).all()

        for fed in feds:
            momentum = fed.momentum or 50

            # Recent show quality (check last show)
            last_show = self.db.query(ShowDB).filter(
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
            contracts = self.db.query(ContractDB).filter(
                ContractDB.federation_id == fed.id,
                ContractDB.status == "active",
            ).all()
            if contracts:
                wrestler_ids = [c.wrestler_id for c in contracts]
                wrestlers = self.db.query(GameWrestlerDB).filter(
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

    def _redistribute_market_share(self):
        """Redistribute market share based on momentum and show quality."""
        feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
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

    def _generate_talent_offers(self, game_date: str):
        """NPC feds make talent offers to rivals' wrestlers."""
        npc_feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_npc == True,
            GameFederationDB.is_active == True,
            GameFederationDB.budget > 50000,
        ).all()

        for fed in npc_feds:
            if random.random() > 0.15:  # 15% chance per week
                continue

            # Find targets: popular wrestlers from other feds with low morale
            targets = self.db.query(GameWrestlerDB).join(ContractDB).filter(
                GameWrestlerDB.world_id == self.world.id,
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
            existing = self.db.query(TalentOfferDB).filter(
                TalentOfferDB.wrestler_id == target.id,
                TalentOfferDB.status == "pending",
            ).first()
            if existing:
                continue

            salary = max(1500, target.popularity * 30 + random.randint(-500, 500))
            expires = advance_game_date(game_date, 14)

            self.db.add(TalentOfferDB(
                world_id=self.world.id,
                federation_id=fed.id,
                wrestler_id=target.id,
                salary_offered=salary,
                contract_length_weeks=52,
                offered_date=game_date,
                expires_date=expires,
            ))
            self._log_event(
                "talent_offer",
                f"{fed.short_name or fed.name} makes an offer to {target.name}",
                [fed.id, target.id], importance=5,
            )

    def _process_talent_offers(self, game_date: str):
        """Process pending talent offers — NPC wrestlers decide."""
        offers = self.db.query(TalentOfferDB).filter(
            TalentOfferDB.world_id == self.world.id,
            TalentOfferDB.status == "pending",
        ).all()

        for offer in offers:
            # Expired?
            if offer.expires_date and offer.expires_date <= game_date:
                offer.status = "expired"
                continue

            wrestler = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id == offer.wrestler_id
            ).first()
            if not wrestler or not wrestler.is_npc:
                continue

            # Current contract
            current = self.db.query(ContractDB).filter(
                ContractDB.wrestler_id == wrestler.id,
                ContractDB.status == "active",
            ).first()

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
                    world_id=self.world.id,
                    wrestler_id=wrestler.id,
                    federation_id=offer.federation_id,
                    salary_weekly=offer.salary_offered,
                    start_date=game_date,
                    is_exclusive=True,
                )
                self.db.add(new_contract)
                offer.status = "accepted"

                fed = self.db.query(GameFederationDB).filter(
                    GameFederationDB.id == offer.federation_id
                ).first()
                fed_name = fed.short_name or fed.name if fed else "Unknown"
                self._log_event(
                    "talent_signing",
                    f"BREAKING: {wrestler.name} signs with {fed_name}!",
                    [wrestler.id, offer.federation_id], importance=8,
                )
                self.events.append(f"{wrestler.name} signs with {fed_name}!")
                _get_news_service().generate_signing_news(
                    self.db, self.world.id, wrestler.name, fed_name, game_date,
                )

                # Momentum shifts
                if fed:
                    fed.momentum = min(100, (fed.momentum or 50) + 3)
            else:
                offer.status = "rejected"

    def _adjust_tv_deals(self):
        """Quarterly TV deal adjustments based on performance."""
        # Only adjust on first Sunday of each quarter-ish (every ~13 weeks)
        if self.world.current_tick % 91 != 0:
            return

        feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
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

    # ------------------------------------------------------------------
    # Phase 12: Weekly news
    # ------------------------------------------------------------------

    def _generate_weekly_news(self, game_date: str):
        """Generate weekly dirt sheet news on Sundays."""
        if get_day_of_week(game_date) != 6:  # Sunday
            return
        try:
            news_svc = _get_news_service()
            news_svc.generate_weekly_dirt_sheet(self.db, self.world.id, game_date)
        except Exception as e:
            logger.error("Weekly news generation failed: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Phase 13: Wrestler lifecycle (Groups 1-6)
    # ------------------------------------------------------------------

    def _wrestler_lifecycle(self, game_date: str):
        """All wrestler lifecycle processing — aging, goals, politics, etc."""
        from game_service.wrestler_lifecycle_service import (
            age_wrestlers, evaluate_goals, create_wrestler_goals,
            update_locker_room_dynamics, auto_assign_mentors,
            hall_of_fame_ceremony, update_conditioning,
            apply_nostalgia_pop,
        )

        # --- Annual events ---
        # Jan 1: Age all wrestlers (Group 1) + PPV calendar rollover
        if game_date.endswith("-01-01"):
            age_wrestlers(self.db, self.world.id, game_date)
            self.events.append("Annual aging applied to all wrestlers")

            # Generate next year's PPV calendars for all active federations
            from game_service.ppv_calendar_service import rollover_ppv_calendar
            all_feds = self.db.query(GameFederationDB).filter(
                GameFederationDB.world_id == self.world.id,
                GameFederationDB.is_active == True,
            ).all()
            for fed in all_feds:
                new_ppvs = rollover_ppv_calendar(self.db, fed, game_date)
                if new_ppvs:
                    self.events.append(
                        f"{fed.short_name or fed.name}: {len(new_ppvs)} PPVs scheduled for new year"
                    )

        # April 1: Hall of Fame ceremony (Group 5)
        if game_date.endswith("-04-01"):
            inductee = hall_of_fame_ceremony(self.db, self.world.id, game_date)
            if inductee:
                self.events.append(f"HALL OF FAME: {inductee.name} inducted!")

        # --- Quarterly seasonal events ---
        # Q1 (Jan): New Year's Resolution — wrestlers with unmet goals get morale boost
        if game_date.endswith("-01-07"):
            self._seasonal_new_year_resolution(game_date)

        # Q2 (June): King of the Ring tournament
        if game_date.endswith("-06-01"):
            self._seasonal_king_of_the_ring(game_date)

        # Q3 (Jul-Sep): Summer Slam month — attendance boost
        month = game_date[5:7]
        if month in ("07", "08") and get_day_of_week(game_date) == 0:
            # Summer boost: all federations get a momentum nudge
            npc_feds = self.db.query(GameFederationDB).filter(
                GameFederationDB.world_id == self.world.id,
                GameFederationDB.is_active == True,
            ).all()
            for fed in npc_feds:
                old_m = fed.momentum or 50
                fed.momentum = min(100, old_m + 2)

        # Dec 31: Year-end summary and awards
        if game_date.endswith("-12-31"):
            self._generate_year_end_summary(game_date)

        # --- Weekly events (Thursdays) ---
        if get_day_of_week(game_date) == 3:
            # Goal evaluation (Group 2)
            wrestlers = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.world_id == self.world.id,
                GameWrestlerDB.is_active == True,
            ).all()
            for w in wrestlers:
                # Ensure goals are created
                create_wrestler_goals(self.db, w, game_date)
                completed = evaluate_goals(self.db, w, game_date)
                for g in completed:
                    self.events.append(f"{w.name} achieved: {g}")

            # Locker room dynamics (Group 3)
            npc_feds = self.db.query(GameFederationDB).filter(
                GameFederationDB.world_id == self.world.id,
                GameFederationDB.is_active == True,
            ).all()
            for fed in npc_feds:
                update_locker_room_dynamics(self.db, fed, game_date)

            # Auto-assign mentors (Group 4)
            for fed in npc_feds:
                if fed.is_npc:
                    auto_assign_mentors(self.db, fed, game_date)

            # Conditioning cycle (Group 6)
            for w in wrestlers:
                update_conditioning(self.db, w, game_date)

        # --- Daily: ring rust tracking (Group 1) ---
        active = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
        ).all()
        for w in active:
            if w.last_booked_date:
                try:
                    days = self._days_between(w.last_booked_date, game_date)
                    w.ring_rust_days = days
                except (ValueError, TypeError):
                    pass

        # --- Daily: nostalgia pop on return from long absence (Group 5) ---
        for w in active:
            if w.last_booked_date and w.ring_rust_days and w.ring_rust_days > 90:
                if (w.legacy_score or 0) >= 30:
                    # Only apply once per return (when they get booked again,
                    # ring_rust_days resets)
                    pass  # Pop applied in match_aftermath when booked

    # ------------------------------------------------------------------
    # Phase 14: Persona & Social Media (Group 7)
    # ------------------------------------------------------------------

    def _persona_tick(self, game_date: str):
        """Persona duality processing: gimmick evolution, life events, social media."""
        # Weekly persona tick on Fridays
        if get_day_of_week(game_date) == 4:  # Friday
            try:
                from game_service.wrestler_lifecycle_service import tick_persona
                tick_persona(self.db, self.world.id, game_date)
                self.events.append("Persona lifecycle tick processed")
            except Exception as e:
                logger.error("Persona tick failed: %s", e, exc_info=True)

            # Check for worked-shoot storylines from life events
            try:
                from game_service.storyline_service import (
                    check_life_event_storylines,
                    check_relationship_collision_storylines,
                )
                ws_storylines = check_life_event_storylines(
                    self.db, self.world.id, game_date
                )
                for sl in ws_storylines:
                    self.events.append(f"Worked-shoot storyline '{sl.name}' created!")

                coll_storylines = check_relationship_collision_storylines(
                    self.db, self.world.id, game_date
                )
                for sl in coll_storylines:
                    self.events.append(f"Collision storyline '{sl.name}' created!")
            except Exception as e:
                logger.error("Kayfabe collision check failed: %s", e, exc_info=True)

        # Daily social media tick
        try:
            from game_service import social_media_service
            social_media_service.tick_social_media(
                self.db, self.world.id, game_date
            )
        except Exception as e:
            logger.error("Social media tick failed: %s", e, exc_info=True)

    def _stable_dynamics_tick(self, game_date: str):
        """Process internal faction politics for all active stables.

        Runs on Wednesdays and Saturdays — two chances per week for
        loyalty drift, influence jockeying, and auto-generated drama.
        """
        day_of_week = get_day_of_week(game_date)
        if day_of_week not in (2, 5):  # Wednesday, Saturday
            return

        try:
            stable_svc = _get_stable_service()
            from models.game_models import StableDB
            stables = self.db.query(StableDB).filter_by(
                world_id=self.world.id, is_active=True
            ).all()
            for stable in stables:
                stable_svc.tick_stable_dynamics(self.db, stable, game_date)
            if stables:
                self.events.append(f"Faction dynamics processed for {len(stables)} stable(s)")
        except Exception as e:
            logger.error("Stable dynamics tick failed: %s", e, exc_info=True)

    def _manager_tick(self, game_date: str):
        """Track manager effectiveness and bond evolution.

        Runs on Thursdays — manager bonds slowly grow in effectiveness
        as the pairing builds chemistry.
        """
        if get_day_of_week(game_date) != 3:  # Thursday
            return

        try:
            from models.game_models import ManagerClientDB
            bonds = self.db.query(ManagerClientDB).filter_by(
                world_id=self.world.id, is_active=True
            ).all()
            for bond in bonds:
                # Effectiveness slowly grows over time (chemistry building)
                if bond.effectiveness < 90:
                    bond.effectiveness = min(100, bond.effectiveness + 1)
                # Recalculate bonuses as effectiveness grows
                if bond.effectiveness > 70:
                    bond.charisma_bonus = min(20, bond.charisma_bonus + 1)
                    bond.heat_bonus = min(20, bond.heat_bonus + 1)
            if bonds:
                self.events.append(f"Manager bonds updated for {len(bonds)} pairing(s)")
        except Exception as e:
            logger.error("Manager tick failed: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Seasonal events
    # ------------------------------------------------------------------

    def _seasonal_new_year_resolution(self, game_date: str):
        """Q1 event: Wrestlers with unmet goals get a fresh-start morale boost."""
        wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
        ).all()

        boosted = 0
        for w in wrestlers:
            if (w.morale or 50) < 60:
                w.morale = min(100, (w.morale or 50) + 5)
                boosted += 1

        if boosted:
            self._log_event(
                "seasonal_event",
                f"New Year's Resolution: {boosted} wrestlers start the year with renewed motivation!",
                importance=5,
            )
            self.events.append(f"New Year's Resolution: {boosted} wrestlers got a morale boost")

    def _seasonal_king_of_the_ring(self, game_date: str):
        """Q2 event: King of the Ring tournament across all NPC feds.

        Picks top 8 by popularity per federation, announces a tournament via
        narrative log, and crowns a winner with +10 popularity.
        """
        npc_feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_npc == True,
            GameFederationDB.is_active == True,
        ).all()

        for fed in npc_feds:
            contracts = self.db.query(ContractDB).filter(
                ContractDB.federation_id == fed.id,
                ContractDB.status == "active",
            ).all()
            wrestler_ids = [c.wrestler_id for c in contracts]
            wrestlers = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id.in_(wrestler_ids),
                GameWrestlerDB.is_active == True,
                GameWrestlerDB.is_injured == False,
            ).order_by(GameWrestlerDB.popularity.desc()).limit(8).all()

            if len(wrestlers) < 4:
                continue

            # Simulate single-elimination tournament (simplified)
            bracket = list(wrestlers)
            round_num = 1
            while len(bracket) > 1:
                next_round = []
                for i in range(0, len(bracket) - 1, 2):
                    w1, w2 = bracket[i], bracket[i + 1]
                    # Higher popularity + randomness wins
                    w1_score = w1.popularity + random.randint(-20, 20)
                    w2_score = w2.popularity + random.randint(-20, 20)
                    winner = w1 if w1_score >= w2_score else w2
                    next_round.append(winner)
                # Handle odd bracket
                if len(bracket) % 2 == 1:
                    next_round.append(bracket[-1])
                bracket = next_round
                round_num += 1

            king = bracket[0]
            old_pop = king.popularity
            king.popularity = min(100, king.popularity + 10)

            self._log_event(
                "seasonal_event",
                f"KING OF THE RING: {king.name} wins the {fed.short_name or fed.name} "
                f"King of the Ring tournament! (Pop {old_pop} → {king.popularity})",
                [king.id], importance=8,
            )
            self.events.append(
                f"King of the Ring: {king.name} crowned in {fed.short_name or fed.name}!"
            )

    # ------------------------------------------------------------------
    # Year-end summary
    # ------------------------------------------------------------------

    def _generate_year_end_summary(self, game_date: str):
        """Generate year-end awards and summary news. Fires on Dec 31."""
        news_svc = _get_news_service()
        year = game_date[:4]

        # Find all completed shows this year
        year_start = f"{year}-01-01"
        shows = self.db.query(ShowDB).filter(
            ShowDB.world_id == self.world.id,
            ShowDB.is_completed == True,
            ShowDB.game_date >= year_start,
            ShowDB.game_date <= game_date,
        ).all()

        # Best show of the year
        best_show = max(shows, key=lambda s: s.overall_rating or 0) if shows else None

        # Most popular wrestler (current popularity)
        wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.is_active == True,
        ).order_by(GameWrestlerDB.popularity.desc()).all()
        wrestler_of_year = wrestlers[0] if wrestlers else None

        # Best match of the year
        best_match = self.db.query(MatchDB).filter(
            MatchDB.world_id == self.world.id,
            MatchDB.is_completed == True,
            MatchDB.match_rating != None,
            MatchDB.game_date >= year_start,
        ).order_by(MatchDB.match_rating.desc()).first()

        # Most dominant (highest win count)
        from sqlalchemy import func
        win_counts = (
            self.db.query(
                MatchParticipantDB.wrestler_id,
                func.count(MatchParticipantDB.id).label("wins"),
            )
            .join(MatchDB)
            .filter(
                MatchParticipantDB.is_winner == True,
                MatchDB.is_completed == True,
                MatchDB.game_date >= year_start,
                MatchDB.game_date <= game_date,
            )
            .group_by(MatchParticipantDB.wrestler_id)
            .order_by(func.count(MatchParticipantDB.id).desc())
            .first()
        )

        most_wins_wrestler = None
        most_wins_count = 0
        if win_counts:
            most_wins_wrestler = self.db.query(GameWrestlerDB).filter(
                GameWrestlerDB.id == win_counts[0]
            ).first()
            most_wins_count = win_counts[1]

        # Federation of the year (highest momentum)
        feds = self.db.query(GameFederationDB).filter(
            GameFederationDB.world_id == self.world.id,
            GameFederationDB.is_active == True,
        ).order_by(GameFederationDB.momentum.desc()).all()
        fed_of_year = feds[0] if feds else None

        # Build summary
        awards = []
        if wrestler_of_year:
            awards.append(f"Wrestler of the Year: {wrestler_of_year.name} (Popularity: {wrestler_of_year.popularity})")
        if best_show:
            fed = self.db.query(GameFederationDB).filter(
                GameFederationDB.id == best_show.federation_id
            ).first()
            fed_name = (fed.short_name or fed.name) if fed else "Unknown"
            awards.append(f"Show of the Year: {best_show.name} by {fed_name} ({best_show.overall_rating:.1f} stars)")
        if best_match and best_match.match_rating:
            awards.append(f"Match of the Year: {best_match.match_rating:.1f}-star classic")
        if most_wins_wrestler:
            awards.append(f"Most Dominant: {most_wins_wrestler.name} ({most_wins_count} wins)")
        if fed_of_year:
            awards.append(f"Federation of the Year: {fed_of_year.short_name or fed_of_year.name} (Momentum: {fed_of_year.momentum})")

        summary = f"YEAR IN REVIEW {year}\n" + "\n".join(f"  - {a}" for a in awards)

        self._log_event(
            "year_end_awards",
            summary,
            [],
            importance=10,
        )

        # Generate news article
        self.db.add(WorldNewsDB(
            world_id=self.world.id,
            headline=f"YEAR IN REVIEW: The {year} Wrestling Awards!",
            body="\n\n".join(awards),
            category="year_end",
            game_date=game_date,
            is_kayfabe=False,
            source="Wrestling Observer Year-End Issue",
        ))

        self.events.append(f"Year-end awards generated for {year}")
        for award in awards:
            self.events.append(f"AWARD: {award}")

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
