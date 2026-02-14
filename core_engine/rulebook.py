"""RuleBook for validating and translating chosen actions to AppliedAction.

For now it wraps the incoming action and marks it as always valid.
AppliedAction is imported at call time to break a circular dependency
with engine.py (engine -> rulebook -> engine). This is the one place
where deferred import is justified (Rule 10).
"""
from __future__ import annotations

from typing import Dict, Any


class RuleBook:
    """Static utility to validate actions."""

    @staticmethod
    def validate(action_id: str, description: str | None = None, meta: Dict[str, Any] | None = None) -> AppliedAction:
        """Return an AppliedAction — trivial pass-through for now."""
        from core_engine.engine import AppliedAction
        return AppliedAction(
            action_id=action_id,
            description=description or "Validated action",
            effects=meta or {},
        )
