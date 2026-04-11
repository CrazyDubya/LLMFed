"""
Match Simulation Engine

Simulates a wrestling match move-by-move using wrestler stats, chemistry,
and storytelling logic. Produces a narrative log and determines the winner.

The simulation runs in "spots" (key moments), not real-time ticks.
Each spot involves an offensive wrestler performing a move, the defensive
wrestler potentially reversing, and crowd/momentum shifts.
"""

import random
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from core_engine.match_constants import (
    # Momentum thresholds
    TAUNT_MOMENTUM_THRESHOLD, SIGNATURE_MOMENTUM_THRESHOLD,
    FINISHER_MOMENTUM_THRESHOLD, FINISH_MOMENTUM_BONUS_THRESHOLD,
    CAGE_ESCAPE_MOMENTUM_THRESHOLD, LADDER_CLIMB_MOMENTUM_THRESHOLD,
    # Probability constants
    TAUNT_CHANCE, COCKY_BACKFIRE_CHANCE, SIGNATURE_CHANCE,
    STIPULATION_SPOT_CHANCE,
    BOTCH_DIFFICULTY_FACTOR, BOTCH_AERIAL_BONUS, BOTCH_MAX_CHANCE,
    BOTCH_MINOR_THRESHOLD, BOTCH_BAD_THRESHOLD,
    REVERSAL_BASE_CHANCE_DIVISOR, REVERSAL_DAMAGE_MULTIPLIER,
    INTERFERENCE_CATCH_CHANCE, INTERFERENCE_DQ_CHANCE,
    INTERFERENCE_MAX_CHANCE, INTERFERENCE_DAMAGE,
    INTERFERENCE_MOMENTUM_LOSS, INTERFERENCE_MOMENTUM_GAIN,
    NEAR_FALL_CHANCE, NEAR_FALL_HEALTH_THRESHOLD, MULTI_NEAR_FALL_CHANCE,
    UPSET_CHANCE, SHOOT_MAX_CHANCE, SHOOT_EGO_THRESHOLD,
    SHOOT_FRUSTRATION_THRESHOLD, SHOOT_MORALE_THRESHOLD,
    SHOOT_TITLE_MULTIPLIER,
    ELIMINATION_ENDURANCE_THRESHOLD, ELIMINATION_CHANCE,
    # Damage modifiers
    BASE_DAMAGE_MIN, SIGNATURE_DAMAGE_MIN, STAT_BASELINE,
    DEFENSE_DIVISOR, STAMINA_FLOOR, HOMETOWN_DAMAGE_MULTIPLIER,
    DANGEROUS_BOTCH_DAMAGE_MULTIPLIER,
    FINISHER_DAMAGE, SHOOT_FINISHER_DAMAGE,
    # Momentum shift values
    REVERSAL_MOMENTUM_GAIN, REVERSAL_MOMENTUM_LOSS,
    NORMAL_HIT_MOMENTUM_GAIN, NORMAL_HIT_MOMENTUM_LOSS,
    TAUNT_MOMENTUM_DEFAULT, TAUNT_MOMENTUM_INTENSE, TAUNT_MOMENTUM_COCKY,
    # Stamina / endurance drain
    ATTACKER_STAMINA_DRAIN_MIN, ATTACKER_STAMINA_DRAIN_MAX,
    DEFENDER_STAMINA_DRAIN_MIN, DEFENDER_STAMINA_DRAIN_MAX,
    ENDURANCE_DRAIN_FACTOR,
    # Match finish chances
    FINISH_BASE_CHANCE, FINISH_FINISHER_READY_CHANCE,
    FINISH_LOW_HEALTH_BONUS, FINISH_HIGH_MOMENTUM_BONUS,
    DEFENDER_LOW_HEALTH_THRESHOLD,
    # Control switch / comeback
    COMEBACK_LOW_HEALTH_THRESHOLD, COMEBACK_LOW_HEALTH_BONUS,
    # Rating (still needed in _build_result for botch penalty)
    BOTCH_RATING_PENALTY_PER, DANGEROUS_BOTCH_EXTRA_PENALTY, RATING_MIN,
    # Highlight tier
    HIGHLIGHT_DAMAGE_THRESHOLD,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static data — moved to match_data.py for cleanliness, re-exported here
# ---------------------------------------------------------------------------

from core_engine.match_data import (  # noqa: E402
    MOVES, SIGNATURE_MOVE_POOLS, ARCHETYPE_FINISHERS,
    CAGE_SPOTS, LADDER_SPOTS, TABLE_SPOTS, HELL_IN_A_CELL_SPOTS,
    IRON_MAN_FALL_DESCRIPTIONS,
    TAUNT_SPOTS, VENUE_ATMOSPHERE, get_venue_tier,
    CROWD_REACTIONS, REVERSAL_DESCRIPTIONS, NEAR_FALL_DESCRIPTIONS,
    INTERFERENCE_SUCCESS, INTERFERENCE_CAUGHT, INTERFERENCE_FAIL,
    POST_MATCH_ATTACK, POST_MATCH_SAVE,
    TAG_DESCRIPTIONS, DOUBLE_TEAM_MOVES,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MatchParticipantState:
    """Runtime state for a wrestler during a match."""
    wrestler_id: str
    name: str
    health: float = 100.0  # 0-100, match ends when pinned at low health
    momentum: float = 50.0  # 0-100, determines who's on offense
    stamina: float = 100.0  # Decreases with each move
    endurance: float = 100.0  # For multi-person elimination tracking
    finisher_available: bool = False
    finisher_used: bool = False
    stats: Dict[str, int] = field(default_factory=dict)
    finisher_name: str = "Finisher"
    alignment: str = "face"
    team: Optional[int] = None
    signature_moves: list = field(default_factory=list)  # [(name, damage, type), ...]
    charisma_style: str = "humble"  # cocky, humble, intense, funny, mysterious
    hometown_bonus: bool = False  # True if wrestling in home region


@dataclass
class MatchSpot:
    """A single moment/event in the match."""
    tick: int
    attacker_id: str
    defender_id: str
    move_name: str
    move_type: str  # power, technical, aerial, brawling, submission
    damage: int
    was_reversed: bool = False
    reversal_move: Optional[str] = None
    is_finisher: bool = False
    is_near_fall: bool = False
    is_finish: bool = False
    finish_type: Optional[str] = None  # pinfall, submission, count_out
    crowd_reaction: str = ""
    heat_change: int = 0
    description: str = ""
    is_botch: bool = False  # Move went wrong
    botch_severity: int = 0  # 0=none, 1=minor (stumble), 2=bad (sloppy), 3=dangerous (injury risk)
    is_shoot: bool = False  # Wrestler went into business for themselves


@dataclass
class ManagerContext:
    """Manager at ringside for a wrestler."""
    manager_id: str
    manager_name: str
    client_wrestler_id: str
    interference_skill: int = 50
    cunning: int = 50
    specialization: str = "all_around"


@dataclass
class MatchResult:
    """Final result of a simulated match."""
    winner_id: Optional[str] = None
    finish_type: str = "pinfall"
    finish_description: str = ""
    match_rating: float = 0.0
    crowd_heat: int = 50
    duration_ticks: int = 0
    spots: List[MatchSpot] = field(default_factory=list)
    narrative_summary: str = ""
    interference_occurred: bool = False
    post_match_angle: Optional[Dict[str, Any]] = None
    botch_count: int = 0  # How many botches occurred
    botch_events: List[Dict[str, Any]] = field(default_factory=list)  # [{attacker, victim, severity, move}]
    went_into_business: bool = False  # Someone deviated from the planned finish
    shoot_wrestler_id: Optional[str] = None  # Who went into business


# ---------------------------------------------------------------------------
# Match Simulator
# ---------------------------------------------------------------------------

class MatchSimulator:
    """Simulates a wrestling match between participants."""

    # Match length targets based on card position
    MATCH_LENGTH = {
        "opener": (8, 15),
        "midcard": (10, 20),
        "semifinal": (15, 25),
        "main_event": (20, 35),
    }

    def __init__(self, planned_winner_id: str = None, planned_finish: str = None,
                 card_position: str = "midcard", is_title_match: bool = False,
                 stipulation: str = None, managers: List[ManagerContext] = None,
                 rivalry_heat: int = 0, show_momentum: int = 50):
        self.planned_winner_id = planned_winner_id
        self.planned_finish = planned_finish or "pinfall"
        self.card_position = card_position
        self.is_title_match = is_title_match
        self.stipulation = stipulation
        self.managers = managers or []
        self.rivalry_heat = rivalry_heat  # 0-100, from storyline/relationship
        self.show_momentum = show_momentum  # crowd energy from earlier segments
        self.spots: List[MatchSpot] = []
        self.tick = 0
        self._interference_happened = False
        self._dq_triggered = False
        self._shoot_occurred = False
        self._shoot_wrestler_id = None
        self._trust_penalty = 0.0  # Set by caller from relationship trust_level

    def simulate(self, participants: List[MatchParticipantState]) -> MatchResult:
        """Run the full match simulation."""
        if len(participants) < 2:
            return MatchResult(narrative_summary="Match cancelled - not enough participants")

        # Detect tag match: 4+ participants with team assignments
        teams = set(p.team for p in participants if p.team is not None)
        if len(teams) >= 2 and len(participants) >= 4:
            return self._simulate_tag_match(participants)

        # Multi-person match (triple threat, fatal four way, battle royal)
        if len(participants) > 2:
            return self._simulate_multi_person(participants)

        return self._simulate_singles(participants)

    def _simulate_singles(self, participants: List[MatchParticipantState]) -> MatchResult:
        """Run a singles (or non-tag multi-person) match simulation."""
        # Determine target length
        min_len, max_len = self.MATCH_LENGTH.get(self.card_position, (10, 20))
        target_length = random.randint(min_len, max_len)

        attacker_idx = 0
        defender_idx = 1

        while self.tick < target_length + 10:
            self.tick += 1
            attacker = participants[attacker_idx]
            defender = participants[defender_idx]

            spot = self._generate_spot(attacker, defender)
            self.spots.append(spot)
            self._apply_spot(spot, attacker, defender)

            if not attacker.finisher_available and attacker.momentum > FINISHER_MOMENTUM_THRESHOLD:
                attacker.finisher_available = True

            # Manager interference opportunity (second half of match)
            if self.tick > target_length * 0.5 and not self._interference_happened:
                interference = self._attempt_interference(attacker, defender)
                if interference:
                    self.spots.append(interference)
                    if interference.is_finish:
                        # DQ finish
                        return self._build_result(interference, attacker, defender, participants)

            if self.tick >= target_length - 3:
                finish_spot = self._attempt_finish(attacker, defender)
                if finish_spot:
                    self.spots.append(finish_spot)
                    return self._build_result(finish_spot, attacker, defender, participants)

            if self.tick > target_length * 0.6 and random.random() < NEAR_FALL_CHANCE:
                near_fall = self._near_fall(attacker, defender)
                if near_fall:
                    self.spots.append(near_fall)

            if self._should_switch_control(attacker, defender):
                attacker_idx, defender_idx = defender_idx, attacker_idx

        return MatchResult(
            winner_id=None,
            finish_type="time_limit_draw",
            finish_description="The match ends in a time limit draw!",
            match_rating=self._calculate_rating(participants),
            crowd_heat=self._calculate_heat(),
            duration_ticks=self.tick,
            spots=self.spots,
        )

    def _simulate_multi_person(self, participants: List[MatchParticipantState]) -> MatchResult:
        """Simulate a multi-person match (triple threat, fatal four way, battle royal).

        Uses elimination logic: when a participant's endurance drops low, they can
        be eliminated. The last two standing get a proper finishing sequence.
        """
        min_len, max_len = self.MATCH_LENGTH.get(self.card_position, (10, 20))
        # Multi-person matches run a bit longer
        target_length = random.randint(min_len + 3, max_len + 5)

        active = list(participants)
        eliminated = []

        while self.tick < target_length + 15 and len(active) >= 2:
            self.tick += 1

            # Pick a random attacker/defender pair from active participants
            attacker = random.choice(active)
            defender = random.choice([p for p in active if p is not attacker])

            spot = self._generate_spot(attacker, defender)
            self.spots.append(spot)
            self._apply_spot(spot, attacker, defender)

            if not attacker.finisher_available and attacker.momentum > FINISHER_MOMENTUM_THRESHOLD:
                attacker.finisher_available = True

            # Elimination check: participants with very low endurance can be pinned
            if len(active) > 2 and self.tick > target_length * 0.3:
                for p in list(active):
                    if p is attacker:
                        continue
                    if p.endurance < ELIMINATION_ENDURANCE_THRESHOLD and random.random() < ELIMINATION_CHANCE:
                        eliminated.append(p)
                        active.remove(p)
                        elim_spot = MatchSpot(
                            tick=self.tick,
                            attacker_id=attacker.wrestler_id,
                            defender_id=p.wrestler_id,
                            move_name="Elimination",
                            move_type="power",
                            damage=0,
                            description=f"{p.name} has been eliminated!",
                            crowd_reaction="pop",
                        )
                        self.spots.append(elim_spot)

            # Near-falls add drama
            if self.tick > target_length * 0.5 and random.random() < MULTI_NEAR_FALL_CHANCE:
                near_fall = self._near_fall(attacker, defender)
                if near_fall:
                    self.spots.append(near_fall)

            # When down to 2, try for a finish
            if len(active) == 2 and self.tick >= target_length - 3:
                finish_spot = self._attempt_finish(attacker, defender)
                if finish_spot:
                    self.spots.append(finish_spot)
                    return self._build_result(finish_spot, attacker, defender, participants)

        # Time limit: pick the participant with the highest momentum as winner
        if len(active) >= 2:
            winner = max(active, key=lambda p: p.momentum)
            remaining = [p for p in active if p is not winner]
            loser = remaining[0] if remaining else active[-1]
            return MatchResult(
                winner_id=winner.wrestler_id,
                finish_type="pinfall",
                finish_description=f"{winner.name} pins {loser.name} after a grueling multi-person match!",
                match_rating=self._calculate_rating(participants),
                crowd_heat=self._calculate_heat(),
                duration_ticks=self.tick,
                spots=self.spots,
            )

        return MatchResult(
            winner_id=active[0].wrestler_id if active else None,
            finish_type="last_person_standing",
            finish_description="Last person standing wins!" if active else "No winner — all participants eliminated!",
            match_rating=self._calculate_rating(participants),
            crowd_heat=self._calculate_heat(),
            duration_ticks=self.tick,
            spots=self.spots,
        )

    def _simulate_tag_match(self, participants: List[MatchParticipantState]) -> MatchResult:
        """Simulate a tag team match.  Delegates to tag_match_simulator module."""
        from core_engine.tag_match_simulator import simulate_tag_match
        return simulate_tag_match(self, participants)

    def _generate_spot(self, attacker: MatchParticipantState,
                       defender: MatchParticipantState) -> MatchSpot:
        """Generate a single match spot."""
        # --- Charisma style taunt ---
        if attacker.momentum > TAUNT_MOMENTUM_THRESHOLD and random.random() < TAUNT_CHANCE:
            style = attacker.charisma_style or "humble"
            if style in TAUNT_SPOTS:
                taunt = random.choice(TAUNT_SPOTS[style]).format(
                    name=attacker.name, opponent=defender.name)
                momentum_gain = TAUNT_MOMENTUM_DEFAULT
                if style == "intense":
                    momentum_gain = TAUNT_MOMENTUM_INTENSE
                elif style == "cocky":
                    momentum_gain = TAUNT_MOMENTUM_COCKY
                    if random.random() < COCKY_BACKFIRE_CHANCE:
                        # Backfire: opponent fires up
                        return MatchSpot(
                            tick=self.tick,
                            attacker_id=defender.wrestler_id,
                            defender_id=attacker.wrestler_id,
                            move_name="Fired Up",
                            move_type="brawling",
                            damage=3,
                            description=f"{attacker.name} taunts — but {defender.name} fires up! The crowd goes wild!",
                            crowd_reaction="Huge pop from the fired-up underdog!",
                            heat_change=5,
                        )
                return MatchSpot(
                    tick=self.tick,
                    attacker_id=attacker.wrestler_id,
                    defender_id=defender.wrestler_id,
                    move_name="Taunt",
                    move_type="charisma",
                    damage=0,
                    description=taunt,
                    crowd_reaction=random.choice(CROWD_REACTIONS),
                    heat_change=momentum_gain,
                )

        # --- Match-type-specific spots ---
        if self.stipulation and random.random() < STIPULATION_SPOT_CHANCE:
            stip_spot = self._generate_stipulation_spot(attacker, defender)
            if stip_spot:
                return stip_spot

        # --- Signature move ---
        if (attacker.signature_moves and attacker.momentum > SIGNATURE_MOMENTUM_THRESHOLD
                and random.random() < SIGNATURE_CHANCE):
            sig = random.choice(attacker.signature_moves)
            if len(sig) >= 3:
                sig_name, sig_damage, sig_type = sig[0], sig[1], sig[2]
            else:
                logger.warning(f"Malformed signature move for {attacker.name}: {sig}")
                sig_name = sig[0] if sig else "Signature Move"
                sig_damage = sig[1] if len(sig) > 1 else SIGNATURE_DAMAGE_MIN
                sig_type = "power"
            attack_stat = attacker.stats.get(sig_type, STAT_BASELINE)
            damage = int(sig_damage * (attack_stat / STAT_BASELINE) * (attacker.stamina / 100))
            damage = max(SIGNATURE_DAMAGE_MIN, damage)
            return MatchSpot(
                tick=self.tick,
                attacker_id=attacker.wrestler_id,
                defender_id=defender.wrestler_id,
                move_name=sig_name,
                move_type=sig_type,
                damage=damage,
                description=f"{attacker.name} hits the {sig_name}! Signature move!",
                crowd_reaction="The crowd erupts for the signature move!",
                heat_change=random.randint(3, 6),
            )

        # --- Standard move selection ---
        category = self._pick_move_category(attacker)
        move_name, base_damage, move_type = random.choice(MOVES[category])

        # Calculate actual damage based on stats
        attack_stat = attacker.stats.get(category, STAT_BASELINE)
        defense_stat = defender.stats.get("toughness", STAT_BASELINE)
        stamina_factor = attacker.stamina / 100
        damage = int(base_damage * (attack_stat / STAT_BASELINE) * stamina_factor * (1 - defense_stat / DEFENSE_DIVISOR))
        damage = max(BASE_DAMAGE_MIN, damage)

        # Hometown advantage: small damage boost
        if attacker.hometown_bonus:
            damage = int(damage * HOMETOWN_DAMAGE_MULTIPLIER)

        # --- BOTCH CHECK: moves can go wrong ---
        is_botch, botch_severity, damage = self._check_botch(
            category, base_damage, attack_stat, attacker.stamina, damage)


        # Check for reversal
        was_reversed = False
        reversal_move = None
        reversal_chance = (
            defender.stats.get("technical", STAT_BASELINE)
            + defender.stats.get("psychology", STAT_BASELINE)
            + defender.stats.get("speed", STAT_BASELINE) * 0.5
        ) / REVERSAL_BASE_CHANCE_DIVISOR
        reversal_chance *= (defender.momentum / 100)

        if not is_botch and random.random() < reversal_chance:
            was_reversed = True
            rev_cat = self._pick_move_category(defender)
            reversal_move, rev_dmg, _ = random.choice(MOVES[rev_cat])
            damage = int(rev_dmg * REVERSAL_DAMAGE_MULTIPLIER)

        # Build description
        if is_botch:
            botch_descs = {
                1: [
                    f"{attacker.name} goes for {move_name} but stumbles slightly — lands it awkwardly on {defender.name}.",
                    f"{attacker.name} nearly misses the {move_name} — sloppier than usual.",
                    f"Slight miscommunication — {attacker.name}'s {move_name} doesn't connect cleanly.",
                ],
                2: [
                    f"{attacker.name} BOTCHES the {move_name}! That looked BAD. {defender.name} barely protected themselves.",
                    f"That {move_name} went wrong! {attacker.name} and {defender.name} are both shaken up.",
                    f"Ugly execution on the {move_name} — the crowd groans. {attacker.name} looks frustrated.",
                ],
                3: [
                    f"DANGEROUS BOTCH! {attacker.name}'s {move_name} drops {defender.name} RIGHT on their head!",
                    f"OH NO! {attacker.name}'s {move_name} goes horribly wrong — {defender.name} lands neck-first!",
                    f"SCARY MOMENT! The {move_name} from {attacker.name} was NOT supposed to land like that!",
                ],
            }
            desc = random.choice(botch_descs.get(botch_severity, botch_descs[1]))
        elif was_reversed:
            desc = f"{attacker.name} goes for {move_name}, but {defender.name} {random.choice(REVERSAL_DESCRIPTIONS)} {reversal_move}!"
        else:
            desc = f"{attacker.name} hits {defender.name} with a devastating {move_name}!"

        # Crowd reaction
        heat_change = 0
        crowd = ""
        if is_botch:
            if botch_severity >= 2:
                crowd = "The crowd goes quiet... that didn't look right."
                heat_change = -3  # Botches kill crowd heat
            elif botch_severity == 1:
                crowd = "A slight stumble there..."
                heat_change = -1
        elif damage >= HIGHLIGHT_DAMAGE_THRESHOLD or was_reversed:
            crowd = random.choice(CROWD_REACTIONS)
            heat_change = random.randint(1, 3)
            if attacker.alignment == "face" and not was_reversed:
                heat_change = abs(heat_change)
            elif attacker.alignment == "heel" and not was_reversed:
                heat_change = -abs(heat_change)

        return MatchSpot(
            tick=self.tick,
            attacker_id=attacker.wrestler_id if not was_reversed else defender.wrestler_id,
            defender_id=defender.wrestler_id if not was_reversed else attacker.wrestler_id,
            move_name=move_name if not was_reversed else reversal_move,
            move_type=move_type,
            damage=damage,
            was_reversed=was_reversed,
            reversal_move=reversal_move,
            crowd_reaction=crowd,
            heat_change=heat_change,
            description=desc,
            is_botch=is_botch,
            botch_severity=botch_severity,
        )

    def _generate_stipulation_spot(self, attacker: MatchParticipantState,
                                   defender: MatchParticipantState) -> Optional[MatchSpot]:
        """Generate a match-type-specific special spot."""
        stip = (self.stipulation or "").lower()

        if "cage" in stip or "steel cage" in stip:
            desc, base_dmg, stype = random.choice(CAGE_SPOTS)
            if stype == "escape":
                # Cage escape attempt — only works if momentum > 80
                if attacker.momentum > CAGE_ESCAPE_MOMENTUM_THRESHOLD and attacker.health > 40:
                    return MatchSpot(
                        tick=self.tick, attacker_id=attacker.wrestler_id,
                        defender_id=defender.wrestler_id,
                        move_name="Cage Escape Attempt", move_type="technical",
                        damage=0,
                        description=f"{attacker.name} is climbing the cage! Can they escape?!",
                        crowd_reaction="The crowd is on their feet!",
                        heat_change=5,
                    )
                return None
            return self._build_stipulation_hit(attacker, defender, desc, base_dmg, "brawling",
                                               "Cage Spot", "brawling", 3, CROWD_REACTIONS, (2, 5))

        elif "ladder" in stip:
            desc, base_dmg, stype = random.choice(LADDER_SPOTS)
            if stype == "climb":
                if attacker.momentum > LADDER_CLIMB_MOMENTUM_THRESHOLD:
                    return self._build_special_stip_spot(attacker, defender,
                        "Ladder Climb", "aerial",
                        f"{attacker.name} is climbing the ladder! Fingers inches from the prize!",
                        "This could be it!", 6)
                return None
            return self._build_stipulation_hit(attacker, defender, desc, base_dmg, "power",
                                               "Ladder Spot", stype, 5, ["OH MY GOD!"], (3, 7))

        elif "table" in stip:
            desc, base_dmg, stype = random.choice(TABLE_SPOTS)
            if stype == "setup":
                return self._build_special_stip_spot(attacker, defender,
                    "Table Setup", "power",
                    f"{attacker.name} {desc}!",
                    "The crowd knows what's coming!", 3)
            return self._build_stipulation_hit(attacker, defender, desc, base_dmg, "power",
                                               "Table Spot", stype, 8, ["THROUGH THE TABLE!"], (5, 8))

        elif "hell" in stip or "cell" in stip:
            desc, base_dmg, stype = random.choice(HELL_IN_A_CELL_SPOTS)
            if stype == "climb":
                return self._build_special_stip_spot(attacker, defender,
                    "Cell Climb", "aerial",
                    f"{attacker.name} {desc}! This is getting dangerous!",
                    "Don't do it! DON'T DO IT!", 7)
            return self._build_stipulation_hit(attacker, defender, desc, base_dmg, "brawling",
                                               "Cell Spot", stype, 5, ["GOOD GOD ALMIGHTY!"], (4, 8))

        return None

    def _build_special_stip_spot(self, attacker, defender, move_name, move_type,
                                  description, crowd_reaction, heat_change):
        """Build a zero-damage stipulation spot (escapes, climbs, setups)."""
        return MatchSpot(
            tick=self.tick, attacker_id=attacker.wrestler_id,
            defender_id=defender.wrestler_id,
            move_name=move_name, move_type=move_type,
            damage=0, description=description,
            crowd_reaction=crowd_reaction, heat_change=heat_change,
        )

    def _build_stipulation_hit(self, attacker, defender, desc, base_dmg, stat_key,
                                move_name, move_type, min_damage, reactions, heat_range):
        """Build a damage-dealing stipulation spot with stat scaling."""
        damage = int(base_dmg * self._stat_multiplier(attacker, stat_key))
        reaction = random.choice(reactions) if isinstance(reactions, list) else reactions
        return MatchSpot(
            tick=self.tick, attacker_id=attacker.wrestler_id,
            defender_id=defender.wrestler_id,
            move_name=move_name, move_type=move_type,
            damage=max(min_damage, damage),
            description=f"{attacker.name} {desc}!",
            crowd_reaction=reaction,
            heat_change=random.randint(*heat_range),
        )

    def _check_botch(self, category: str, base_damage: int, attack_stat: int,
                      stamina: float, damage: int) -> tuple:
        """Check if a move is botched. Returns (is_botch, severity, modified_damage)."""
        move_difficulty = base_damage / 15.0
        if category == "aerial":
            move_difficulty += BOTCH_AERIAL_BONUS
        fatigue_factor = max(0, (100 - stamina) / 200)
        skill_factor = max(0, (100 - attack_stat) / 300)
        trust_factor = getattr(self, '_trust_penalty', 0.0)

        botch_chance = (move_difficulty * BOTCH_DIFFICULTY_FACTOR) + fatigue_factor + skill_factor + trust_factor
        botch_chance = min(BOTCH_MAX_CHANCE, botch_chance)

        if random.random() >= botch_chance:
            return False, 0, damage

        severity_roll = random.random()
        if severity_roll < BOTCH_MINOR_THRESHOLD:
            return True, 1, max(1, damage // 2)
        elif severity_roll < BOTCH_BAD_THRESHOLD:
            return True, 2, max(1, damage // 3)
        else:
            return True, 3, int(damage * DANGEROUS_BOTCH_DAMAGE_MULTIPLIER)

    def _stat_multiplier(self, wrestler: MatchParticipantState, stat_key: str) -> float:
        """Get damage multiplier from a wrestler's stat vs baseline."""
        return wrestler.stats.get(stat_key, STAT_BASELINE) / STAT_BASELINE

    def _update_momentum(self, wrestler: MatchParticipantState, delta: float):
        """Apply momentum change clamped to 0-100."""
        wrestler.momentum = max(0, min(100, wrestler.momentum + delta))

    def _pick_move_category(self, wrestler: MatchParticipantState) -> str:
        """Pick a move category weighted by wrestler's stats."""
        categories = ["power", "technical", "aerial", "brawling", "submission"]
        weights = [wrestler.stats.get(c, STAT_BASELINE) for c in categories]
        total = sum(weights)
        if total <= 0:
            return random.choice(categories)
        weights = [w / total for w in weights]
        return random.choices(categories, weights=weights, k=1)[0]

    def _apply_spot(self, spot: MatchSpot, attacker: MatchParticipantState,
                    defender: MatchParticipantState):
        """Apply the effects of a spot to participant states."""
        if spot.was_reversed:
            # Reversal: attacker takes damage, defender gains momentum
            attacker.health -= spot.damage
            self._update_momentum(defender, REVERSAL_MOMENTUM_GAIN)
            self._update_momentum(attacker, -REVERSAL_MOMENTUM_LOSS)
        else:
            # Normal: defender takes damage, attacker gains momentum
            defender.health -= spot.damage
            self._update_momentum(attacker, NORMAL_HIT_MOMENTUM_GAIN)
            self._update_momentum(defender, -NORMAL_HIT_MOMENTUM_LOSS)

        # Stamina drain
        attacker.stamina = max(STAMINA_FLOOR, attacker.stamina - random.uniform(
            ATTACKER_STAMINA_DRAIN_MIN, ATTACKER_STAMINA_DRAIN_MAX))
        defender.stamina = max(STAMINA_FLOOR, defender.stamina - random.uniform(
            DEFENDER_STAMINA_DRAIN_MIN, DEFENDER_STAMINA_DRAIN_MAX))

        # Endurance drain (tracks cumulative damage for multi-person eliminations)
        if not spot.was_reversed:
            defender.endurance = max(0, defender.endurance - spot.damage * ENDURANCE_DRAIN_FACTOR)
        else:
            attacker.endurance = max(0, attacker.endurance - spot.damage * ENDURANCE_DRAIN_FACTOR)

    def _should_switch_control(self, attacker: MatchParticipantState,
                               defender: MatchParticipantState) -> bool:
        """Determine if offensive control should switch."""
        # Psychology stat helps maintain control
        hold_chance = attacker.stats.get("psychology", STAT_BASELINE) / 100
        comeback_chance = defender.stats.get("stamina", STAT_BASELINE) / 200
        comeback_chance += defender.stats.get("speed", STAT_BASELINE) / 400  # Fast wrestlers escape faster

        # Lower health = more likely to mount comeback (fighting spirit)
        if defender.health < COMEBACK_LOW_HEALTH_THRESHOLD:
            comeback_chance += COMEBACK_LOW_HEALTH_BONUS

        return random.random() > hold_chance or random.random() < comeback_chance

    def _attempt_finish(self, attacker: MatchParticipantState,
                        defender: MatchParticipantState) -> Optional[MatchSpot]:
        """Attempt to finish the match.

        Includes "going into business" mechanic: a wrestler with high ego,
        high frustration, and low morale may refuse to lose as planned,
        shooting on their opponent to win when they were supposed to lose.
        """
        # Determine if this is the right person to win
        should_win = True
        if self.planned_winner_id and attacker.wrestler_id != self.planned_winner_id:
            # Not the planned winner — much less likely to hit finish
            should_win = random.random() < UPSET_CHANCE

            # --- GOING INTO BUSINESS: wrestler refuses to do the job ---
            # Check if this wrestler has the ego/frustration to go into business
            ego = attacker.stats.get("ego", STAT_BASELINE)
            frustration = getattr(attacker, '_frustration', 0)
            morale_mod = getattr(attacker, '_morale', STAT_BASELINE)

            # Conditions: high ego + high frustration + low morale + title match stakes
            shoot_chance = 0.0
            if ego > SHOOT_EGO_THRESHOLD:
                shoot_chance += (ego - SHOOT_EGO_THRESHOLD) / 300  # Up to ~0.10
            if frustration > SHOOT_FRUSTRATION_THRESHOLD:
                shoot_chance += (frustration - SHOOT_FRUSTRATION_THRESHOLD) / 400  # Up to ~0.10
            if morale_mod < SHOOT_MORALE_THRESHOLD:
                shoot_chance += (SHOOT_MORALE_THRESHOLD - morale_mod) / 300  # Up to ~0.10
            if self.is_title_match:
                shoot_chance *= SHOOT_TITLE_MULTIPLIER

            shoot_chance = min(SHOOT_MAX_CHANCE, shoot_chance)

            if shoot_chance > 0 and random.random() < shoot_chance:
                # GOING INTO BUSINESS — wrestler refuses to lose
                self._shoot_occurred = True
                self._shoot_wrestler_id = attacker.wrestler_id
                should_win = True  # They're going to win whether planned or not

                desc = (
                    f"{attacker.name} was supposed to lose — but they're NOT going down! "
                    f"{attacker.name} hits the {attacker.finisher_name} with REAL intent! "
                    f"This was NOT in the script!"
                )
                return MatchSpot(
                    tick=self.tick,
                    attacker_id=attacker.wrestler_id,
                    defender_id=defender.wrestler_id,
                    move_name=attacker.finisher_name,
                    move_type="finisher",
                    damage=SHOOT_FINISHER_DAMAGE,
                    is_finisher=True,
                    is_finish=True,
                    finish_type="pinfall",
                    crowd_reaction="The crowd doesn't know what just happened... something felt WRONG.",
                    heat_change=8,
                    description=desc,
                    is_shoot=True,
                )

        if not should_win:
            return None

        # Check if attacker can hit their finisher
        finish_chance = FINISH_BASE_CHANCE
        if attacker.finisher_available:
            finish_chance = FINISH_FINISHER_READY_CHANCE
        if defender.health < DEFENDER_LOW_HEALTH_THRESHOLD:
            finish_chance += FINISH_LOW_HEALTH_BONUS
        if attacker.momentum > FINISH_MOMENTUM_BONUS_THRESHOLD:
            finish_chance += FINISH_HIGH_MOMENTUM_BONUS

        if random.random() > finish_chance:
            return None

        # Finisher hits!
        if self.planned_finish == "submission":
            desc = f"{attacker.name} locks in the {attacker.finisher_name}! {defender.name} struggles... and taps out!"
            finish_type = "submission"
        else:
            desc = f"{attacker.name} hits the {attacker.finisher_name}! Covers {defender.name}... ONE... TWO... THREE! It's over!"
            finish_type = "pinfall"

        return MatchSpot(
            tick=self.tick,
            attacker_id=attacker.wrestler_id,
            defender_id=defender.wrestler_id,
            move_name=attacker.finisher_name,
            move_type="finisher",
            damage=FINISHER_DAMAGE,
            is_finisher=True,
            is_finish=True,
            finish_type=finish_type,
            crowd_reaction="The crowd erupts as the match is over!",
            heat_change=5,
            description=desc,
        )

    def _near_fall(self, attacker: MatchParticipantState,
                   defender: MatchParticipantState) -> Optional[MatchSpot]:
        """Generate a near-fall spot."""
        if defender.health > NEAR_FALL_HEALTH_THRESHOLD:
            return None

        desc = f"{attacker.name} covers! {random.choice(NEAR_FALL_DESCRIPTIONS)}"
        return MatchSpot(
            tick=self.tick,
            attacker_id=attacker.wrestler_id,
            defender_id=defender.wrestler_id,
            move_name="Pin Attempt",
            move_type="pin",
            damage=0,
            is_near_fall=True,
            crowd_reaction="The crowd thought that was it!",
            heat_change=3,
            description=desc,
        )

    def _attempt_interference(self, attacker: MatchParticipantState,
                              defender: MatchParticipantState) -> Optional[MatchSpot]:
        """Check if a manager at ringside interferes."""
        if self._interference_happened or not self.managers:
            return None

        for mgr in self.managers:
            # Manager only helps their client (the attacker in this context)
            if mgr.client_wrestler_id != attacker.wrestler_id:
                continue

            # Interference chance based on manager's skill
            base_chance = mgr.interference_skill / 100.0
            cunning_bonus = mgr.cunning / 200.0
            chance = base_chance * 0.4 + cunning_bonus * 0.2 + 0.05
            chance = min(INTERFERENCE_MAX_CHANCE, chance)

            if random.random() > chance:
                continue

            self._interference_happened = True

            # Did they get caught?
            caught = random.random() < INTERFERENCE_CATCH_CHANCE
            if caught:
                # DQ finish — defender wins by disqualification
                if random.random() < INTERFERENCE_DQ_CHANCE:
                    self._dq_triggered = True
                    desc = random.choice(INTERFERENCE_CAUGHT).format(
                        mgr=mgr.manager_name, attacker=attacker.name,
                        defender=defender.name
                    )
                    return MatchSpot(
                        tick=self.tick, attacker_id=defender.wrestler_id,
                        defender_id=attacker.wrestler_id,
                        move_name="Disqualification",
                        move_type="interference", damage=0,
                        is_finish=True, finish_type="disqualification",
                        crowd_reaction="The crowd is furious!",
                        heat_change=-5,
                        description=desc,
                    )
                else:
                    # Caught but only warned/ejected
                    desc = random.choice(INTERFERENCE_FAIL).format(
                        mgr=mgr.manager_name, defender=defender.name
                    )
                    return MatchSpot(
                        tick=self.tick, attacker_id=attacker.wrestler_id,
                        defender_id=defender.wrestler_id,
                        move_name="Failed Interference",
                        move_type="interference", damage=0,
                        crowd_reaction="The referee is on to the tricks!",
                        heat_change=2,
                        description=desc,
                    )
            else:
                # Successful interference — bonus damage + momentum
                desc = random.choice(INTERFERENCE_SUCCESS).format(
                    mgr=mgr.manager_name, attacker=attacker.name,
                    defender=defender.name
                )
                defender.health -= INTERFERENCE_DAMAGE
                self._update_momentum(defender, -INTERFERENCE_MOMENTUM_LOSS)
                self._update_momentum(attacker, INTERFERENCE_MOMENTUM_GAIN)
                return MatchSpot(
                    tick=self.tick, attacker_id=attacker.wrestler_id,
                    defender_id=defender.wrestler_id,
                    move_name="Manager Interference",
                    move_type="interference", damage=INTERFERENCE_DAMAGE,
                    crowd_reaction="The crowd boos the cheating!",
                    heat_change=-3 if attacker.alignment == "heel" else 2,
                    description=desc,
                )

        return None

    def _calculate_rating(self, participants: List[MatchParticipantState]) -> float:
        """Calculate match star rating (0.0 - 5.0).  Delegates to match_rating module."""
        from core_engine.match_rating import calculate_rating
        return calculate_rating(
            self.spots, self.is_title_match, self.rivalry_heat,
            self._interference_happened, self.stipulation,
            self.show_momentum, self.tick, participants,
        )

    def _calculate_heat(self) -> int:
        """Calculate final crowd heat level.  Delegates to match_rating module."""
        from core_engine.match_rating import calculate_heat
        return calculate_heat(self.spots, self.show_momentum, self.rivalry_heat)

    def _build_result(self, finish_spot: MatchSpot, attacker: MatchParticipantState,
                      defender: MatchParticipantState,
                      participants: List[MatchParticipantState]) -> MatchResult:
        """Build the final MatchResult."""
        # Generate narrative summary
        highlights = [s for s in self.spots if s.damage >= HIGHLIGHT_DAMAGE_THRESHOLD or s.is_near_fall or s.is_finisher]
        narrative_parts = [s.description for s in highlights[-5:]]  # Last 5 highlights
        narrative = " ".join(narrative_parts)

        # LLM-as-journalist: generate a vivid match narrative
        import os
        if os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes"):
            try:
                from game_service.character_agent import generate_match_narrative
                llm_narrative = generate_match_narrative(
                    winner_name=attacker.name,
                    loser_name=defender.name,
                    finish_type=finish_spot.finish_type or "pinfall",
                    finish_description=finish_spot.description,
                    rating=self._calculate_rating(participants),
                    key_spots=narrative_parts,
                    stipulation=self.stipulation or "",
                    is_title_match=self.is_title_match,
                )
                if llm_narrative and len(llm_narrative.strip()) > 20:
                    narrative = llm_narrative
            except Exception:
                pass  # Keep template narrative

        # Collect botch events for post-match processing
        botch_events = []
        botch_count = 0
        for s in self.spots:
            if s.is_botch:
                botch_count += 1
                botch_events.append({
                    "attacker_id": s.attacker_id,
                    "victim_id": s.defender_id,
                    "severity": s.botch_severity,
                    "move": s.move_name,
                    "tick": s.tick,
                })

        # Botches hurt match rating
        rating = self._calculate_rating(participants)
        if botch_count > 0:
            botch_penalty = botch_count * BOTCH_RATING_PENALTY_PER
            for be in botch_events:
                if be["severity"] >= 3:
                    botch_penalty += DANGEROUS_BOTCH_EXTRA_PENALTY
            rating = max(RATING_MIN, rating - botch_penalty)
            rating = round(rating, 1)

        return MatchResult(
            winner_id=finish_spot.attacker_id,
            finish_type=finish_spot.finish_type or "pinfall",
            finish_description=finish_spot.description,
            match_rating=rating,
            crowd_heat=self._calculate_heat(),
            duration_ticks=self.tick,
            spots=self.spots,
            narrative_summary=narrative,
            interference_occurred=self._interference_happened,
            botch_count=botch_count,
            botch_events=botch_events,
            went_into_business=self._shoot_occurred,
            shoot_wrestler_id=self._shoot_wrestler_id,
        )


# ---------------------------------------------------------------------------
# DB integration functions — delegated to match_db_integration module.
# Re-exported here for backward compatibility.
# ---------------------------------------------------------------------------

from core_engine.match_db_integration import (  # noqa: E402
    _build_stat_modifiers,
    simulate_match_from_db,
    _generate_post_match_angle,
)
