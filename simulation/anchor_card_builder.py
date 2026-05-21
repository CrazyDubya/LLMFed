"""
Anchor card builder: one coherent FullCard for the marquee show two years out.

Builds the target card using:
- Roster at anchor date (available, not injured)
- Tenure mix (veteran main event, rising title match, newcomer opener)
- Titles and storylines with payoff at anchor
- ConceptualCard targets if set
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from models.calendar import Card, Match
from models.card_structure import FullCard, CardType, Segment, SegmentType, POV, SEGMENT_POV_VISIBILITY
from models.world_anchor import WorldAnchor
from simulation.roster_timeline import (
    get_available_at_date,
    get_tenure_mix_at_date,
    tenure_tier_for,
    get_roster_at_date,
)
from simulation.card_builder import build_full_card

logger = logging.getLogger(__name__)


def build_anchor_card(
    db,
    federation_id: str,
    anchor: WorldAnchor,
    conceptual_target: Optional[Dict[str, Any]] = None,
) -> FullCard:
    """
    Build one coherent FullCard for the marquee show at anchor date.

    Uses available roster (minus injured), tenure mix (veteran/rising/newcomer),
    titles, storylines with payoff at anchor, and optional conceptual targets.
    """
    from agent_service.wrestling_crud import (
        get_titles,
        get_storylines,
        get_current_champion,
        get_title_by_id,
    )

    anchor_date = anchor.get_anchor_date()
    available = get_available_at_date(db, federation_id, anchor_date, "participant")
    roster = get_roster_at_date(db, federation_id, anchor_date, "participant")
    tenure_mix = get_tenure_mix_at_date(db, federation_id, anchor_date, anchor)

    if len(available) < 2:
        # Fallback: use roster agent_ids if available empty
        fallback = [r["agent_id"] for r in roster][:8]
        if len(fallback) < 2:
            fallback = fallback * 2 if fallback else ["p1", "p2"]
        available = fallback

    titles = get_titles(db, federation_id=federation_id, limit=5)
    storylines = get_storylines(db, federation_id=federation_id, status="active", limit=10)
    anchor_storylines = [s for s in storylines if getattr(s, "payoff_phase", None) == "anchor"]

    # Build matches: main event (veterans), title matches (veteran/rising), mid-card, opener (newcomer)
    matches: List[Match] = []
    card_id = str(uuid.uuid4())
    used = set()

    # 1. Main event (veterans) - from conceptual target or tenure_mix.veteran
    main_event_ids = []
    if conceptual_target and conceptual_target.get("main_event_target"):
        t = conceptual_target["main_event_target"]
        ids = t.get("participant_ids", []) if isinstance(t, dict) else []
        main_event_ids = [i for i in ids if i in available and i not in used][:2]
    if not main_event_ids and tenure_mix.get("veteran"):
        main_event_ids = [a for a in tenure_mix["veteran"] if a in available and a not in used][:2]
    if not main_event_ids:
        main_event_ids = [a for a in available if a not in used][:2]
    if len(main_event_ids) >= 2:
        m = Match(
            match_id=str(uuid.uuid4()),
            card_id=card_id,
            participant_ids=main_event_ids,
            stipulation="StandardMatch",
        )
        matches.append(m)
        used.update(main_event_ids)

    # 2. Title matches (veteran/rising vs champion)
    for title in titles[:2]:
        champ_id = get_current_champion(db, title.title_id)
        if not champ_id or champ_id not in available:
            continue
        challengers = [a for a in (tenure_mix.get("rising") or []) + (tenure_mix.get("veteran") or [])
                      if a in available and a not in used and a != champ_id]
        if conceptual_target and conceptual_target.get("title_matches_target"):
            for tm in conceptual_target["title_matches_target"]:
                if isinstance(tm, dict) and tm.get("title_id") == title.title_id:
                    chal = tm.get("challenger_id") or (tm.get("participant_ids") or [])
                    if isinstance(chal, list):
                        chal = chal[0] if chal else None
                    if chal and chal in available and chal not in used:
                        challengers = [chal]
                        break
        if challengers:
            chal = random.choice(challengers[:3]) if challengers else None
            if chal:
                m = Match(
                    match_id=str(uuid.uuid4()),
                    card_id=card_id,
                    participant_ids=[champ_id, chal],
                    is_title_match=True,
                    title_id=title.title_id,
                )
                matches.append(m)
                used.add(champ_id)
                used.add(chal)

    # 3. Storyline matches (payoff at anchor)
    for s in anchor_storylines[:2]:
        pids = getattr(s, "participant_ids", []) or []
        avail = [p for p in pids if p in available and p not in used]
        if len(avail) >= 2:
            m = Match(
                match_id=str(uuid.uuid4()),
                card_id=card_id,
                participant_ids=avail[:2],
                storyline_id=getattr(s, "storyline_id", None),
            )
            matches.append(m)
            used.update(avail[:2])

    # 4. Remaining matches (fill from available)
    remaining = [a for a in available if a not in used]
    random.shuffle(remaining)
    while len(remaining) >= 2 and len(matches) < 6:
        m = Match(
            match_id=str(uuid.uuid4()),
            card_id=card_id,
            participant_ids=[remaining.pop(0), remaining.pop(0)],
        )
        matches.append(m)

    # Build FullCard from Card + MARQUEE_YEAR template
    card = Card(
        card_id=card_id,
        federation_id=federation_id,
        name=anchor.anchor_event_name,
        card_date=anchor_date,
        is_ppv=True,
        matches=matches,
    )
    full = build_full_card(card, card_type=CardType.MARQUEE_YEAR)
    return full
