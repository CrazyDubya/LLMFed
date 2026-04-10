"""
Tag Match Simulation Logic

Extracted from match_engine.py — contains the tag team match simulation loop
and tag-specific action logic (tag-in, hot tag, double-team).
"""

import random
from typing import List, Dict, Optional

from core_engine.match_constants import (
    FINISHER_MOMENTUM_THRESHOLD, NEAR_FALL_CHANCE,
    TAG_IN_TICKS_THRESHOLD, TAG_IN_STAMINA_THRESHOLD, TAG_IN_CHANCE,
    TAG_IN_MOMENTUM_BOOST,
    HOT_TAG_TICKS_THRESHOLD, HOT_TAG_HEALTH_THRESHOLD, HOT_TAG_CHANCE,
    HOT_TAG_MOMENTUM_BOOST,
    DOUBLE_TEAM_CHANCE,
)
from core_engine.match_engine import (
    MatchParticipantState, MatchSpot, MatchResult,
    TAG_DESCRIPTIONS, DOUBLE_TEAM_MOVES,
)
from core_engine.match_rating import calculate_rating, calculate_heat


def simulate_tag_match(sim, participants: List[MatchParticipantState]) -> MatchResult:
    """Simulate a tag team match with legal man tracking, tags, hot tags, and double-team spots.

    Parameters
    ----------
    sim : MatchSimulator
        The simulator instance (provides helper methods and shared state).
    participants : list[MatchParticipantState]
        All participants in the tag match.
    """
    team_map: Dict[int, List[MatchParticipantState]] = {}
    for p in participants:
        team_id = p.team if p.team is not None else 0
        team_map.setdefault(team_id, []).append(p)

    team_ids = sorted(team_map.keys())
    if len(team_ids) < 2:
        return sim._simulate_singles(participants)

    # teams[0] = team A roster, teams[1] = team B roster
    teams = [team_map[team_ids[0]], team_map[team_ids[1]]]

    # Mutable state: legal_indices[i] = index of legal man in teams[i]
    legal_indices = [0, 0]
    # ticks_in[i] = how long team i's legal man has been in the ring
    ticks_in = [0, 0]

    # Tag matches run slightly longer
    min_len, max_len = sim.MATCH_LENGTH.get(sim.card_position, (10, 20))
    target_length = random.randint(min_len + 3, max_len + 5)

    # Who's on offense: 0 = teams[0] attacks, 1 = teams[1] attacks
    attacking_team = 0

    while sim.tick < target_length + 10:
        sim.tick += 1
        ticks_in[0] += 1
        ticks_in[1] += 1

        atk_team = attacking_team
        def_team = 1 - attacking_team
        attacker = teams[atk_team][legal_indices[atk_team]]
        defender = teams[def_team][legal_indices[def_team]]

        # --- Tag-in, hot tag, and double-team opportunities ---
        result = tag_team_action(
            sim, teams, legal_indices, ticks_in, attacking_team,
            attacker, defender,
        )
        if result is not None:
            action_type, attacker, defender, attacking_team = result
            if action_type == "double_team":
                continue  # Double-team already applied; skip normal spot

        # --- Normal spot ---
        spot = sim._generate_spot(attacker, defender)
        sim.spots.append(spot)
        sim._apply_spot(spot, attacker, defender)

        if not attacker.finisher_available and attacker.momentum > FINISHER_MOMENTUM_THRESHOLD:
            attacker.finisher_available = True

        if sim.tick >= target_length - 3:
            finish_spot = sim._attempt_finish(attacker, defender)
            if finish_spot:
                sim.spots.append(finish_spot)
                return sim._build_result(finish_spot, attacker, defender, participants)

        if sim.tick > target_length * 0.6 and random.random() < NEAR_FALL_CHANCE:
            near_fall = sim._near_fall(attacker, defender)
            if near_fall:
                sim.spots.append(near_fall)

        if sim._should_switch_control(attacker, defender):
            attacking_team = 1 - attacking_team

    return MatchResult(
        winner_id=None,
        finish_type="time_limit_draw",
        finish_description="The tag team match ends in a time limit draw!",
        match_rating=calculate_rating(sim.spots, sim.is_title_match, sim.rivalry_heat,
                                       sim._interference_happened, sim.stipulation,
                                       sim.show_momentum, sim.tick, participants),
        crowd_heat=calculate_heat(sim.spots, sim.show_momentum, sim.rivalry_heat),
        duration_ticks=sim.tick,
        spots=sim.spots,
    )


def tag_team_action(
    sim,
    teams: List[List[MatchParticipantState]],
    legal_indices: List[int],
    ticks_in: List[int],
    attacking_team: int,
    attacker: MatchParticipantState,
    defender: MatchParticipantState,
) -> Optional[tuple]:
    """Handle tag-in, hot tag, and double-team logic for either team.

    Returns ``None`` if no tag action occurred, or a tuple of
    ``(action_type, attacker, defender, attacking_team)`` reflecting the
    (possibly updated) match state.
    """
    atk_team = attacking_team
    def_team = 1 - attacking_team

    # --- Tag-in opportunity (attacking team tags to bring fresh partner) ---
    if (ticks_in[atk_team] > TAG_IN_TICKS_THRESHOLD
            and attacker.stamina < TAG_IN_STAMINA_THRESHOLD
            and random.random() < TAG_IN_CHANCE
            and len(teams[atk_team]) > 1):
        legal_indices[atk_team] = (legal_indices[atk_team] + 1) % len(teams[atk_team])
        ticks_in[atk_team] = 0
        new_wrestler = teams[atk_team][legal_indices[atk_team]]
        new_wrestler.momentum = min(100, new_wrestler.momentum + TAG_IN_MOMENTUM_BOOST)
        sim.spots.append(MatchSpot(
            tick=sim.tick, attacker_id=new_wrestler.wrestler_id,
            defender_id=defender.wrestler_id, move_name="Tag",
            move_type="tag", damage=0,
            crowd_reaction="Tag made!", heat_change=1,
            description=f"{attacker.name} {random.choice(TAG_DESCRIPTIONS)}! {new_wrestler.name} enters the ring!",
        ))
        return ("tag_in", new_wrestler, defender, attacking_team)

    # --- Hot tag mechanic (defending team, beaten down, makes desperate tag) ---
    if (ticks_in[def_team] > HOT_TAG_TICKS_THRESHOLD
            and defender.health < HOT_TAG_HEALTH_THRESHOLD
            and random.random() < HOT_TAG_CHANCE
            and len(teams[def_team]) > 1):
        legal_indices[def_team] = (legal_indices[def_team] + 1) % len(teams[def_team])
        ticks_in[def_team] = 0
        hot_tag = teams[def_team][legal_indices[def_team]]
        hot_tag.momentum = min(100, hot_tag.momentum + HOT_TAG_MOMENTUM_BOOST)
        hot_tag.finisher_available = True
        sim.spots.append(MatchSpot(
            tick=sim.tick, attacker_id=hot_tag.wrestler_id,
            defender_id=attacker.wrestler_id, move_name="Hot Tag",
            move_type="tag", damage=0,
            crowd_reaction="The crowd erupts for the hot tag!",
            heat_change=4,
            description=f"{defender.name} desperately reaches out... HOT TAG! {hot_tag.name} storms into the ring on fire!",
        ))
        # Offense switches to the defending team
        new_attacking_team = def_team
        return ("hot_tag", hot_tag, attacker, new_attacking_team)

    # --- Double-team opportunity (both partners briefly in ring) ---
    if random.random() < DOUBLE_TEAM_CHANCE and len(teams[atk_team]) > 1:
        partner = teams[atk_team][(legal_indices[atk_team] + 1) % len(teams[atk_team])]
        move_name, dmg = random.choice(DOUBLE_TEAM_MOVES)
        dt_spot = MatchSpot(
            tick=sim.tick, attacker_id=attacker.wrestler_id,
            defender_id=defender.wrestler_id, move_name=move_name,
            move_type="power", damage=dmg,
            crowd_reaction="Incredible double-team!",
            heat_change=3,
            description=f"{attacker.name} and {partner.name} hit a {move_name} on {defender.name}!",
        )
        sim.spots.append(dt_spot)
        sim._apply_spot(dt_spot, attacker, defender)
        return ("double_team", attacker, defender, attacking_team)

    return None
