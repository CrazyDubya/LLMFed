"""
Match engine: real wrestling move pool filtered by position, timing, style, opponent.

Wrestlers draw from:
- **Common moves**: strikes, grapples, takedowns — based on position, timing, style
- **Special moves**: signatures — based on momentum, style, opponent
- **Unique moves**: character-specific (from gimmick) — future
- **Finishers**: match-ending — based on momentum, position, style
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

# ---------------------------------------------------------------------------
# Move definition
# ---------------------------------------------------------------------------
@dataclass
class Move:
    """A single wrestling move."""
    id: str
    name: str
    description: str
    move_type: str  # common, special, finisher
    positions: List[str]  # standing, ground, corner, ropes, top_rope, apron
    styles: List[str]  # powerhouse, technical, high_flyer, brawler, submission, any
    momentum_min: int = 0  # min momentum to use (specials/finishers)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.positions, list):
            self.positions = [self.positions]
        if not isinstance(self.styles, list):
            self.styles = [self.styles]


# ---------------------------------------------------------------------------
# Common moves (basic pool)
# ---------------------------------------------------------------------------
COMMON_STRIKES = [
    Move("punch", "Punch", "A quick right hand to the jaw", "common", ["standing", "ground"], ["any"]),
    Move("kick", "Kick", "A stiff kick to the leg or midsection", "common", ["standing", "ground"], ["any"]),
    Move("elbow", "Elbow strike", "Drives elbow into opponent's face", "common", ["standing", "corner"], ["brawler", "any"]),
    Move("forearm", "Forearm smash", "Forearm to the chest or face", "common", ["standing"], ["technical", "brawler", "any"]),
    Move("chop", "Knife-edge chop", "Open-hand chop to the chest", "common", ["standing", "corner"], ["any"]),
    Move("headbutt", "Headbutt", "Drives forehead into opponent", "common", ["standing", "ground"], ["brawler", "any"]),
    Move("knee", "Knee strike", "Knee to the gut or face", "common", ["standing", "corner"], ["high_flyer", "brawler", "any"]),
    Move("backhand", "Backhand slap", "Slap across the face", "common", ["standing"], ["any"]),
]

COMMON_GRAPPLES = [
    Move("headlock", "Headlock", "Wraps head in headlock", "common", ["standing"], ["any"]),
    Move("arm_drag", "Arm drag", "Pulls opponent by arm to mat", "common", ["standing"], ["technical", "high_flyer", "any"]),
    Move("shoulder_tackle", "Shoulder tackle", "Drives shoulder into opponent's gut", "common", ["standing"], ["powerhouse", "brawler", "any"]),
    Move("hip_toss", "Hip toss", "Throws opponent over hip", "common", ["standing"], ["technical", "any"]),
    Move("fireman_carry", "Fireman's carry", "Lifts opponent across shoulders", "common", ["standing"], ["powerhouse", "technical", "any"]),
    Move("snapmare", "Snapmare", "Snaps opponent to mat face-down", "common", ["standing"], ["technical", "any"]),
    Move("armbar_takedown", "Armbar takedown", "Wrenches arm and takes down", "common", ["standing"], ["technical", "submission", "any"]),
    Move("body_slam", "Body slam", "Lifts and slams opponent to mat", "common", ["standing"], ["powerhouse", "brawler", "any"]),
]

COMMON_TAKEDOWNS = [
    Move("single_leg", "Single leg takedown", "Grabs leg and drives opponent down", "common", ["standing"], ["technical", "submission", "any"]),
    Move("double_leg", "Double leg takedown", "Tackles both legs", "common", ["standing"], ["technical", "brawler", "any"]),
    Move("russian_legsweep", "Russian leg sweep", "Sweeps legs from standing", "common", ["standing"], ["technical", "any"]),
    Move("rana_takedown", "Hurricanrana takedown", "Head scissors takedown", "common", ["standing"], ["high_flyer", "technical", "any"]),
]

COMMON_GROUND = [
    Move("stomp", "Stomp", "Stomps on downed opponent", "common", ["ground"], ["brawler", "any"]),
    Move("elbow_drop", "Elbow drop", "Drops elbow onto opponent", "common", ["ground"], ["brawler", "high_flyer", "any"]),
    Move("leg_drop", "Leg drop", "Drops leg across opponent", "common", ["ground"], ["brawler", "any"]),
    Move("running_splash", "Running splash", "Jumps onto downed opponent", "common", ["ground"], ["powerhouse", "high_flyer", "any"]),
    Move("kick_to_legs", "Kick to legs", "Kicks downed opponent's legs", "common", ["ground"], ["technical", "any"]),
]

COMMON_CORNER = [
    Move("irish_whip", "Irish whip", "Whips opponent into corner", "common", ["standing", "corner"], ["any"]),
    Move("corner_clothesline", "Corner clothesline", "Running clothesline in corner", "common", ["corner"], ["brawler", "powerhouse", "any"]),
    Move("bulldog", "Bulldog", "Drops opponent face-first from headlock", "common", ["standing", "corner"], ["brawler", "technical", "any"]),
    Move("ten_punch", "Ten punch", "Repeated punches in corner", "common", ["corner"], ["brawler", "any"]),
]

COMMON_ROPES = [
    Move("clothesline", "Clothesline", "Running clothesline", "common", ["standing", "ropes"], ["brawler", "powerhouse", "any"]),
    Move("dropkick", "Dropkick", "Springboard dropkick", "common", ["standing", "ropes"], ["high_flyer", "technical", "any"]),
    Move("crossbody", "Crossbody", "Running crossbody", "common", ["ropes"], ["high_flyer", "any"]),
    Move("reversal", "Reversal", "Counters opponent's move", "common", ["standing", "ground", "corner", "ropes"], ["technical", "any"]),
]

COMMON_REVERSALS = [
    Move("counter", "Counter", "Counters and gains advantage", "common", ["standing", "ground", "ropes"], ["technical", "any"]),
    Move("noop", "Recover", "Regains footing, catches breath", "common", ["standing", "ground", "corner", "ropes", "top_rope"], ["any"]),
]

# ---------------------------------------------------------------------------
# Special moves (signature-level)
# ---------------------------------------------------------------------------
SPECIAL_MOVES = [
    Move("powerbomb", "Powerbomb", "Lifts and slams opponent hard", "special", ["standing"], ["powerhouse"], momentum_min=25, meta={"impact": "high"}),
    Move("spinebuster", "Spinebuster", "Slams opponent spine-first", "special", ["standing"], ["powerhouse", "brawler"], momentum_min=20, meta={"impact": "high"}),
    Move("german_suplex", "German suplex", "Belly-to-back suplex", "special", ["standing"], ["technical", "powerhouse"], momentum_min=25, meta={"impact": "high"}),
    Move("belly_to_belly", "Belly-to-belly suplex", "Throws opponent overhead", "special", ["standing"], ["technical", "powerhouse"], momentum_min=22, meta={"impact": "high"}),
    Move("ddt", "DDT", "Drops opponent head-first", "special", ["standing"], ["brawler", "technical"], momentum_min=25, meta={"impact": "high"}),
    Move("backbreaker", "Backbreaker", "Snaps back across knee", "special", ["standing"], ["powerhouse", "brawler"], momentum_min=20, meta={"impact": "high"}),
    Move("hurricanrana", "Hurricanrana", "Head scissors roll-through", "special", ["standing", "ropes"], ["high_flyer", "technical"], momentum_min=22, meta={"impact": "medium"}),
    Move("moonsault", "Moonsault", "Backflip splash", "special", ["top_rope", "ropes"], ["high_flyer"], momentum_min=28, meta={"impact": "high"}),
    Move("sleeper", "Sleeper hold", "Chokes opponent from behind", "special", ["standing", "ground"], ["submission", "technical"], momentum_min=25, meta={"submission": True}),
    Move("suplex", "Vertical suplex", "Overhead suplex", "special", ["standing"], ["technical", "powerhouse"], momentum_min=20, meta={"impact": "high"}),
    Move("fallaway_slam", "Fallaway slam", "Throws opponent over shoulder", "special", ["standing"], ["powerhouse"], momentum_min=22, meta={"impact": "high"}),
    Move("flying_clothesline", "Flying clothesline", "Springboard clothesline", "special", ["ropes"], ["high_flyer", "brawler"], momentum_min=20, meta={"impact": "medium"}),
]

# ---------------------------------------------------------------------------
# Finishers (match-ending)
# ---------------------------------------------------------------------------
FINISHER_MOVES = [
    Move("chokeslam", "Chokeslam", "Lifts by throat and slams", "finisher", ["standing"], ["powerhouse"], momentum_min=35, meta={"finisher": True}),
    Move("spear", "Spear", "Running tackle", "finisher", ["standing", "ropes"], ["powerhouse", "brawler"], momentum_min=35, meta={"finisher": True}),
    Move("tombstone", "Tombstone piledriver", "Inverted piledriver", "finisher", ["standing"], ["powerhouse", "brawler"], momentum_min=40, meta={"finisher": True}),
    Move("f5", "F-5", "Spinning facebuster", "finisher", ["standing"], ["powerhouse"], momentum_min=38, meta={"finisher": True}),
    Move("jackhammer", "Jackhammer", "Military press slam", "finisher", ["standing"], ["powerhouse"], momentum_min=40, meta={"finisher": True}),
    Move("pedigree", "Pedigree", "Double underhook facebuster", "finisher", ["standing"], ["brawler", "technical"], momentum_min=38, meta={"finisher": True}),
    Move("stunner", "Stunner", "Jawbreaker from shoulder", "finisher", ["standing"], ["brawler"], momentum_min=35, meta={"finisher": True}),
    Move("rock_bottom", "Rock Bottom", "Slam from fireman's carry", "finisher", ["standing"], ["brawler", "powerhouse"], momentum_min=35, meta={"finisher": True}),
    Move("rko", "RKO", "Jumping cutter", "finisher", ["standing", "ropes"], ["brawler", "high_flyer"], momentum_min=35, meta={"finisher": True}),
    Move("ankle_lock", "Ankle lock", "Single leg submission", "finisher", ["ground", "standing"], ["submission", "technical"], momentum_min=35, meta={"finisher": True, "submission": True}),
    Move("crossface", "Crossface", "Crossface chickenwing", "finisher", ["ground"], ["submission", "technical"], momentum_min=35, meta={"finisher": True, "submission": True}),
    Move("sharpshooter", "Sharpshooter", "Figure-four leglock", "finisher", ["ground"], ["submission", "technical"], momentum_min=38, meta={"finisher": True, "submission": True}),
    Move("walls_of_jericho", "Walls of Jericho", "Boston crab variation", "finisher", ["ground"], ["submission"], momentum_min=38, meta={"finisher": True, "submission": True}),
    Move("swanton", "Swanton bomb", "Front flip splash", "finisher", ["top_rope"], ["high_flyer"], momentum_min=38, meta={"finisher": True}),
    Move("450_splash", "450° splash", "Rotating splash", "finisher", ["top_rope"], ["high_flyer"], momentum_min=40, meta={"finisher": True}),
    Move("frog_splash", "Frog splash", "Frog splash from top", "finisher", ["top_rope"], ["high_flyer", "brawler"], momentum_min=36, meta={"finisher": True}),
]

# ---------------------------------------------------------------------------
# Full move pool
# ---------------------------------------------------------------------------
ALL_MOVES: List[Move] = (
    COMMON_STRIKES + COMMON_GRAPPLES + COMMON_TAKEDOWNS +
    COMMON_GROUND + COMMON_CORNER + COMMON_ROPES + COMMON_REVERSALS +
    SPECIAL_MOVES + FINISHER_MOVES
)
MOVE_BY_ID: Dict[str, Move] = {m.id: m for m in ALL_MOVES}
FINISHER_IDS: set = {m.id for m in FINISHER_MOVES}

# Styles derived from gimmick keywords
STYLE_KEYWORDS = {
    "powerhouse": ["power", "strong", "heavy", "slam", "dominate", "brute", "tank"],
    "technical": ["technical", "grapple", "mat", "chain", "precise", "wrestler"],
    "high_flyer": ["fly", "aerial", "high", "jump", "dive", "agile", "acrobat"],
    "brawler": ["brawler", "street", "fight", "punch", "rough", "hardcore"],
    "submission": ["submission", "hold", "lock", "choke", "tap", "mat"],
}


def _infer_style(gimmick: str) -> str:
    """Infer wrestler style from gimmick description. Default: brawler."""
    g = (gimmick or "").lower()
    for style, keywords in STYLE_KEYWORDS.items():
        if any(kw in g for kw in keywords):
            return style
    return "brawler"


def _cycle_position(tick: int) -> str:
    """Derive position from tick (simple cycle)."""
    cycle = tick % 12
    if cycle < 5:
        return "standing"
    if cycle < 7:
        return "ground"
    if cycle < 9:
        return "corner"
    if cycle < 11:
        return "ropes"
    return "top_rope"


# ---------------------------------------------------------------------------
# MoveEngine
# ---------------------------------------------------------------------------
class MoveEngine:
    """Filters move pool by position, timing, style, opponent, momentum."""

    @staticmethod
    def get_available_moves(
        position: str = "standing",
        tick: int = 1,
        momentum: int = 0,
        style: str = "brawler",
        opponent_style: Optional[str] = None,
        include_finishers: bool = True,
        max_common: int = 12,
        max_special: int = 4,
        max_finisher: int = 3,
    ) -> List[Tuple[str, str]]:
        """Return list of (move_id, description) for context.

        Filters by:
        - position: standing, ground, corner, ropes, top_rope
        - momentum: specials/finishers need momentum_min
        - style: wrestler's style (powerhouse, technical, high_flyer, brawler, submission)
        - opponent_style: optional, for style-based counters
        """
        common: List[Move] = []
        special: List[Move] = []
        finisher: List[Move] = []

        for m in ALL_MOVES:
            if position not in m.positions:
                continue
            if "any" not in m.styles and style not in m.styles:
                continue
            if m.momentum_min > momentum:
                continue
            if m.move_type == "common":
                common.append(m)
            elif m.move_type == "special":
                special.append(m)
            elif m.move_type == "finisher" and include_finishers:
                finisher.append(m)

        # Limit to keep prompt size manageable; prefer variety
        def take(moves: List[Move], n: int) -> List[Tuple[str, str]]:
            if len(moves) <= n:
                return [(m.id, m.description) for m in moves]
            sampled = random.sample(moves, n)
            return [(m.id, m.description) for m in sampled]

        result: List[Tuple[str, str]] = []
        result.extend(take(common, max_common))
        result.extend(take(special, max_special))
        result.extend(take(finisher, max_finisher))
        return result

    @staticmethod
    def is_finisher(move_id: str) -> bool:
        return move_id in FINISHER_IDS

    @staticmethod
    def get_move_meta(move_id: str) -> Dict[str, Any]:
        m = MOVE_BY_ID.get(move_id)
        return (m.meta or {}) if m else {}
