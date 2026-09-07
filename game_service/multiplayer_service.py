"""
Multi-Player Service — federation-scoped ownership and conflict resolution.

Allows multiple users to each control their own federation in the same
world.  When two players issue conflicting actions in the same tick
(e.g., both try to sign the same free-agent), the conflict resolver
determines the outcome.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Federation ownership mapping
# ---------------------------------------------------------------------------


def assign_federation_owner(
    db: Session,
    world_id: str,
    federation_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Assign a user as the controller of a federation in a world."""
    from models.game_models import GameFederationDB

    fed = (
        db.query(GameFederationDB)
        .filter(
            GameFederationDB.id == federation_id,
            GameFederationDB.world_id == world_id,
        )
        .first()
    )
    if fed is None:
        raise ValueError(f"Federation {federation_id} not found in world {world_id}")

    current_owner = getattr(fed, "owner_user_id", None)
    if current_owner and current_owner != user_id:
        raise ValueError(
            f"Federation {federation_id} is already owned by user {current_owner}"
        )

    fed.owner_user_id = user_id
    db.commit()

    logger.info(
        "User %s assigned as owner of federation %s in world %s",
        user_id,
        federation_id,
        world_id,
    )
    return {
        "federation_id": federation_id,
        "owner_user_id": user_id,
        "federation_name": fed.name,
    }


def get_user_federations(
    db: Session,
    world_id: str,
    user_id: str,
) -> List[Dict[str, Any]]:
    """Return all federations a user controls in a given world."""
    from models.game_models import GameFederationDB

    feds = (
        db.query(GameFederationDB)
        .filter(
            GameFederationDB.world_id == world_id,
            GameFederationDB.owner_user_id == user_id,
        )
        .all()
    )

    return [
        {
            "federation_id": f.id,
            "name": f.name,
            "prestige": getattr(f, "prestige", 50),
            "balance": getattr(f, "balance", 0),
        }
        for f in feds
    ]


# ---------------------------------------------------------------------------
# Action queue with conflict detection
# ---------------------------------------------------------------------------


class ConflictResolver:
    """Detects and resolves conflicting player actions within a single tick.

    Design:
    - All player actions for a tick are collected first.
    - Before execution, the resolver groups them by "conflict key" — a
      natural-language description of the shared resource they touch
      (e.g., "sign_wrestler:wrestler-123").
    - If two or more actions share a conflict key, the resolver picks a
      winner based on priority rules (higher prestige, earlier submission,
      or random tiebreaker).
    """

    def __init__(self):
        self._pending: List[Dict[str, Any]] = []

    def submit_action(
        self,
        user_id: str,
        federation_id: str,
        action_type: str,
        target_id: str,
        params: Optional[Dict[str, Any]] = None,
        priority: float = 0.0,
    ):
        """Queue an action for conflict resolution."""
        self._pending.append(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "federation_id": federation_id,
                "action_type": action_type,
                "target_id": target_id,
                "params": params or {},
                "priority": priority,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def resolve(self) -> Dict[str, List[Dict[str, Any]]]:
        """Resolve all pending actions and return approved vs rejected.

        Returns {"approved": [...], "rejected": [...]}.
        """
        # Group by conflict key
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for action in self._pending:
            key = f"{action['action_type']}:{action['target_id']}"
            groups.setdefault(key, []).append(action)

        approved = []
        rejected = []

        for key, actions in groups.items():
            if len(actions) == 1:
                approved.append(actions[0])
            else:
                # Conflict! Sort by priority descending, then submission time
                actions.sort(key=lambda a: (-a["priority"], a["submitted_at"]))
                winner = actions[0]
                winner["conflict_resolved"] = True
                winner["conflict_reason"] = (
                    f"Won conflict for {key} against {len(actions) - 1} other action(s)"
                )
                approved.append(winner)
                for loser in actions[1:]:
                    loser["conflict_resolved"] = True
                    loser["conflict_reason"] = (
                        f"Lost conflict for {key} to federation "
                        f"{winner['federation_id']}"
                    )
                    rejected.append(loser)

        self._pending.clear()

        logger.info(
            "Conflict resolution: %d approved, %d rejected",
            len(approved),
            len(rejected),
        )
        return {"approved": approved, "rejected": rejected}
