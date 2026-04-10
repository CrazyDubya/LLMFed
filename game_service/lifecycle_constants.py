"""
Constants and data tables for wrestler lifecycle processing.

Extracted from wrestler_lifecycle_service.py to keep logic and data separate.
"""

# ---------------------------------------------------------------------------
# Group 1: Aging, Physical Decline & Career Arc
# ---------------------------------------------------------------------------

# Career phase thresholds (relative to peak_age)
CAREER_PHASE_ROOKIE_MAX_EXP = 2
CAREER_PHASE_RISING_OFFSET = -2   # age < peak + offset => rising
CAREER_PHASE_PRIME_OFFSET = 4     # age < peak + offset => prime
CAREER_PHASE_VETERAN_OFFSET = 8   # age < peak + offset => veteran

# Stat decay caps
MAX_DECLINE_PER_YEAR = 5
MIN_STAT_FLOOR = 5
MAX_STAT_CAP = 100

# Stats that decay first (speed-based)
EARLY_DECLINE_STATS = ("speed", "aerial", "stamina")

# Stats that decay later (after 3 years past peak)
LATE_DECLINE_STATS = ("power", "toughness")
LATE_DECLINE_YEARS_THRESHOLD = 3

# Mental stats that improve with age
IMPROVING_STATS = ("psychology", "selling")
IMPROVING_STAT_MAX_GAIN = 2

# Retirement pressure values
RETIREMENT_PRESSURE = {
    "declining_phase": 10,
    "veteran_phase": 3,
    "low_morale_threshold": 30,
    "low_morale_bonus": 15,
    "injured_age_threshold": 35,
    "injured_bonus": 20,
    "low_pop_threshold": 20,
    "low_pop_age_threshold": 36,
    "low_pop_bonus": 10,
    "old_age_threshold": 42,
    "old_age_bonus": 15,
}

# Ring rust formula
RING_RUST_NO_PENALTY_DAYS = 14
RING_RUST_DIVISOR = 500
RING_RUST_MIN_MODIFIER = 0.85

# ---------------------------------------------------------------------------
# Group 2: Career Goals
# ---------------------------------------------------------------------------

# Morale/satisfaction adjustments on goal completion
GOAL_COMPLETE_MORALE_BONUS = 10
GOAL_COMPLETE_SATISFACTION_BONUS = 15

# Goal frustration
GOAL_FRUSTRATION_PER_WEEK = 1
GOAL_FRUSTRATION_MORALE_THRESHOLD = 80
GOAL_FRUSTRATION_MORALE_PENALTY = 3
GOAL_FRUSTRATION_ALIGNMENT_THRESHOLD = 90
GOAL_FRUSTRATION_ALIGNMENT_SHIFT = -5

# Glass ceiling: weeks stuck before frustration accelerates
GLASS_CEILING_WEEKS = 26
GLASS_CEILING_FRUSTRATION_BONUS = 3

# Goal types that are title-related (for glass ceiling detection)
TITLE_GOAL_TYPES = frozenset({
    "win_title", "become_champion", "win_first_title",
    "main_event_ppv", "one_more_title_run",
})

# Satisfaction thresholds
LOW_SATISFACTION_THRESHOLD = 30
LOW_SATISFACTION_MORALE_PENALTY = 2
HIGH_SATISFACTION_THRESHOLD = 70
HIGH_SATISFACTION_MORALE_BONUS = 1

# Goal completion: attribute-based thresholds
GOAL_PROVE_MYSELF_POP = 50
GOAL_LEGACY_THRESHOLD = 50
GOAL_TOP_DRAW_RATING = 80
GOAL_EARN_RESPECT_POP = 60
GOAL_EARN_RESPECT_MORALE = 60
GOAL_HEADLINE_POP = 75

# ---------------------------------------------------------------------------
# Group 3: Backstage Politics & Locker Room
# ---------------------------------------------------------------------------

# Creative influence calculation
TENURE_MULTIPLIER = 2
TENURE_CAP = 20
POPULARITY_DIVISOR = 5

# Locker room standing thresholds
LEADER_POLITICS = 80
LEADER_POP = 70
RESPECTED_POLITICS = 60
RESPECTED_WORK_ETHIC = 60
DISLIKED_POLITICS = 30
DISLIKED_WORK_ETHIC = 40
TOXIC_POLITICS = 70
TOXIC_WORK_ETHIC = 30

# Morale contagion
LEADER_MORALE_BASELINE = 50
LEADER_MORALE_DIVISOR = 20  # shift = (avg_leader_morale - 50) / 20

# Creative control
CREATIVE_CONTROL_THRESHOLD = 75
CREATIVE_CONTROL_FINISHES = ("pinfall", "submission")
CREATIVE_CONTROL_ALTERNATIVES = ("count_out", "disqualification")
CREATIVE_CONTROL_DIVISOR = 200

# ---------------------------------------------------------------------------
# Group 4: Developmental Pipeline
# ---------------------------------------------------------------------------

# Mentor qualification
MENTOR_MIN_PSYCHOLOGY = 50
MENTOR_BONUS_DIVISOR = 200

# Debut readiness
DEBUT_MIN_WEEKS = 8
DEBUT_MIN_AVG_RING = 45
DEBUT_MIN_PSYCHOLOGY = 35
DEBUT_RING_STATS = ("power", "technical", "aerial", "brawling")

# Training with mentor
MENTOR_SPECIALTY_MULTIPLIER = 2
MENTOR_PSYCHOLOGY_BONUS = 1
MENTOR_SELF_IMPROVE_CHANCE = 0.1

# ---------------------------------------------------------------------------
# Group 5: Legacy, Hall of Fame & Nostalgia
# ---------------------------------------------------------------------------

# Legacy score formula weights
LEGACY_HIGHLIGHT_WEIGHT = 5
LEGACY_REIGN_WEIGHT = 10
LEGACY_RATING_WEIGHT = 8
LEGACY_YEARS_WEIGHT = 2

# Match highlight thresholds
HIGHLIGHT_STAR_THRESHOLD = 4.5
HIGHLIGHT_MAX_SIGNIFICANCE = 10
HIGHLIGHT_SIGNIFICANCE_MULTIPLIER = 2

# Hall of Fame
HOF_MIN_LEGACY = 50

# Nostalgia pop
NOSTALGIA_MIN_DAYS_ABSENT = 90
NOSTALGIA_MIN_LEGACY = 30
NOSTALGIA_MAX_BONUS = 30
NOSTALGIA_DAYS_PER_UNIT = 30
NOSTALGIA_PER_UNIT = 5

# ---------------------------------------------------------------------------
# Group 6: Physical Identity, Specialization & Conditioning
# ---------------------------------------------------------------------------

# Body type weight thresholds (kg)
BODY_TYPE_THRESHOLDS = [
    (85, "cruiserweight"),
    (110, "average"),
    (140, "big_man"),
]
BODY_TYPE_DEFAULT = "super_heavyweight"

# Physical attribute generation ranges
HEIGHT_RANGE = (165, 205)
WEIGHT_OFFSET_RANGE = (-10, 20)
WEIGHT_MIN = 70
WEIGHT_MAX = 160
HEIGHT_WEIGHT_FACTOR = 0.5

# Body modifier weight difference thresholds
BODY_MOD_HEAVY_DIFF = 30
BODY_MOD_HEAVY = {"power": 1.15, "speed": 1.0, "aerial": 0.85}
BODY_MOD_LIGHT = {"power": 0.85, "speed": 1.15, "aerial": 1.10}
BODY_MOD_NEUTRAL = {"power": 1.0, "speed": 1.0, "aerial": 1.0}

# Stipulation-to-specialist-attribute mapping (shared by bonus calc and growth)
STIPULATION_SPECIALIST_MAP = {
    "cage": "cage_specialist",
    "hell_in_a_cell": "cage_specialist",
    "ladder": "ladder_specialist",
    "tables": "hardcore_specialist",
    "no_dq": "hardcore_specialist",
    "falls_count_anywhere": "hardcore_specialist",
    "extreme_rules": "hardcore_specialist",
    "street_fight": "hardcore_specialist",
}

# Stipulation bonus formula
STIPULATION_BONUS_DIVISOR = 200

# Specialization growth per stipulation match
SPECIALIZATION_GROWTH = 2

# Conditioning adjustment values
CONDITIONING_DEFAULT = 70
CONDITIONING_OVERWORK_THRESHOLD = 3   # matches per week
CONDITIONING_OVERWORK_PENALTY = 5
CONDITIONING_REST_GAIN = 3
CONDITIONING_WORK_GAIN = 1
CONDITIONING_MIN = 20
