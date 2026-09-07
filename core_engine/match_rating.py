"""
Match Rating & Crowd Heat Calculations

Extracted from match_engine.py — pure calculation functions that compute
a match's star rating and crowd heat level from the list of spots and
match context.
"""

import random
from typing import Optional

from core_engine.match_constants import (
    VARIETY_BONUS_PER_TYPE,
    VARIETY_BONUS_CAP,
    NEAR_FALL_BONUS_WEIGHT,
    NEAR_FALL_BONUS_CAP,
    REVERSAL_BONUS_WEIGHT,
    REVERSAL_BONUS_CAP,
    LENGTH_BONUS_DIVISOR,
    LENGTH_BONUS_CAP,
    LENGTH_BONUS_MIN_TICKS,
    TITLE_MATCH_RATING_BONUS,
    RIVALRY_HEAT_RATING_DIVISOR,
    RIVALRY_HEAT_RATING_CAP,
    INTERFERENCE_RATING_PENALTY,
    SIGNATURE_BONUS_WEIGHT,
    SIGNATURE_BONUS_CAP,
    CAGE_CELL_STIP_BONUS,
    LADDER_TABLE_STIP_BONUS,
    GENERIC_STIP_BONUS,
    RATING_MIN,
    RATING_MAX,
    RATING_NOISE_MIN,
    RATING_NOISE_MAX,
    RIVALRY_HEAT_CROWD_FACTOR,
    CROWD_HEAT_MIN,
    CROWD_HEAT_MAX,
)


def calculate_rating(
    spots,
    is_title_match: bool,
    rivalry_heat: int,
    interference_happened: bool,
    stipulation: Optional[str],
    show_momentum: int,
    tick: int,
    participants,
) -> float:
    """Calculate match star rating (0.0 - 5.0).

    Parameters
    ----------
    spots : list[MatchSpot]
        All spots generated during the match.
    is_title_match : bool
    rivalry_heat : int  (0-100)
    interference_happened : bool
    stipulation : str or None
    show_momentum : int
    tick : int  (total match ticks)
    participants : list[MatchParticipantState]
    """
    from core_engine.match_engine import get_venue_tier, VENUE_ATMOSPHERE

    # Base: average of participants' psychology and selling
    avg_psychology = sum(p.stats.get("psychology", 50) for p in participants) / len(
        participants
    )
    avg_selling = sum(p.stats.get("selling", 50) for p in participants) / len(
        participants
    )

    base_quality = (avg_psychology + avg_selling) / 100  # 0-1 scale

    # Bonus for spot variety
    move_types_used = set(s.move_type for s in spots if not s.was_reversed)
    variety_bonus = min(
        len(move_types_used) * VARIETY_BONUS_PER_TYPE, VARIETY_BONUS_CAP
    )

    # Bonus for near falls
    near_falls = sum(1 for s in spots if s.is_near_fall)
    near_fall_bonus = min(near_falls * NEAR_FALL_BONUS_WEIGHT, NEAR_FALL_BONUS_CAP)

    # Bonus for reversals (back-and-forth action)
    reversals = sum(1 for s in spots if s.was_reversed)
    reversal_bonus = min(reversals * REVERSAL_BONUS_WEIGHT, REVERSAL_BONUS_CAP)

    # Match length bonus
    length_bonus = (
        min(tick / LENGTH_BONUS_DIVISOR, LENGTH_BONUS_CAP)
        if tick > LENGTH_BONUS_MIN_TICKS
        else 0
    )

    # Title match bonus
    title_bonus = TITLE_MATCH_RATING_BONUS if is_title_match else 0

    # Rivalry heat bonus — hot feuds produce better matches
    rivalry_bonus = min(
        RIVALRY_HEAT_RATING_CAP, rivalry_heat / RIVALRY_HEAT_RATING_DIVISOR
    )

    # Interference penalty — cheating cheapens ratings slightly
    interference_penalty = INTERFERENCE_RATING_PENALTY if interference_happened else 0

    # Signature move bonus — fans love seeing signature spots
    sig_spots = sum(
        1 for s in spots if "Signature" in s.description or "signature" in s.description
    )
    sig_bonus = min(sig_spots * SIGNATURE_BONUS_WEIGHT, SIGNATURE_BONUS_CAP)

    # Stipulation bonus — gimmick matches get a bump for spectacle
    stip_bonus = 0.0
    stip = (stipulation or "").lower()
    if "cage" in stip or "cell" in stip:
        stip_bonus = CAGE_CELL_STIP_BONUS
    elif "ladder" in stip or "table" in stip:
        stip_bonus = LADDER_TABLE_STIP_BONUS
    elif stip and stip not in ("", "standard"):
        stip_bonus = GENERIC_STIP_BONUS

    # Venue atmosphere bonus (set by caller via show_momentum scaling)
    venue_tier = get_venue_tier(show_momentum * 100)  # approximate
    venue_mod = VENUE_ATMOSPHERE.get(venue_tier, {}).get("rating_mod", 0)

    rating = (
        (base_quality * 2.5)
        + variety_bonus
        + near_fall_bonus
        + reversal_bonus
        + length_bonus
        + title_bonus
        + rivalry_bonus
        + interference_penalty
        + sig_bonus
        + stip_bonus
        + venue_mod
    )
    rating = min(
        RATING_MAX,
        max(RATING_MIN, rating + random.uniform(RATING_NOISE_MIN, RATING_NOISE_MAX)),
    )
    return round(rating, 1)


def calculate_heat(spots, show_momentum: int, rivalry_heat: int) -> int:
    """Calculate final crowd heat level.

    Parameters
    ----------
    spots : list[MatchSpot]
    show_momentum : int
    rivalry_heat : int
    """
    # Start from show momentum (crowd energy carried from prior segments)
    base = show_momentum
    # Rivalry heat gives a crowd bonus — fans care about these two
    base += int(rivalry_heat * RIVALRY_HEAT_CROWD_FACTOR)
    for spot in spots:
        base += spot.heat_change
    return max(CROWD_HEAT_MIN, min(CROWD_HEAT_MAX, base))
