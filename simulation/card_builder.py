"""
Build full cards with segments from Card + CardType.

Maps matches into segment slots and fills non-match segments (opening, promo,
backstage, commercial, intermission, closing, dark match) per card type template.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from models.calendar import Card, Match
from models.card_structure import (
    CardType,
    FullCard,
    Segment,
    SegmentType,
    POV,
    CARD_TYPE_SEGMENT_TEMPLATE,
    SEGMENT_POV_VISIBILITY,
)


def card_type_from_show_type(show_type: Optional[str]) -> CardType:
    """Map week show_type to CardType for full card segment template."""
    if not show_type:
        return CardType.MAJOR_TV
    st = show_type.lower()
    if st == "house":
        return CardType.HOUSE
    if st == "ppv":
        return CardType.PPV
    if st == "dark":
        return CardType.MINOR_TV
    if st == "tv":
        return CardType.MAJOR_TV
    return CardType.MAJOR_TV


def build_full_card(
    card: Card,
    card_type: CardType = CardType.MAJOR_TV,
    extra_promos: int = 0,
    extra_backstage: int = 0,
) -> FullCard:
    """
    Build a FullCard with ordered segments from a Card and CardType.

    Maps matches into match slots from the template; fills opening, promo,
    backstage, commercial, intermission, closing, dark match per template.
    """
    template = CARD_TYPE_SEGMENT_TEMPLATE.get(card_type, CARD_TYPE_SEGMENT_TEMPLATE[CardType.MAJOR_TV])
    matches = list(card.matches) if card.matches else []
    match_idx = 0
    promo_lineup = getattr(card, "promo_lineup", None) or []
    promo_idx = 0
    segments: List[Segment] = []
    order = 0

    for st in template:
        order += 1
        seg_id = str(uuid.uuid4())
        pov_visible = SEGMENT_POV_VISIBILITY.get(st.value, [])

        if st == SegmentType.MATCH:
            if match_idx < len(matches):
                m = matches[match_idx]
                match_idx += 1
                seg = Segment(
                    segment_id=seg_id,
                    card_id=card.card_id,
                    segment_type=SegmentType.MATCH,
                    order=order,
                    match_id=m.match_id,
                    participant_ids=m.participant_ids,
                    duration_blocks=1,  # Will be overridden by actual match ticks
                    pov_visible=pov_visible,
                )
            else:
                continue  # No more matches, skip extra match slots
        elif st == SegmentType.DARK_MATCH:
            if match_idx < len(matches):
                m = matches[match_idx]
                match_idx += 1
                seg = Segment(
                    segment_id=seg_id,
                    card_id=card.card_id,
                    segment_type=SegmentType.DARK_MATCH,
                    order=order,
                    match_id=m.match_id,
                    participant_ids=m.participant_ids,
                    duration_blocks=1,
                    pov_visible=pov_visible,
                )
            else:
                continue
        else:
            # Promo: use promoter's promo_lineup if set, else next match's participants
            promo_participants: List[str] = []
            if st == SegmentType.PROMO:
                if promo_idx < len(promo_lineup):
                    promo_participants = list(promo_lineup[promo_idx])[:2]
                    promo_idx += 1
                elif match_idx < len(matches):
                    promo_participants = list(matches[match_idx].participant_ids)[:2]
            seg = Segment(
                segment_id=seg_id,
                card_id=card.card_id,
                segment_type=st,
                order=order,
                duration_blocks=1,
                pov_visible=pov_visible,
                participant_ids=promo_participants,
                metadata={} if st != SegmentType.COMMERCIAL else {"break_blocks": 1},
            )
        segments.append(seg)

    # If we have more matches than template slots, append as match segments
    while match_idx < len(matches):
        order += 1
        m = matches[match_idx]
        match_idx += 1
        segments.append(Segment(
            segment_id=str(uuid.uuid4()),
            card_id=card.card_id,
            segment_type=SegmentType.MATCH,
            order=order,
            match_id=m.match_id,
            participant_ids=m.participant_ids,
            duration_blocks=1,
            pov_visible=SEGMENT_POV_VISIBILITY["match"],
        ))

    # Extract match dicts for legacy compatibility
    match_dicts = [
        {
            "match_id": m.match_id,
            "card_id": m.card_id,
            "participant_ids": m.participant_ids,
            "stipulation": m.stipulation,
            "title_id": m.title_id,
            "storyline_id": m.storyline_id,
        }
        for m in matches
    ]

    return FullCard(
        card_id=card.card_id,
        federation_id=card.federation_id,
        name=card.name,
        card_date=card.card_date,
        week_id=card.week_id,
        venue_id=getattr(card, "venue_id", None),
        show_type=getattr(card, "show_type", None),
        prep_date=getattr(card, "prep_date", None),
        travel_squad_ids=getattr(card, "travel_squad_ids", None),
        card_type=card_type,
        segments=segments,
        matches=match_dicts,
    )
