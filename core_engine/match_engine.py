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
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB, WrestlerStatsDB, MatchDB, MatchParticipantDB,
    MatchEventDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Move databases
# ---------------------------------------------------------------------------

MOVES = {
    "power": [
        ("Powerbomb", 12, "power"), ("Suplex", 8, "power"),
        ("Bodyslam", 6, "power"), ("Clothesline", 7, "power"),
        ("Spinebuster", 10, "power"), ("Gorilla Press", 9, "power"),
        ("Big Boot", 7, "power"), ("Chokeslam", 11, "power"),
    ],
    "technical": [
        ("Arm Drag", 4, "technical"), ("Suplex Combo", 9, "technical"),
        ("German Suplex", 10, "technical"), ("Snap Mare", 3, "technical"),
        ("Dragon Screw", 7, "technical"), ("Backbreaker", 8, "technical"),
        ("Neckbreaker", 7, "technical"), ("Brainbuster", 11, "technical"),
    ],
    "aerial": [
        ("Dropkick", 6, "aerial"), ("Moonsault", 11, "aerial"),
        ("Diving Crossbody", 9, "aerial"), ("Hurricanrana", 8, "aerial"),
        ("450 Splash", 12, "aerial"), ("Springboard Elbow", 8, "aerial"),
        ("Frog Splash", 10, "aerial"), ("Shooting Star Press", 13, "aerial"),
    ],
    "brawling": [
        ("Right Hand", 4, "brawling"), ("Uppercut", 5, "brawling"),
        ("Knee Strike", 7, "brawling"), ("Elbow Smash", 6, "brawling"),
        ("Headbutt", 5, "brawling"), ("Lariat", 9, "brawling"),
        ("Running Knee", 10, "brawling"), ("Discus Punch", 8, "brawling"),
    ],
    "submission": [
        ("Armbar", 6, "submission"), ("Figure Four", 8, "submission"),
        ("Sharpshooter", 9, "submission"), ("Crossface", 8, "submission"),
        ("Sleeper Hold", 5, "submission"), ("Ankle Lock", 9, "submission"),
        ("Kimura", 7, "submission"), ("Triangle Choke", 8, "submission"),
    ],
}

CROWD_REACTIONS = [
    "The crowd erupts!", "Huge pop from the fans!", "The audience is on their feet!",
    "Mixed reaction from the crowd.", "The fans are booing loudly!",
    "Chants break out across the arena!", "Stunned silence from the crowd.",
    "The energy in the building is electric!", "The crowd is split down the middle!",
]

REVERSAL_DESCRIPTIONS = [
    "ducks and counters with", "reverses into", "blocks and hits",
    "sidesteps and delivers", "catches the leg and transitions to",
]

NEAR_FALL_DESCRIPTIONS = [
    "Goes for the cover! ONE... TWO... kickout at the last moment!",
    "Hooks the leg! ONE... TWO... shoulder up just in time!",
    "Lateral press! ONE... TWO... NO! They stay alive!",
    "Quick pin attempt! ONE... TWO... power out!",
]

TAG_DESCRIPTIONS = [
    "tags in their partner",
    "reaches out and makes the tag",
    "dives and makes the hot tag",
    "slaps hands with their partner",
]

DOUBLE_TEAM_MOVES = [
    ("Double Suplex", 14), ("Double Clothesline", 10),
    ("Aided Powerbomb", 16), ("Tandem Neckbreaker", 12),
    ("Double Dropkick", 11), ("Combo Finisher", 18),
]


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
    finisher_available: bool = False
    finisher_used: bool = False
    stats: Dict[str, int] = field(default_factory=dict)
    finisher_name: str = "Finisher"
    alignment: str = "face"
    team: Optional[int] = None


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
                 stipulation: str = None):
        self.planned_winner_id = planned_winner_id
        self.planned_finish = planned_finish or "pinfall"
        self.card_position = card_position
        self.is_title_match = is_title_match
        self.stipulation = stipulation
        self.spots: List[MatchSpot] = []
        self.tick = 0

    def simulate(self, participants: List[MatchParticipantState]) -> MatchResult:
        """Run the full match simulation."""
        if len(participants) < 2:
            return MatchResult(narrative_summary="Match cancelled - not enough participants")

        # Detect tag match: 4+ participants with team assignments
        teams = set(p.team for p in participants if p.team is not None)
        if len(teams) >= 2 and len(participants) >= 4:
            return self._simulate_tag_match(participants)

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

            if not attacker.finisher_available and attacker.momentum > 75:
                attacker.finisher_available = True

            if self.tick >= target_length - 3:
                finish_spot = self._attempt_finish(attacker, defender)
                if finish_spot:
                    self.spots.append(finish_spot)
                    return self._build_result(finish_spot, attacker, defender, participants)

            if self.tick > target_length * 0.6 and random.random() < 0.25:
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

    def _simulate_tag_match(self, participants: List[MatchParticipantState]) -> MatchResult:
        """Simulate a tag team match with legal man tracking, tags, hot tags, and double-team spots."""
        team_map: Dict[int, List[MatchParticipantState]] = {}
        for p in participants:
            team_id = p.team if p.team is not None else 0
            team_map.setdefault(team_id, []).append(p)

        team_ids = sorted(team_map.keys())
        if len(team_ids) < 2:
            return self._simulate_singles(participants)

        team_a = team_map[team_ids[0]]
        team_b = team_map[team_ids[1]]

        # Legal men: index 0 from each team starts
        legal_a_idx = 0
        legal_b_idx = 0

        # Track how long each legal man has been in (for hot tag mechanic)
        ticks_in_a = 0
        ticks_in_b = 0

        # Tag matches run slightly longer
        min_len, max_len = self.MATCH_LENGTH.get(self.card_position, (10, 20))
        target_length = random.randint(min_len + 3, max_len + 5)

        # Who's on offense: 0 = team_a attacks, 1 = team_b attacks
        attacking_team = 0

        while self.tick < target_length + 10:
            self.tick += 1
            ticks_in_a += 1
            ticks_in_b += 1

            attacker = team_a[legal_a_idx] if attacking_team == 0 else team_b[legal_b_idx]
            defender = team_b[legal_b_idx] if attacking_team == 0 else team_a[legal_a_idx]

            # --- Tag-in opportunity (attacking team tags to bring fresh partner) ---
            ticks_in = ticks_in_a if attacking_team == 0 else ticks_in_b
            if ticks_in > 5 and attacker.stamina < 60 and random.random() < 0.35:
                if attacking_team == 0 and len(team_a) > 1:
                    legal_a_idx = (legal_a_idx + 1) % len(team_a)
                    ticks_in_a = 0
                    new_wrestler = team_a[legal_a_idx]
                    new_wrestler.momentum = min(100, new_wrestler.momentum + 10)
                    self.spots.append(MatchSpot(
                        tick=self.tick, attacker_id=new_wrestler.wrestler_id,
                        defender_id=defender.wrestler_id, move_name="Tag",
                        move_type="tag", damage=0,
                        crowd_reaction="Tag made!", heat_change=1,
                        description=f"{attacker.name} {random.choice(TAG_DESCRIPTIONS)}! {new_wrestler.name} enters the ring!",
                    ))
                    attacker = new_wrestler
                elif attacking_team == 1 and len(team_b) > 1:
                    legal_b_idx = (legal_b_idx + 1) % len(team_b)
                    ticks_in_b = 0
                    new_wrestler = team_b[legal_b_idx]
                    new_wrestler.momentum = min(100, new_wrestler.momentum + 10)
                    self.spots.append(MatchSpot(
                        tick=self.tick, attacker_id=new_wrestler.wrestler_id,
                        defender_id=defender.wrestler_id, move_name="Tag",
                        move_type="tag", damage=0,
                        crowd_reaction="Tag made!", heat_change=1,
                        description=f"{attacker.name} {random.choice(TAG_DESCRIPTIONS)}! {new_wrestler.name} enters the ring!",
                    ))
                    attacker = new_wrestler

            # --- Hot tag mechanic (defending team, beaten down, makes desperate tag) ---
            defending_ticks = ticks_in_b if attacking_team == 0 else ticks_in_a
            if defending_ticks > 6 and defender.health < 50 and random.random() < 0.3:
                if attacking_team == 0 and len(team_b) > 1:
                    legal_b_idx = (legal_b_idx + 1) % len(team_b)
                    ticks_in_b = 0
                    hot_tag = team_b[legal_b_idx]
                    hot_tag.momentum = min(100, hot_tag.momentum + 25)
                    hot_tag.finisher_available = True
                    self.spots.append(MatchSpot(
                        tick=self.tick, attacker_id=hot_tag.wrestler_id,
                        defender_id=attacker.wrestler_id, move_name="Hot Tag",
                        move_type="tag", damage=0,
                        crowd_reaction="The crowd erupts for the hot tag!",
                        heat_change=4,
                        description=f"{defender.name} desperately reaches out... HOT TAG! {hot_tag.name} storms into the ring on fire!",
                    ))
                    attacking_team = 1
                    defender = attacker
                    attacker = hot_tag
                elif attacking_team == 1 and len(team_a) > 1:
                    legal_a_idx = (legal_a_idx + 1) % len(team_a)
                    ticks_in_a = 0
                    hot_tag = team_a[legal_a_idx]
                    hot_tag.momentum = min(100, hot_tag.momentum + 25)
                    hot_tag.finisher_available = True
                    self.spots.append(MatchSpot(
                        tick=self.tick, attacker_id=hot_tag.wrestler_id,
                        defender_id=attacker.wrestler_id, move_name="Hot Tag",
                        move_type="tag", damage=0,
                        crowd_reaction="The crowd erupts for the hot tag!",
                        heat_change=4,
                        description=f"{defender.name} desperately reaches out... HOT TAG! {hot_tag.name} storms into the ring on fire!",
                    ))
                    attacking_team = 0
                    defender = attacker
                    attacker = hot_tag

            # --- Double-team opportunity (both partners briefly in ring) ---
            if random.random() < 0.12:
                if attacking_team == 0 and len(team_a) > 1:
                    partner = team_a[(legal_a_idx + 1) % len(team_a)]
                    move_name, dmg = random.choice(DOUBLE_TEAM_MOVES)
                    dt_spot = MatchSpot(
                        tick=self.tick, attacker_id=attacker.wrestler_id,
                        defender_id=defender.wrestler_id, move_name=move_name,
                        move_type="power", damage=dmg,
                        crowd_reaction="Incredible double-team!",
                        heat_change=3,
                        description=f"{attacker.name} and {partner.name} hit a {move_name} on {defender.name}!",
                    )
                    self.spots.append(dt_spot)
                    self._apply_spot(dt_spot, attacker, defender)
                    continue
                elif attacking_team == 1 and len(team_b) > 1:
                    partner = team_b[(legal_b_idx + 1) % len(team_b)]
                    move_name, dmg = random.choice(DOUBLE_TEAM_MOVES)
                    dt_spot = MatchSpot(
                        tick=self.tick, attacker_id=attacker.wrestler_id,
                        defender_id=defender.wrestler_id, move_name=move_name,
                        move_type="power", damage=dmg,
                        crowd_reaction="Incredible double-team!",
                        heat_change=3,
                        description=f"{attacker.name} and {partner.name} hit a {move_name} on {defender.name}!",
                    )
                    self.spots.append(dt_spot)
                    self._apply_spot(dt_spot, attacker, defender)
                    continue

            # --- Normal spot ---
            spot = self._generate_spot(attacker, defender)
            self.spots.append(spot)
            self._apply_spot(spot, attacker, defender)

            if not attacker.finisher_available and attacker.momentum > 75:
                attacker.finisher_available = True

            if self.tick >= target_length - 3:
                finish_spot = self._attempt_finish(attacker, defender)
                if finish_spot:
                    self.spots.append(finish_spot)
                    return self._build_result(finish_spot, attacker, defender, participants)

            if self.tick > target_length * 0.6 and random.random() < 0.25:
                near_fall = self._near_fall(attacker, defender)
                if near_fall:
                    self.spots.append(near_fall)

            if self._should_switch_control(attacker, defender):
                attacking_team = 1 - attacking_team

        return MatchResult(
            winner_id=None,
            finish_type="time_limit_draw",
            finish_description="The tag team match ends in a time limit draw!",
            match_rating=self._calculate_rating(participants),
            crowd_heat=self._calculate_heat(),
            duration_ticks=self.tick,
            spots=self.spots,
        )

    def _generate_spot(self, attacker: MatchParticipantState,
                       defender: MatchParticipantState) -> MatchSpot:
        """Generate a single match spot."""
        # Pick move category based on attacker's strongest stats
        category = self._pick_move_category(attacker)
        move_name, base_damage, move_type = random.choice(MOVES[category])

        # Calculate actual damage based on stats
        attack_stat = attacker.stats.get(category, 50)
        defense_stat = defender.stats.get("toughness", 50)
        stamina_factor = attacker.stamina / 100
        damage = int(base_damage * (attack_stat / 50) * stamina_factor * (1 - defense_stat / 200))
        damage = max(1, damage)

        # Check for reversal
        was_reversed = False
        reversal_move = None
        reversal_chance = (defender.stats.get("technical", 50) + defender.stats.get("psychology", 50)) / 400
        reversal_chance *= (defender.momentum / 100)

        if random.random() < reversal_chance:
            was_reversed = True
            rev_cat = self._pick_move_category(defender)
            reversal_move, rev_dmg, _ = random.choice(MOVES[rev_cat])
            damage = int(rev_dmg * 0.7)  # Reversals do less damage

        # Build description
        if was_reversed:
            desc = f"{attacker.name} goes for {move_name}, but {defender.name} {random.choice(REVERSAL_DESCRIPTIONS)} {reversal_move}!"
        else:
            desc = f"{attacker.name} hits {defender.name} with a devastating {move_name}!"

        # Crowd reaction
        heat_change = 0
        crowd = ""
        if damage >= 10 or was_reversed:
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
        )

    def _pick_move_category(self, wrestler: MatchParticipantState) -> str:
        """Pick a move category weighted by wrestler's stats."""
        categories = ["power", "technical", "aerial", "brawling", "submission"]
        weights = [wrestler.stats.get(c, 50) for c in categories]
        total = sum(weights)
        weights = [w / total for w in weights]
        return random.choices(categories, weights=weights, k=1)[0]

    def _apply_spot(self, spot: MatchSpot, attacker: MatchParticipantState,
                    defender: MatchParticipantState):
        """Apply the effects of a spot to participant states."""
        if spot.was_reversed:
            # Reversal: attacker takes damage, defender gains momentum
            attacker.health -= spot.damage
            defender.momentum = min(100, defender.momentum + 8)
            attacker.momentum = max(0, attacker.momentum - 8)
        else:
            # Normal: defender takes damage, attacker gains momentum
            defender.health -= spot.damage
            attacker.momentum = min(100, attacker.momentum + 5)
            defender.momentum = max(0, defender.momentum - 3)

        # Stamina drain
        attacker.stamina = max(0, attacker.stamina - random.uniform(1.5, 3.5))
        defender.stamina = max(0, defender.stamina - random.uniform(0.5, 1.5))

    def _should_switch_control(self, attacker: MatchParticipantState,
                               defender: MatchParticipantState) -> bool:
        """Determine if offensive control should switch."""
        # Psychology stat helps maintain control
        hold_chance = attacker.stats.get("psychology", 50) / 100
        comeback_chance = defender.stats.get("stamina", 50) / 200

        # Lower health = more likely to mount comeback (fighting spirit)
        if defender.health < 40:
            comeback_chance += 0.15

        return random.random() > hold_chance or random.random() < comeback_chance

    def _attempt_finish(self, attacker: MatchParticipantState,
                        defender: MatchParticipantState) -> Optional[MatchSpot]:
        """Attempt to finish the match."""
        # Determine if this is the right person to win
        should_win = True
        if self.planned_winner_id and attacker.wrestler_id != self.planned_winner_id:
            # Not the planned winner — much less likely to hit finish
            should_win = random.random() < 0.08  # 8% chance of upset

        if not should_win:
            return None

        # Check if attacker can hit their finisher
        finish_chance = 0.3
        if attacker.finisher_available:
            finish_chance = 0.6
        if defender.health < 30:
            finish_chance += 0.3
        if attacker.momentum > 80:
            finish_chance += 0.2

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
            damage=20,
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
        if defender.health > 50:
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

    def _calculate_rating(self, participants: List[MatchParticipantState]) -> float:
        """Calculate match star rating (0.0 - 5.0)."""
        # Base: average of participants' psychology and selling
        avg_psychology = sum(p.stats.get("psychology", 50) for p in participants) / len(participants)
        avg_selling = sum(p.stats.get("selling", 50) for p in participants) / len(participants)

        base_quality = (avg_psychology + avg_selling) / 100  # 0-1 scale

        # Bonus for spot variety
        move_types_used = set(s.move_type for s in self.spots if not s.was_reversed)
        variety_bonus = min(len(move_types_used) * 0.1, 0.5)

        # Bonus for near falls
        near_falls = sum(1 for s in self.spots if s.is_near_fall)
        near_fall_bonus = min(near_falls * 0.15, 0.5)

        # Bonus for reversals (back-and-forth action)
        reversals = sum(1 for s in self.spots if s.was_reversed)
        reversal_bonus = min(reversals * 0.08, 0.4)

        # Match length bonus
        length_bonus = min(self.tick / 30, 0.3) if self.tick > 10 else 0

        # Title match bonus
        title_bonus = 0.3 if self.is_title_match else 0

        rating = (base_quality * 2.5) + variety_bonus + near_fall_bonus + reversal_bonus + length_bonus + title_bonus
        rating = min(5.0, max(0.5, rating + random.uniform(-0.3, 0.3)))
        return round(rating, 1)

    def _calculate_heat(self) -> int:
        """Calculate final crowd heat level."""
        base = 50
        for spot in self.spots:
            base += spot.heat_change
        return max(0, min(100, base))

    def _build_result(self, finish_spot: MatchSpot, attacker: MatchParticipantState,
                      defender: MatchParticipantState,
                      participants: List[MatchParticipantState]) -> MatchResult:
        """Build the final MatchResult."""
        # Generate narrative summary
        highlights = [s for s in self.spots if s.damage >= 10 or s.is_near_fall or s.is_finisher]
        narrative_parts = [s.description for s in highlights[-5:]]  # Last 5 highlights
        narrative = " ".join(narrative_parts)

        return MatchResult(
            winner_id=finish_spot.attacker_id,
            finish_type=finish_spot.finish_type or "pinfall",
            finish_description=finish_spot.description,
            match_rating=self._calculate_rating(participants),
            crowd_heat=self._calculate_heat(),
            duration_ticks=self.tick,
            spots=self.spots,
            narrative_summary=narrative,
        )


# ---------------------------------------------------------------------------
# Helper: Run a match from DB models
# ---------------------------------------------------------------------------

def simulate_match_from_db(db: Session, match: MatchDB, game_date: str = None) -> MatchResult:
    """Load match data from DB, simulate, and persist results."""
    participants_db = db.query(MatchParticipantDB).filter(
        MatchParticipantDB.match_id == match.id,
        MatchParticipantDB.role == "competitor",
    ).all()

    if len(participants_db) < 2:
        return MatchResult(narrative_summary="Not enough competitors")

    # Build participant states with morale modifier
    participant_states = []
    for p in participants_db:
        wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == p.wrestler_id).first()
        stats = db.query(WrestlerStatsDB).filter(WrestlerStatsDB.wrestler_id == p.wrestler_id).first()

        if not wrestler or not stats:
            continue

        # Morale affects performance: range 0.85 to 1.15
        morale = wrestler.morale if wrestler.morale is not None else 50
        stat_modifier = 0.85 + (morale / 100) * 0.3

        state = MatchParticipantState(
            wrestler_id=wrestler.id,
            name=wrestler.name,
            health=wrestler.condition,  # Current condition affects match health
            stats={
                "power": int(stats.power * stat_modifier),
                "technical": int(stats.technical * stat_modifier),
                "aerial": int(stats.aerial * stat_modifier),
                "brawling": int(stats.brawling * stat_modifier),
                "submission": int(stats.submission * stat_modifier),
                "stamina": int(stats.stamina * stat_modifier),
                "toughness": int(stats.toughness * stat_modifier),
                "speed": int(stats.speed * stat_modifier),
                "charisma": int(stats.charisma * stat_modifier),
                "psychology": int(stats.psychology * stat_modifier),
                "selling": int(stats.selling * stat_modifier),
            },
            finisher_name=wrestler.finisher_name or "Finisher",
            alignment=wrestler.alignment or "face",
            team=p.team,
        )
        participant_states.append(state)

    if len(participant_states) < 2:
        return MatchResult(narrative_summary="Not enough competitors with stats")

    # Determine card position (may be set by world ticker, fallback to heuristic)
    card_position = getattr(match, "card_position", None) or "midcard"
    if match.is_title_match and card_position == "midcard":
        card_position = "main_event"

    # Simulate
    simulator = MatchSimulator(
        planned_winner_id=match.winner_id,  # Pre-planned winner from booker
        planned_finish=match.finish_type,
        card_position=card_position,
        is_title_match=match.is_title_match,
        stipulation=match.stipulation,
    )
    result = simulator.simulate(participant_states)

    # Apply chemistry bonus from wrestler relationships
    try:
        from core_engine.match_aftermath import get_chemistry_bonus
        if len(participant_states) >= 2 and match.world_id:
            chem_bonus = get_chemistry_bonus(
                db, match.world_id,
                participant_states[0].wrestler_id,
                participant_states[1].wrestler_id,
            )
            if chem_bonus > 0:
                result.match_rating = round(
                    min(5.0, result.match_rating + chem_bonus), 1
                )
    except Exception:
        pass  # Chemistry bonus is optional enhancement

    # Persist results back to DB
    match.winner_id = result.winner_id
    match.finish_type = result.finish_type
    match.finish_description = result.finish_description
    match.match_rating = result.match_rating
    match.crowd_heat = result.crowd_heat
    match.duration_minutes = result.duration_ticks  # 1 tick ≈ 1 minute
    match.is_completed = True
    match.simulation_log = [
        {
            "tick": s.tick, "attacker": s.attacker_id, "defender": s.defender_id,
            "move": s.move_name, "move_type": s.move_type, "damage": s.damage,
            "reversed": s.was_reversed, "is_near_fall": s.is_near_fall,
            "is_finisher": s.is_finisher, "is_finish": s.is_finish,
            "crowd_reaction": s.crowd_reaction,
            "highlight_tier": (3 if s.is_finisher or s.is_finish else
                               2 if s.is_near_fall or s.was_reversed or s.damage >= 10 else 1),
            "description": s.description,
        }
        for s in result.spots
    ]

    # Persist individual match events
    for spot in result.spots:
        db.add(MatchEventDB(
            match_id=match.id,
            tick=spot.tick,
            acting_wrestler_id=spot.attacker_id,
            target_wrestler_id=spot.defender_id,
            event_type=spot.move_type,
            description=spot.description,
            crowd_reaction=spot.crowd_reaction,
            heat_change=spot.heat_change,
            damage=spot.damage,
        ))

    # Update winner's participation record
    for p in participants_db:
        if p.wrestler_id == result.winner_id:
            p.is_winner = True
        p.performance_rating = result.match_rating

    # Wear on wrestlers' condition
    for p_state in participant_states:
        wrestler = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == p_state.wrestler_id
        ).first()
        if wrestler:
            stamina_loss = int((100 - p_state.stamina) * 0.5)
            health_loss = int((100 - p_state.health) * 0.3)
            wrestler.condition = max(0, wrestler.condition - stamina_loss - health_loss)

            # Injury risk check
            if p_state.health < 20:
                injury_prone = 30
                s = db.query(WrestlerStatsDB).filter(
                    WrestlerStatsDB.wrestler_id == wrestler.id
                ).first()
                if s:
                    injury_prone = s.injury_prone
                if random.random() < injury_prone / 200:
                    wrestler.is_injured = True
                    weeks = random.randint(2, 12)
                    from game_service.world_ticker import advance_game_date
                    # Use the match's actual game date for return date calculation
                    match_date = game_date or getattr(match, "game_date", None)
                    if not match_date and match.world_id:
                        from models.game_models import WorldDB
                        world = db.query(WorldDB).filter(WorldDB.id == match.world_id).first()
                        if world:
                            match_date = world.current_game_date
                    if match_date:
                        wrestler.injury_return_date = advance_game_date(
                            match_date, weeks * 7
                        )
                    else:
                        logger.warning("No game_date available for injury return date; skipping return date")
                        wrestler.injury_return_date = None

    return result
