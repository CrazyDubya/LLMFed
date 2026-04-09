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
        ("Military Press Slam", 10, "power"), ("Sidewalk Slam", 7, "power"),
        ("Running Powerslam", 11, "power"), ("Samoan Drop", 8, "power"),
        ("Fallaway Slam", 9, "power"), ("Avalanche Splash", 10, "power"),
        ("Pop-Up Powerbomb", 13, "power"), ("Deadlift Suplex", 10, "power"),
    ],
    "technical": [
        ("Arm Drag", 4, "technical"), ("Suplex Combo", 9, "technical"),
        ("German Suplex", 10, "technical"), ("Snap Mare", 3, "technical"),
        ("Dragon Screw", 7, "technical"), ("Backbreaker", 8, "technical"),
        ("Neckbreaker", 7, "technical"), ("Brainbuster", 11, "technical"),
        ("Northern Lights Suplex", 9, "technical"), ("T-Bone Suplex", 8, "technical"),
        ("Belly-to-Belly Suplex", 8, "technical"), ("Fisherman Suplex", 9, "technical"),
        ("Tiger Suplex", 10, "technical"), ("Rolling Elbow", 7, "technical"),
        ("Cobra Clutch Slam", 9, "technical"), ("Bridging German", 11, "technical"),
    ],
    "aerial": [
        ("Dropkick", 6, "aerial"), ("Moonsault", 11, "aerial"),
        ("Diving Crossbody", 9, "aerial"), ("Hurricanrana", 8, "aerial"),
        ("450 Splash", 12, "aerial"), ("Springboard Elbow", 8, "aerial"),
        ("Frog Splash", 10, "aerial"), ("Shooting Star Press", 13, "aerial"),
        ("Corkscrew Plancha", 10, "aerial"), ("Springboard Cutter", 11, "aerial"),
        ("Tope Con Hilo", 9, "aerial"), ("Phoenix Splash", 14, "aerial"),
        ("Sasuke Special", 10, "aerial"), ("Spanish Fly", 12, "aerial"),
        ("Diving Elbow Drop", 9, "aerial"), ("Asai Moonsault", 11, "aerial"),
    ],
    "brawling": [
        ("Right Hand", 4, "brawling"), ("Uppercut", 5, "brawling"),
        ("Knee Strike", 7, "brawling"), ("Elbow Smash", 6, "brawling"),
        ("Headbutt", 5, "brawling"), ("Lariat", 9, "brawling"),
        ("Running Knee", 10, "brawling"), ("Discus Punch", 8, "brawling"),
        ("Throat Thrust", 5, "brawling"), ("Spinning Backfist", 8, "brawling"),
        ("Knife-Edge Chop", 4, "brawling"), ("Avalanche Corner Splash", 8, "brawling"),
        ("European Uppercut", 6, "brawling"), ("Rebound Lariat", 10, "brawling"),
        ("Enzuigiri", 7, "brawling"), ("Discus Elbow", 9, "brawling"),
    ],
    "submission": [
        ("Armbar", 6, "submission"), ("Figure Four", 8, "submission"),
        ("Sharpshooter", 9, "submission"), ("Crossface", 8, "submission"),
        ("Sleeper Hold", 5, "submission"), ("Ankle Lock", 9, "submission"),
        ("Kimura", 7, "submission"), ("Triangle Choke", 8, "submission"),
        ("Boston Crab", 7, "submission"), ("STF", 8, "submission"),
        ("Koji Clutch", 7, "submission"), ("Dragon Sleeper", 9, "submission"),
        ("Rings of Saturn", 8, "submission"), ("Octopus Hold", 7, "submission"),
        ("Cattle Mutilation", 9, "submission"), ("Rear Naked Choke", 8, "submission"),
    ],
}

# ---------------------------------------------------------------------------
# Signature move pools by archetype — used when populating wrestlers
# ---------------------------------------------------------------------------

SIGNATURE_MOVE_POOLS = {
    "monster_heel": [
        ("Tombstone Piledriver", 14, "power"), ("Running Big Boot", 9, "power"),
        ("Release German Suplex", 10, "power"), ("Torture Rack", 10, "submission"),
        ("Snake Eyes", 7, "brawling"), ("Tree of Woe Stomp", 8, "brawling"),
    ],
    "underdog_face": [
        ("Sling Blade", 8, "technical"), ("Stunner", 12, "brawling"),
        ("Tornado DDT", 10, "aerial"), ("La Magistral Cradle", 7, "technical"),
        ("Diving Headbutt", 9, "aerial"), ("Thesz Press", 7, "brawling"),
    ],
    "cocky_technician": [
        ("Rolling Thunder", 9, "technical"), ("Regal Cutter", 10, "technical"),
        ("Perfect Plex", 10, "technical"), ("Bridging Suplex", 9, "technical"),
        ("Figure Eight", 10, "submission"), ("Standing Moonsault", 9, "aerial"),
    ],
    "silent_assassin": [
        ("Running Knee Strike", 11, "brawling"), ("Kinshasa", 12, "brawling"),
        ("Roundhouse Kick", 10, "brawling"), ("Buzzsaw Kick", 9, "brawling"),
        ("Snap DDT", 8, "technical"), ("Penalty Kick", 10, "brawling"),
    ],
    "cult_leader": [
        ("Sister Abigail", 12, "power"), ("Mandible Claw", 8, "submission"),
        ("Uranage Slam", 10, "power"), ("Running Senton", 9, "power"),
        ("Swinging Neckbreaker", 8, "technical"), ("Eye Rake Combo", 6, "brawling"),
    ],
    "comedy_act": [
        ("People's Elbow", 8, "brawling"), ("Worm", 6, "brawling"),
        ("Bionic Elbow", 7, "brawling"), ("Stink Face", 3, "brawling"),
        ("Atomic Drop", 6, "power"), ("Airplane Spin", 5, "power"),
    ],
    "anti_hero": [
        ("Stunner", 12, "brawling"), ("Pedigree", 13, "power"),
        ("Curb Stomp", 11, "brawling"), ("GTS", 12, "technical"),
        ("Package Piledriver", 13, "power"), ("V-Trigger", 10, "brawling"),
    ],
    "legacy": [
        ("Crossface Chicken Wing", 9, "submission"), ("Slingshot Suplex", 8, "technical"),
        ("Figure Four Leglock", 9, "submission"), ("Spinning Toe Hold", 7, "submission"),
        ("Flying Body Press", 9, "aerial"), ("Bionic Elbow", 7, "brawling"),
    ],
    "patriot": [
        ("Patriot Slam", 11, "power"), ("Patriot Lock", 9, "submission"),
        ("Red White and Blue Thunder Bomb", 12, "power"), ("Flying Shoulder Tackle", 8, "power"),
        ("Angle Slam", 10, "technical"), ("Running Bulldog", 7, "brawling"),
    ],
    "daredevil": [
        ("Swanton Bomb", 12, "aerial"), ("Springboard 450", 14, "aerial"),
        ("Double Rotation Moonsault", 14, "aerial"), ("Corkscrew Shooting Star", 15, "aerial"),
        ("Coast-to-Coast Dropkick", 12, "aerial"), ("Sky Twister Press", 13, "aerial"),
    ],
}

# Archetype-specific finisher pools (name, damage, type)
ARCHETYPE_FINISHERS = {
    "monster_heel": [
        ("The Annihilation", "power"), ("Tomb of Darkness", "power"),
        ("The Extinction", "power"), ("Final Judgment", "power"),
    ],
    "underdog_face": [
        ("Heart of a Champion", "technical"), ("Against All Odds", "aerial"),
        ("The Comeback", "brawling"), ("Never Say Die", "technical"),
    ],
    "cocky_technician": [
        ("The Masterpiece", "technical"), ("Perfection", "submission"),
        ("Technical Knockout", "technical"), ("The Equation", "submission"),
    ],
    "silent_assassin": [
        ("The Kill Shot", "brawling"), ("Silent Night", "brawling"),
        ("Death Sentence", "brawling"), ("Zero Hour", "brawling"),
    ],
    "cult_leader": [
        ("The Sermon", "power"), ("Enlightenment", "submission"),
        ("The Awakening", "power"), ("Mass Hysteria", "power"),
    ],
    "comedy_act": [
        ("The Punchline", "brawling"), ("The Gag Reflex", "brawling"),
        ("Comedy of Errors", "brawling"), ("Lights Out Comedy", "power"),
    ],
    "anti_hero": [
        ("The Reckoning", "brawling"), ("One Final Beat", "power"),
        ("Bitter End", "power"), ("Anti-Establishment", "brawling"),
    ],
    "legacy": [
        ("The Dynasty", "technical"), ("Legacy Lock", "submission"),
        ("Generational Shift", "technical"), ("The Inheritance", "power"),
    ],
    "patriot": [
        ("The Patriot Act", "power"), ("Eagle's Landing", "aerial"),
        ("Freedom Strike", "brawling"), ("National Anthem", "submission"),
    ],
    "daredevil": [
        ("Terminal Velocity", "aerial"), ("The Death-Defier", "aerial"),
        ("Point of No Return", "aerial"), ("Leap of Faith", "aerial"),
    ],
}

# ---------------------------------------------------------------------------
# Match-type-specific spot pools
# ---------------------------------------------------------------------------

CAGE_SPOTS = [
    ("throws opponent into the cage wall", 8, "brawling"),
    ("grinds opponent's face against the steel", 6, "brawling"),
    ("catapults opponent into the cage", 9, "power"),
    ("climbs the cage and drops an elbow", 12, "aerial"),
    ("slams opponent off the cage wall", 10, "power"),
    ("attempts to escape over the top of the cage", 0, "escape"),
]

LADDER_SPOTS = [
    ("drives opponent through a ladder", 12, "power"),
    ("suplexes opponent onto a ladder", 11, "technical"),
    ("pushes opponent off the ladder", 13, "aerial"),
    ("sunset flip powerbomb off the ladder", 15, "power"),
    ("climbs the ladder and reaches for the prize", 0, "climb"),
    ("tips the ladder over with opponent on it", 14, "power"),
]

TABLE_SPOTS = [
    ("sets up a table at ringside", 0, "setup"),
    ("powerbombs opponent through the table", 16, "power"),
    ("superplexes opponent through a table", 18, "power"),
    ("spears opponent through a table", 15, "brawling"),
    ("elbow drops opponent through a table from the top", 17, "aerial"),
]

HELL_IN_A_CELL_SPOTS = [
    ("throws opponent into the cell wall", 9, "brawling"),
    ("slams opponent onto the steel steps", 10, "power"),
    ("climbs the outside of the cell", 0, "climb"),
    ("chokeslams opponent off the cell roof", 20, "power"),
    ("drives opponent through the announce table", 14, "brawling"),
    ("uses the cell door as a weapon", 8, "brawling"),
]

IRON_MAN_FALL_DESCRIPTIONS = [
    "scores a fall with a pinfall!", "scores a fall via submission!",
    "scores a fall after a devastating finisher!",
]

# ---------------------------------------------------------------------------
# Charisma style match spots
# ---------------------------------------------------------------------------

TAUNT_SPOTS = {
    "cocky": [
        "{name} flexes over their fallen opponent!", "{name} mocks the crowd with a strut!",
        "{name} slaps the taste out of {opponent}'s mouth and laughs!",
    ],
    "intense": [
        "{name} lets out a primal scream!", "{name} no-sells the last move and hulks up!",
        "{name} stares daggers through {opponent} — pure intensity!",
    ],
    "funny": [
        "{name} does a little dance for the crowd!", "{name} pretends to answer a phone call mid-match!",
        "{name} offers a handshake — then pulls it away! Classic!",
    ],
    "mysterious": [
        "{name} sits up like something out of a horror movie!",
        "{name} points to the sky ominously...", "{name} tilts their head — unsettling...",
    ],
    "humble": [
        "{name} fires up the crowd! They're feeding off the energy!",
        "{name} slaps the mat — they're not done yet!",
        "{name} bows to the crowd before delivering the next blow!",
    ],
}

# ---------------------------------------------------------------------------
# Venue atmosphere modifiers
# ---------------------------------------------------------------------------

VENUE_ATMOSPHERE = {
    "club": {"capacity_range": (200, 1500), "rating_mod": -0.2, "crowd_energy": 0.8,
             "description": "intimate venue"},
    "arena": {"capacity_range": (2000, 10000), "rating_mod": 0.0, "crowd_energy": 1.0,
              "description": "electric arena"},
    "large_arena": {"capacity_range": (10001, 25000), "rating_mod": 0.1, "crowd_energy": 1.1,
                    "description": "massive arena"},
    "stadium": {"capacity_range": (25001, 80000), "rating_mod": 0.2, "crowd_energy": 1.2,
                "description": "roaring stadium"},
}

def get_venue_tier(capacity: int) -> str:
    """Determine venue tier from capacity."""
    if capacity <= 1500:
        return "club"
    elif capacity <= 10000:
        return "arena"
    elif capacity <= 25000:
        return "large_arena"
    return "stadium"

CROWD_REACTIONS = [
    "The crowd erupts!", "Huge pop from the fans!", "The audience is on their feet!",
    "Mixed reaction from the crowd.", "The fans are booing loudly!",
    "Chants break out across the arena!", "Stunned silence from the crowd.",
    "The energy in the building is electric!", "The crowd is split down the middle!",
    "THIS IS AWESOME chants ring out!", "FIGHT FOREVER! FIGHT FOREVER!",
    "The crowd is going absolutely ballistic!", "You can barely hear yourself think!",
    "Dueling chants fill the arena!", "The fans throw streamers into the ring!",
    "A hush falls over the crowd...", "The building is shaking!",
    "Standing ovation from the crowd!", "The fans are in disbelief!",
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

INTERFERENCE_SUCCESS = [
    "{mgr} distracts the referee while {attacker} uses a low blow on {defender}!",
    "{mgr} slides a chair into the ring — {attacker} uses it behind the ref's back!",
    "{mgr} grabs {defender}'s ankle from outside! {attacker} capitalizes!",
    "{mgr} throws powder in {defender}'s eyes while the ref argues with the crowd!",
    "{mgr} pulls down the top rope — {defender} tumbles to the outside!",
]

INTERFERENCE_CAUGHT = [
    "The referee catches {mgr} red-handed! The official ejects {mgr} from ringside!",
    "{mgr} tries to interfere but the referee sees it — DISQUALIFICATION!",
    "{defender} catches {mgr} trying to cheat — and decks {mgr} on the apron!",
]

INTERFERENCE_FAIL = [
    "{mgr} tries to distract the referee but gets caught — warning issued!",
    "{mgr} attempts to pass a weapon but {defender} sees it coming!",
    "The referee is wise to {mgr}'s tricks tonight!",
]

POST_MATCH_ATTACK = [
    "{attackers} storm the ring and lay out {victim} with a vicious beatdown!",
    "After the match, {attackers} blindside {victim} from behind!",
    "The bell has rung but {attackers} aren't done — {victim} takes a post-match assault!",
]

POST_MATCH_SAVE = [
    "{savers} charge to the ring and clear out the attackers!",
    "Here comes {savers} to make the save! The crowd goes wild!",
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
    ("Doomsday Device", 17), ("Magic Killer", 15),
    ("3D (Dudley Death Drop)", 16), ("Poetry in Motion", 13),
    ("Total Elimination", 15), ("Shatter Machine", 16),
    ("Hart Attack", 14), ("Rocket Launcher", 13),
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

            if not attacker.finisher_available and attacker.momentum > 75:
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

            if not attacker.finisher_available and attacker.momentum > 75:
                attacker.finisher_available = True

            # Elimination check: participants with very low endurance can be pinned
            if len(active) > 2 and self.tick > target_length * 0.3:
                for p in list(active):
                    if p is attacker:
                        continue
                    if p.endurance < 15 and random.random() < 0.35:
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
            if self.tick > target_length * 0.5 and random.random() < 0.2:
                near_fall = self._near_fall(attacker, defender)
                if near_fall:
                    self.spots.append(near_fall)

            # When down to 2, try for a finish
            if len(active) == 2 and self.tick >= target_length - 3:
                finish_spot = self._attempt_finish(attacker, defender)
                if finish_spot:
                    self.spots.append(finish_spot)
                    return self._build_result(finish_spot, attacker, defender, participants)

            if self._should_switch_control(attacker, defender):
                pass  # In multi-person, control is already random each tick

        # Time limit: pick the participant with the highest momentum as winner
        if len(active) >= 2:
            winner = max(active, key=lambda p: p.momentum)
            loser = [p for p in active if p is not winner][0]
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
            finish_description="Last person standing wins!",
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
        # --- Charisma style taunt (15% chance when momentum is high) ---
        if attacker.momentum > 60 and random.random() < 0.15:
            style = attacker.charisma_style or "humble"
            if style in TAUNT_SPOTS:
                taunt = random.choice(TAUNT_SPOTS[style]).format(
                    name=attacker.name, opponent=defender.name)
                momentum_gain = 5
                if style == "intense":
                    momentum_gain = 10  # No-sell / hulk-up gets huge crowd pop
                elif style == "cocky":
                    momentum_gain = 3  # Risk: cocky taunts can backfire
                    if random.random() < 0.25:
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
        if self.stipulation and random.random() < 0.25:
            stip_spot = self._generate_stipulation_spot(attacker, defender)
            if stip_spot:
                return stip_spot

        # --- Signature move (20% chance when momentum > 55, once per match per sig) ---
        if (attacker.signature_moves and attacker.momentum > 55
                and random.random() < 0.20):
            sig = random.choice(attacker.signature_moves)
            sig_name, sig_damage, sig_type = sig[0], sig[1], sig[2]
            attack_stat = attacker.stats.get(sig_type, 50)
            damage = int(sig_damage * (attack_stat / 50) * (attacker.stamina / 100))
            damage = max(3, damage)
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
        attack_stat = attacker.stats.get(category, 50)
        defense_stat = defender.stats.get("toughness", 50)
        stamina_factor = attacker.stamina / 100
        damage = int(base_damage * (attack_stat / 50) * stamina_factor * (1 - defense_stat / 200))
        damage = max(1, damage)

        # Hometown advantage: small damage boost
        if attacker.hometown_bonus:
            damage = int(damage * 1.1)

        # Check for reversal
        was_reversed = False
        reversal_move = None
        reversal_chance = (
            defender.stats.get("technical", 50)
            + defender.stats.get("psychology", 50)
            + defender.stats.get("speed", 50) * 0.5
        ) / 500
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

    def _generate_stipulation_spot(self, attacker: MatchParticipantState,
                                   defender: MatchParticipantState) -> Optional[MatchSpot]:
        """Generate a match-type-specific special spot."""
        stip = (self.stipulation or "").lower()

        if "cage" in stip or "steel cage" in stip:
            desc, base_dmg, stype = random.choice(CAGE_SPOTS)
            if stype == "escape":
                # Cage escape attempt — only works if momentum > 80
                if attacker.momentum > 80 and attacker.health > 40:
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
            damage = int(base_dmg * (attacker.stats.get("brawling", 50) / 50))
            return MatchSpot(
                tick=self.tick, attacker_id=attacker.wrestler_id,
                defender_id=defender.wrestler_id,
                move_name="Cage Spot", move_type="brawling",
                damage=max(3, damage),
                description=f"{attacker.name} {desc}!",
                crowd_reaction=random.choice(CROWD_REACTIONS),
                heat_change=random.randint(2, 5),
            )

        elif "ladder" in stip:
            desc, base_dmg, stype = random.choice(LADDER_SPOTS)
            if stype == "climb":
                if attacker.momentum > 70:
                    return MatchSpot(
                        tick=self.tick, attacker_id=attacker.wrestler_id,
                        defender_id=defender.wrestler_id,
                        move_name="Ladder Climb", move_type="aerial",
                        damage=0,
                        description=f"{attacker.name} is climbing the ladder! Fingers inches from the prize!",
                        crowd_reaction="This could be it!",
                        heat_change=6,
                    )
                return None
            damage = int(base_dmg * (attacker.stats.get("power", 50) / 50))
            return MatchSpot(
                tick=self.tick, attacker_id=attacker.wrestler_id,
                defender_id=defender.wrestler_id,
                move_name="Ladder Spot", move_type=stype,
                damage=max(5, damage),
                description=f"{attacker.name} {desc}!",
                crowd_reaction="OH MY GOD!",
                heat_change=random.randint(3, 7),
            )

        elif "table" in stip:
            desc, base_dmg, stype = random.choice(TABLE_SPOTS)
            if stype == "setup":
                return MatchSpot(
                    tick=self.tick, attacker_id=attacker.wrestler_id,
                    defender_id=defender.wrestler_id,
                    move_name="Table Setup", move_type="power",
                    damage=0,
                    description=f"{attacker.name} {desc}!",
                    crowd_reaction="The crowd knows what's coming!",
                    heat_change=3,
                )
            damage = int(base_dmg * (attacker.stats.get("power", 50) / 50))
            return MatchSpot(
                tick=self.tick, attacker_id=attacker.wrestler_id,
                defender_id=defender.wrestler_id,
                move_name="Table Spot", move_type=stype,
                damage=max(8, damage), is_finish=False,
                description=f"{attacker.name} {desc}!",
                crowd_reaction="THROUGH THE TABLE!",
                heat_change=random.randint(5, 8),
            )

        elif "hell" in stip or "cell" in stip:
            desc, base_dmg, stype = random.choice(HELL_IN_A_CELL_SPOTS)
            if stype == "climb":
                return MatchSpot(
                    tick=self.tick, attacker_id=attacker.wrestler_id,
                    defender_id=defender.wrestler_id,
                    move_name="Cell Climb", move_type="aerial",
                    damage=0,
                    description=f"{attacker.name} {desc}! This is getting dangerous!",
                    crowd_reaction="Don't do it! DON'T DO IT!",
                    heat_change=7,
                )
            damage = int(base_dmg * (attacker.stats.get("brawling", 50) / 50))
            return MatchSpot(
                tick=self.tick, attacker_id=attacker.wrestler_id,
                defender_id=defender.wrestler_id,
                move_name="Cell Spot", move_type=stype,
                damage=max(5, damage),
                description=f"{attacker.name} {desc}!",
                crowd_reaction="GOOD GOD ALMIGHTY!",
                heat_change=random.randint(4, 8),
            )

        return None

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

        # Endurance drain (tracks cumulative damage for multi-person eliminations)
        if not spot.was_reversed:
            defender.endurance = max(0, defender.endurance - spot.damage * 0.8)
        else:
            attacker.endurance = max(0, attacker.endurance - spot.damage * 0.8)

    def _should_switch_control(self, attacker: MatchParticipantState,
                               defender: MatchParticipantState) -> bool:
        """Determine if offensive control should switch."""
        # Psychology stat helps maintain control
        hold_chance = attacker.stats.get("psychology", 50) / 100
        comeback_chance = defender.stats.get("stamina", 50) / 200
        comeback_chance += defender.stats.get("speed", 50) / 400  # Fast wrestlers escape faster

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
            chance = min(0.35, chance)  # Max 35% per opportunity

            if random.random() > chance:
                continue

            self._interference_happened = True

            # Did they get caught?
            caught = random.random() < 0.20  # 20% catch rate
            if caught:
                # DQ finish — defender wins by disqualification
                if random.random() < 0.5:
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
                defender.health -= 12
                defender.momentum = max(0, defender.momentum - 15)
                attacker.momentum = min(100, attacker.momentum + 10)
                return MatchSpot(
                    tick=self.tick, attacker_id=attacker.wrestler_id,
                    defender_id=defender.wrestler_id,
                    move_name="Manager Interference",
                    move_type="interference", damage=12,
                    crowd_reaction="The crowd boos the cheating!",
                    heat_change=-3 if attacker.alignment == "heel" else 2,
                    description=desc,
                )

        return None

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

        # Rivalry heat bonus — hot feuds produce better matches
        rivalry_bonus = min(0.5, self.rivalry_heat / 200.0)

        # Interference penalty — cheating cheapens ratings slightly
        interference_penalty = -0.2 if self._interference_happened else 0

        # Signature move bonus — fans love seeing signature spots
        sig_spots = sum(1 for s in self.spots if "Signature" in s.description or "signature" in s.description)
        sig_bonus = min(sig_spots * 0.1, 0.3)

        # Stipulation bonus — gimmick matches get a bump for spectacle
        stip_bonus = 0.0
        stip = (self.stipulation or "").lower()
        if "cage" in stip or "cell" in stip:
            stip_bonus = 0.2
        elif "ladder" in stip or "table" in stip:
            stip_bonus = 0.25
        elif stip and stip not in ("", "standard"):
            stip_bonus = 0.1

        # Venue atmosphere bonus (set by caller via show_momentum scaling)
        venue_tier = get_venue_tier(self.show_momentum * 100)  # approximate
        venue_mod = VENUE_ATMOSPHERE.get(venue_tier, {}).get("rating_mod", 0)

        rating = ((base_quality * 2.5) + variety_bonus + near_fall_bonus +
                  reversal_bonus + length_bonus + title_bonus + rivalry_bonus +
                  interference_penalty + sig_bonus + stip_bonus + venue_mod)
        rating = min(5.0, max(0.5, rating + random.uniform(-0.3, 0.3)))
        return round(rating, 1)

    def _calculate_heat(self) -> int:
        """Calculate final crowd heat level."""
        # Start from show momentum (crowd energy carried from prior segments)
        base = self.show_momentum
        # Rivalry heat gives a crowd bonus — fans care about these two
        base += int(self.rivalry_heat * 0.15)
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

        return MatchResult(
            winner_id=finish_spot.attacker_id,
            finish_type=finish_spot.finish_type or "pinfall",
            finish_description=finish_spot.description,
            match_rating=self._calculate_rating(participants),
            crowd_heat=self._calculate_heat(),
            duration_ticks=self.tick,
            spots=self.spots,
            narrative_summary=narrative,
            interference_occurred=self._interference_happened,
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

        # Ring rust modifier (Group 1)
        ring_rust = getattr(wrestler, "ring_rust_days", 0) or 0
        if ring_rust > 14:
            stat_modifier *= max(0.85, 1.0 - (ring_rust / 500))

        # Conditioning modifier (Group 6)
        conditioning = getattr(stats, "conditioning_level", 70) or 70
        cond_modifier = 0.85 + (conditioning / 100) * 0.15  # 0.85-1.0
        stat_modifier *= cond_modifier

        # Load signature moves
        sig_moves = []
        if wrestler.signature_moves:
            for sig in wrestler.signature_moves:
                if isinstance(sig, (list, tuple)) and len(sig) >= 3:
                    sig_moves.append(tuple(sig))

        # Load charisma style
        personality = wrestler.personality_traits or {}
        charisma_style = personality.get("charisma_style", "humble") if isinstance(personality, dict) else "humble"

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
            signature_moves=sig_moves,
            charisma_style=charisma_style,
        )
        participant_states.append(state)

    if len(participant_states) < 2:
        return MatchResult(narrative_summary="Not enough competitors with stats")

    # Determine card position (may be set by world ticker, fallback to heuristic)
    card_position = getattr(match, "card_position", None) or "midcard"
    if match.is_title_match and card_position == "midcard":
        card_position = "main_event"

    # Load manager context for wrestlers at ringside
    managers = []
    try:
        from models.game_models import ManagerClientDB, ManagerDB
        for p_state in participant_states:
            bond = db.query(ManagerClientDB).filter_by(
                client_wrestler_id=p_state.wrestler_id, is_active=True
            ).first()
            if bond:
                mgr = db.query(ManagerDB).filter_by(id=bond.manager_id).first()
                if mgr:
                    managers.append(ManagerContext(
                        manager_id=mgr.id,
                        manager_name=mgr.name,
                        client_wrestler_id=p_state.wrestler_id,
                        interference_skill=mgr.interference_skill or 50,
                        cunning=mgr.cunning or 50,
                        specialization=bond.specialization or "all_around",
                    ))
    except Exception:
        pass  # Manager integration is optional

    # Calculate rivalry heat between participants
    rivalry_heat = 0
    try:
        from models.game_models import WrestlerRelationshipDB
        if len(participant_states) >= 2 and match.world_id:
            rel = db.query(WrestlerRelationshipDB).filter(
                WrestlerRelationshipDB.world_id == match.world_id,
                WrestlerRelationshipDB.wrestler1_id.in_(
                    [participant_states[0].wrestler_id, participant_states[1].wrestler_id]
                ),
                WrestlerRelationshipDB.wrestler2_id.in_(
                    [participant_states[0].wrestler_id, participant_states[1].wrestler_id]
                ),
            ).first()
            if rel:
                rivalry_heat = rel.rivalry_heat or 0
    except Exception:
        pass  # Rivalry heat is optional

    # Show momentum passed via match attribute (set by world_ticker)
    show_momentum = getattr(match, "_show_momentum", 50)

    # Simulate
    simulator = MatchSimulator(
        planned_winner_id=match.winner_id,  # Pre-planned winner from booker
        planned_finish=match.finish_type,
        card_position=card_position,
        is_title_match=match.is_title_match,
        stipulation=match.stipulation,
        managers=managers,
        rivalry_heat=rivalry_heat,
        show_momentum=show_momentum,
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

    # Generate post-match angle (faction run-ins, beatdowns)
    result.post_match_angle = _generate_post_match_angle(
        db, match, result, participant_states
    )

    return result


def _generate_post_match_angle(
    db: Session, match: MatchDB, result: MatchResult,
    participants: List[MatchParticipantState],
) -> Optional[Dict[str, Any]]:
    """Check if a post-match angle occurs — faction attacks, saves, etc."""
    if not result.winner_id or not match.world_id:
        return None

    try:
        from models.game_models import StableMemberDB, StableDB, GameWrestlerDB

        loser_id = None
        for p in participants:
            if p.wrestler_id != result.winner_id:
                loser_id = p.wrestler_id
                break
        if not loser_id:
            return None

        # Check if winner is in a heel stable — faction beatdown chance
        winner_member = db.query(StableMemberDB).filter_by(
            wrestler_id=result.winner_id, is_active=True
        ).first()
        if winner_member:
            stable = db.query(StableDB).filter_by(
                id=winner_member.stable_id, is_active=True
            ).first()
            if stable and stable.alignment == "heel" and random.random() < 0.25:
                # Faction beatdown on the loser
                stablemates = db.query(StableMemberDB).filter_by(
                    stable_id=stable.id, is_active=True
                ).all()
                attacker_ids = [m.wrestler_id for m in stablemates if m.wrestler_id != result.winner_id]
                if attacker_ids:
                    attackers = db.query(GameWrestlerDB).filter(
                        GameWrestlerDB.id.in_(attacker_ids[:2])
                    ).all()
                    attacker_names = " & ".join(a.name for a in attackers)
                    victim = db.query(GameWrestlerDB).filter_by(id=loser_id).first()
                    desc = random.choice(POST_MATCH_ATTACK).format(
                        attackers=f"{stable.name} ({attacker_names})",
                        victim=victim.name if victim else "the loser"
                    )
                    return {
                        "type": "faction_beatdown",
                        "stable_id": stable.id,
                        "stable_name": stable.name,
                        "victim_id": loser_id,
                        "attacker_ids": attacker_ids[:2],
                        "description": desc,
                    }

        # Check if loser is in a face stable — save chance
        loser_member = db.query(StableMemberDB).filter_by(
            wrestler_id=loser_id, is_active=True
        ).first()
        if loser_member:
            stable = db.query(StableDB).filter_by(
                id=loser_member.stable_id, is_active=True
            ).first()
            if stable and stable.alignment == "face" and random.random() < 0.15:
                stablemates = db.query(StableMemberDB).filter_by(
                    stable_id=stable.id, is_active=True
                ).all()
                saver_ids = [m.wrestler_id for m in stablemates if m.wrestler_id != loser_id]
                if saver_ids:
                    savers = db.query(GameWrestlerDB).filter(
                        GameWrestlerDB.id.in_(saver_ids[:2])
                    ).all()
                    saver_names = " & ".join(s.name for s in savers)
                    desc = random.choice(POST_MATCH_SAVE).format(
                        savers=f"{stable.name} ({saver_names})"
                    )
                    return {
                        "type": "faction_save",
                        "stable_id": stable.id,
                        "stable_name": stable.name,
                        "saved_id": loser_id,
                        "saver_ids": saver_ids[:2],
                        "description": desc,
                    }
    except Exception as e:
        logger.warning("Post-match angle generation failed: %s", e)

    return None
