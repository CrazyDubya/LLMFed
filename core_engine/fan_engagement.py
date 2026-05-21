"""
Fan interaction system (ENHANCEMENT_PROPOSAL Phase 3.1).

- Match polls: fans vote on stipulations, opponents
- Agent popularity: heat from fan reactions
- FanReaction: simulate crowd reaction
"""

from __future__ import annotations

import logging
import random
import uuid
from typing import List, Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PollType(str, Enum):
    """Type of fan poll."""
    POPULARITY = "popularity"
    MATCH_BOOKING = "match_booking"
    STIPULATION = "stipulation"


class Poll(BaseModel):
    """A fan poll."""
    poll_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    poll_type: PollType = Field(default=PollType.POPULARITY)
    subject_agent_id: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    votes: Dict[str, int] = Field(default_factory=dict)


class Vote(BaseModel):
    """A single vote in a poll."""
    vote_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    poll_id: str = Field()
    option: str = Field()
    user_id: Optional[str] = None


class FanReaction(BaseModel):
    """Simulated crowd reaction."""
    intensity: int = Field(default=5, ge=1, le=10)
    sentiment: str = Field(default="mixed")
    chants: List[str] = Field(default_factory=list)


class FanEngagement:
    """Process fan votes and generate fan reactions."""

    def __init__(self, db_session_factory=None):
        from agent_service.database import SessionLocal
        self._get_db = db_session_factory or SessionLocal

    def process_fan_vote(self, poll: Poll, user_vote: Vote) -> Dict[str, Any]:
        """Process a vote and update poll results."""
        if user_vote.option not in poll.options and poll.options:
            user_vote.option = poll.options[0]
        votes = dict(poll.votes or {})
        votes[user_vote.option] = votes.get(user_vote.option, 0) + 1
        poll.votes = votes
        return {"poll_id": poll.poll_id, "option": user_vote.option, "results": votes}

    def generate_fan_reaction(
        self,
        event: Dict[str, Any],
        agent_popularity: Optional[Dict[str, int]] = None,
        move_quality: int = 5,
        storyline_significance: int = 5,
        surprise_factor: int = 0,
    ) -> FanReaction:
        """Simulate crowd reaction based on event context."""
        base = (agent_popularity or {}).get("heat", 50) / 10
        intensity = int(min(10, max(1, base + move_quality // 2 + storyline_significance // 2 + surprise_factor)))
        sentiment = "positive" if intensity >= 7 else ("negative" if intensity <= 3 else "mixed")
        chants = ["This is awesome!"] if intensity >= 8 else (["Boring!"] if intensity <= 3 else [])
        return FanReaction(intensity=intensity, sentiment=sentiment, chants=chants)
