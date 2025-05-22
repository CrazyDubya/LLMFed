"""Stub LLMDispatcher.
Generates a random placeholder action id to simulate agent/LLM choice.
"""

import random
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class StubAction:
    action_id: str
    description: str
    meta: Dict[str, Any]


class LLMDispatcher:
    """Very naive dispatcher that returns a random action."""

    _ACTIONS = [
        ("punch", "A quick right hand"),
        ("kick", "A stiff kick"),
        ("taunt", "Raises arms to taunt the crowd"),
    ]

    def choose_action(self) -> StubAction:
        aid, desc = random.choice(self._ACTIONS)
        return StubAction(action_id=aid, description=desc, meta={})
