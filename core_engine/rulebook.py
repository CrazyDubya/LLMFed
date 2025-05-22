"""Very simple RuleBook for validating and translating chosen actions to AppliedAction.

In future this will contain comprehensive rules. For now it simply wraps the
incoming stub action and marks it as always valid, returning an `AppliedAction`.
"""
from __future__ import annotations

from typing import Dict, Any
from dataclasses import dataclass

# We'll import AppliedAction at call time to avoid circular import

class RuleBook:
    """Static utility to validate actions until richer rules implemented."""

    @staticmethod
    def validate(action_id: str, description: str | None = None, meta: Dict[str, Any] | None = None) -> AppliedAction:
        """Return an AppliedAction with trivial effect (placeholder)."""
        from core_engine.engine import AppliedAction
        return AppliedAction(
            action_id=action_id,
            description=description or "Validated action",
            effects=meta or {},
        )
