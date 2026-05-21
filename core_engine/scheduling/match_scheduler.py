"""
Automated match scheduling (ENHANCEMENT_PROPOSAL Phase 2.2).

Creates compelling match cards based on:
- Storyline progression needs
- Agent win/loss records
- Title picture implications
- Balanced rosters
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import date
from typing import List, Optional, Any, Dict

from models.calendar import Card, Match, Week
from models.card_structure import CardType, FullCard
from simulation.card_builder import build_full_card

logger = logging.getLogger(__name__)


class WeeklyShow:
    """A scheduled weekly show with matches and storylines."""

    def __init__(
        self,
        federation_id: str,
        name: str,
        card_date: Optional[date] = None,
        matches: Optional[List[Match]] = None,
        storylines: Optional[List[Dict[str, Any]]] = None,
    ):
        self.federation_id = federation_id
        self.name = name
        self.card_date = card_date or date.today()
        self.matches = matches or []
        self.storylines = storylines or []


class MatchScheduler:
    """
    Automated match scheduling.

    - Title contenders: automatic #1 contender logic
    - Rivalry development: escalating confrontations
    - Balanced rosters: ensure all agents get opportunities
    - Special events: PPV-style monthly culmination
    """

    def __init__(self, db_session_factory=None):
        from agent_service.database import SessionLocal
        self._get_db = db_session_factory or (lambda: SessionLocal())

    def schedule_weekly_show(
        self,
        federation_id: str,
        name: str = "Weekly Show",
        card_date: Optional[date] = None,
        card_type: CardType = CardType.MAJOR_TV,
        title_id: Optional[str] = None,
        storyline_ids: Optional[List[str]] = None,
    ) -> Card:
        """
        Generate a match card for a weekly show.

        Uses available agents, active storylines, and title context.
        """
        db = self._get_db()
        try:
            from agent_service.crud import get_agents_by_federation_id
            from agent_service.wrestling_crud import get_storylines, get_title_by_id, get_current_champion

            agents = get_agents_by_federation_id(db, federation_id)
            participants = [a for a in agents if getattr(a, "role", None) == "participant"]
            participant_ids = [a.agent_id for a in participants]

            if len(participant_ids) < 2:
                logger.warning("Fewer than 2 participants; using all agents")
                participant_ids = [a.agent_id for a in agents][:4]
            if len(participant_ids) < 2:
                participant_ids = participant_ids * 2 if participant_ids else ["p1", "p2"]

            storylines_list = []
            if storyline_ids:
                from agent_service.wrestling_crud import get_storyline_by_id
                for sid in storyline_ids:
                    s = get_storyline_by_id(db, sid)
                    if s and s.status == "active" and s.participant_ids:
                        storylines_list.append(s)

            active_storylines = storylines_list or [
                s for s in get_storylines(db, federation_id=federation_id, status="active", limit=5)
                if s and getattr(s, "participant_ids", None)
            ]

            matches = self._create_optimal_match_card(
                participant_ids=participant_ids,
                federation_id=federation_id,
                title_id=title_id,
                active_storylines=active_storylines,
                db=db,
            )

            card_id = str(uuid.uuid4())
            card = Card(
                card_id=card_id,
                federation_id=federation_id,
                name=name,
                card_date=card_date or date.today(),
                is_ppv=card_type in (CardType.PPV, CardType.MARQUEE_SEASON, CardType.MARQUEE_YEAR),
                matches=matches,
            )
            return card
        finally:
            db.close()

    def _create_optimal_match_card(
        self,
        participant_ids: List[str],
        federation_id: str,
        title_id: Optional[str],
        active_storylines: List[Any],
        db,
    ) -> List[Match]:
        """Build matches: title match if requested, storyline matches, then fresh matchups."""
        matches: List[Match] = []
        card_id = str(uuid.uuid4())
        used = set()

        if title_id:
            from agent_service.wrestling_crud import get_title_by_id, get_current_champion
            title = get_title_by_id(db, title_id)
            champ_id = get_current_champion(db, title_id) if title else None
            if title and champ_id and champ_id in participant_ids:
                challengers = [p for p in participant_ids if p != champ_id]
                if challengers:
                    chal = random.choice(challengers)
                    m = Match(
                        match_id=str(uuid.uuid4()),
                        card_id=card_id,
                        participant_ids=[champ_id, chal],
                        is_title_match=True,
                        title_id=title_id,
                    )
                    matches.append(m)
                    used.add(champ_id)
                    used.add(chal)

        for story in active_storylines[:2]:
            pids = getattr(story, "participant_ids", None) or []
            avail = [p for p in pids if p in participant_ids and p not in used]
            if len(avail) >= 2:
                a, b = avail[0], avail[1]
                m = Match(
                    match_id=str(uuid.uuid4()),
                    card_id=card_id,
                    participant_ids=[a, b],
                    storyline_id=getattr(story, "storyline_id", None),
                )
                matches.append(m)
                used.add(a)
                used.add(b)

        remaining = [p for p in participant_ids if p not in used]
        random.shuffle(remaining)
        while len(remaining) >= 2:
            a, b = remaining.pop(), remaining.pop()
            m = Match(
                match_id=str(uuid.uuid4()),
                card_id=card_id,
                participant_ids=[a, b],
            )
            matches.append(m)

        return matches
