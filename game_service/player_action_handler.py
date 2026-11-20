"""
Player Action Handler — extracted from WorldTicker.

Contains all _action_* methods and the dispatch logic for processing
player-submitted actions (sign wrestler, book show, train, cut promo,
stable/manager/storyline management, match requests, etc.).
"""

import logging
import math
import random
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from models.game_models import (
    WorldDB, PlayerActionDB, GameWrestlerDB,
    WrestlerStatsDB, ContractDB, ShowDB, StorylineDB,
    GameFederationDB, PlayerDB, StableDB, ManagerDB, ManagerClientDB,
)

logger = logging.getLogger(__name__)

# Lazy imports (same pattern as world_ticker) to avoid circular deps
_storyline_service = None
_stable_service = None
_manager_service = None


def _get_storyline_service():
    global _storyline_service
    if _storyline_service is None:
        from game_service import storyline_service as _sls
        _storyline_service = _sls
    return _storyline_service


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


# -----------------------------------------------------------------
# DRY helper for the repeated active-contract query
# -----------------------------------------------------------------

def get_active_contract(db: Session, wrestler_id: str, world_id: str = None):
    """Return the active ContractDB for a wrestler, or None."""
    query = db.query(ContractDB).filter(
        ContractDB.wrestler_id == wrestler_id,
        ContractDB.status == "active",
    )
    if world_id is not None:
        query = query.filter(ContractDB.world_id == world_id)
    return query.first()


def get_signing_salary(data: dict) -> float:
    error = "salary_weekly must be a finite, non-negative number"
    try:
        salary = float(data.get("salary_weekly", 1000))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(error) from exc
    if not math.isfinite(salary) or salary < 0:
        raise ValueError(error)
    return salary


# -----------------------------------------------------------------
# PlayerActionHandler
# -----------------------------------------------------------------

class PlayerActionHandler:
    """Handles player-submitted actions during the tick.

    Parameters
    ----------
    db : Session
        SQLAlchemy session.
    world : WorldDB
        The current game world being ticked.
    log_event : callable
        Callback with signature (event_type, description, involved, importance)
        used to persist narrative log entries.  Typically ``WorldTicker._log_event``.
    """

    def __init__(self, db: Session, world: WorldDB, log_event: Callable):
        self.db = db
        self.world = world
        self._log_event = log_event

    # ---- dispatch ------------------------------------------------

    def validate(self, action: PlayerActionDB):
        """Validate every referenced entity before any handler can mutate state."""
        if action.world_id is not None and action.world_id != self.world.id:
            raise ValueError("Action not found in this world")
        data = action.action_data
        fields = {
            "sign_wrestler": ("wrestler_id", "federation_id"),
            "book_show": ("federation_id",),
            "train": ("wrestler_id",),
            "cut_promo": ("wrestler_id", "target_wrestler_id"),
            "request_match": ("wrestler_id",),
            "open_challenge": ("wrestler_id",),
            "form_stable": ("leader_id", "founding_member_ids", "manager_id"),
            "join_stable": ("stable_id", "wrestler_id"),
            "leave_stable": ("stable_id", "wrestler_id"),
            "dissolve_stable": ("stable_id",),
            "assign_manager": ("manager_id", "client_wrestler_id"),
            "create_manager": ("federation_id",),
            "remove_manager": ("bond_id",),
            "create_storyline": ("wrestler_ids", "federation_id"),
            "advance_storyline": ("storyline_id",),
        }.get(action.action_type)
        if fields is None:
            return
        personal_actions = ("train", "cut_promo", "request_match", "open_challenge")
        player = None
        if action.player_id is not None:
            player = self.db.query(PlayerDB).filter_by(id=action.player_id, world_id=self.world.id).first()
            if player is None:
                raise ValueError("Player not found in this world")
            if action.action_type in personal_actions:
                if player.player_type != "wrestler":
                    raise ValueError("You do not control this wrestler")
            elif player.player_type != "promoter":
                raise ValueError("You do not control this federation")
        models = {
            "wrestler_id": (GameWrestlerDB, "Wrestler"),
            "target_wrestler_id": (GameWrestlerDB, "Wrestler"),
            "leader_id": (GameWrestlerDB, "Wrestler"),
            "founding_member_ids": (GameWrestlerDB, "Wrestler"),
            "wrestler_ids": (GameWrestlerDB, "Wrestler"),
            "client_wrestler_id": (GameWrestlerDB, "Wrestler"),
            "federation_id": (GameFederationDB, "Federation"),
            "stable_id": (StableDB, "Stable"),
            "manager_id": (ManagerDB, "Manager"),
            "bond_id": (ManagerClientDB, "Bond"),
            "storyline_id": (StorylineDB, "Storyline"),
        }
        entities = {}
        for field in fields:
            value = data.get(field)
            if value is None:
                continue
            model, label = models[field]
            ids = set(value) if field in ("founding_member_ids", "wrestler_ids") else {value}
            targets = self.db.query(model).filter(model.id.in_(ids), model.world_id == self.world.id).all() if ids else []
            if len(targets) != len(ids):
                raise ValueError(f"{label} not found in this world")
            entities[field] = targets

        # Calls without a player are also used by trusted in-process services.
        if player is None:
            return
        if action.action_type in personal_actions:
            wrestler_id = data.get("wrestler_id")
            if player.player_type != "wrestler" or player.wrestler_id != wrestler_id:
                raise ValueError("You do not control this wrestler")
        else:
            # Preserve duplicate-signing rejection before checking the destination.
            if action.action_type == "sign_wrestler" and get_active_contract(
                self.db, data.get("wrestler_id"),
            ):
                raise ValueError("Wrestler already under contract")
            federation_ids = set()
            roster_ids = set()
            for field, targets in entities.items():
                for target in targets:
                    if field == "federation_id":
                        federation_ids.add(target.id)
                    elif hasattr(target, "federation_id") and target.federation_id:
                        federation_ids.add(target.federation_id)
                    elif isinstance(target, ManagerClientDB):
                        manager = self.db.query(ManagerDB).filter_by(
                            id=target.manager_id, world_id=self.world.id,
                        ).first()
                        if manager is None:
                            raise ValueError("Manager not found in this world")
                        if manager.federation_id:
                            federation_ids.add(manager.federation_id)
                    elif isinstance(target, GameWrestlerDB) and action.action_type != "sign_wrestler":
                        roster_ids.add(target.id)
            if roster_ids:
                contracts = self.db.query(ContractDB).filter(
                    ContractDB.wrestler_id.in_(roster_ids),
                    ContractDB.world_id == self.world.id,
                    ContractDB.status == "active",
                ).all()
                federation_ids.update(contract.federation_id for contract in contracts)
            if player.player_type != "promoter" or any(fed != player.federation_id for fed in federation_ids):
                raise ValueError("You do not control this federation")

    def execute(self, action: PlayerActionDB) -> dict:
        """Execute a single player action.  Returns result dict."""
        self.validate(action)
        action_type = action.action_type
        data = action.action_data

        dispatch = {
            "sign_wrestler": self._action_sign_wrestler,
            "book_show": self._action_book_show,
            "train": self._action_train,
            "cut_promo": self._action_cut_promo,
            "form_stable": self._action_form_stable,
            "join_stable": self._action_join_stable,
            "leave_stable": self._action_leave_stable,
            "dissolve_stable": self._action_dissolve_stable,
            "assign_manager": self._action_assign_manager,
            "create_manager": self._action_create_manager,
            "remove_manager": self._action_remove_manager,
            "create_storyline": self._action_create_storyline,
            "advance_storyline": self._action_advance_storyline,
            "request_match": self._action_request_match,
            "open_challenge": self._action_open_challenge,
        }

        handler = dispatch.get(action_type)
        if handler:
            return handler(data)
        return {"message": f"Action '{action_type}' acknowledged"}

    # ---- individual action handlers ------------------------------

    def _action_sign_wrestler(self, data: dict) -> dict:
        """Promoter signs a free agent."""
        wrestler_id = data.get("wrestler_id")
        federation_id = data.get("federation_id")
        salary = get_signing_salary(data)

        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id,
            GameWrestlerDB.world_id == self.world.id,
        ).first()
        if not wrestler:
            raise ValueError("Wrestler not found")

        # Check not already signed
        active_contract = get_active_contract(self.db, wrestler_id)
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
        self.db.flush()
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
        ).join(GameWrestlerDB, GameWrestlerDB.id == WrestlerStatsDB.wrestler_id).filter(
            GameWrestlerDB.world_id == self.world.id,
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
        """Wrestler cuts a promo -- gains popularity, boosts storyline heat."""
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
            existing = sl_svc._find_storyline_between(self.db, wrestler_id, target_id, self.world.id)
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
        contract = get_active_contract(self.db, wrestler_id, self.world.id)
        if not contract:
            raise ValueError("Wrestler has no active contract")

        # Store the request in world metadata for the show booking phase to pick up
        meta = dict(self.world.world_config or {})
        match_requests = meta.get("pending_match_requests", [])

        # Check cooldown -- only 1 request per 7 days
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
        """Player issues an open challenge -- higher risk/reward than request_match.

        Matched against someone +/-10 popularity. Win = +4-6 pop, Loss = +0.
        Can spark a storyline if player popularity > 40.
        """
        wrestler_id = data.get("wrestler_id")
        wrestler = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == wrestler_id
        ).first()
        if not wrestler:
            raise ValueError("Wrestler not found")

        contract = get_active_contract(self.db, wrestler_id, self.world.id)
        if not contract:
            raise ValueError("Wrestler has no active contract")

        # Find a suitable opponent: +/-10 popularity from same federation
        roster_contracts = self.db.query(ContractDB).filter(
            ContractDB.world_id == self.world.id,
            ContractDB.federation_id == contract.federation_id,
            ContractDB.status == "active",
            ContractDB.wrestler_id != wrestler_id,
        ).all()

        roster_wrestlers = self.db.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == self.world.id,
            GameWrestlerDB.id.in_([c.wrestler_id for c in roster_contracts]),
            GameWrestlerDB.is_injured.is_(False),
        ).all()

        candidates = [
            opp for opp in roster_wrestlers
            if abs(opp.popularity - wrestler.popularity) <= 15
        ]

        if not candidates:
            # Fallback: anyone on the roster who isn't injured
            candidates = list(roster_wrestlers)

        if not candidates:
            return {"message": "No suitable opponents available for an open challenge"}

        opponent = random.choice(candidates)

        # Store in metadata for show booking
        meta = dict(self.world.world_config or {})
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
        contract = get_active_contract(self.db, leader_id, self.world.id)
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
        return {"member_id": member.id, "role": member.role,
                "wrestler_name": wrestler.name if wrestler else wrestler_id}

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
            contract = get_active_contract(self.db, wrestler_ids[0], self.world.id)
            federation_id = contract.federation_id if contract else None
        storyline = sl_svc.create_storyline(
            self.db, self.world.id, federation_id,
            wrestler_ids=wrestler_ids,
            storyline_type=data.get("storyline_type", "feud"),
            name=data.get("name"),
            description=data.get("description"),
            game_date=self.world.current_game_date,
        )
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
