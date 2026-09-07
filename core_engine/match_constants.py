"""
Match Simulation Constants

Named constants extracted from match_engine.py to replace magic numbers.
Grouped by domain: momentum, probability, damage, rating, tag match, and finish.
"""

# ---------------------------------------------------------------------------
# Momentum thresholds
# ---------------------------------------------------------------------------

TAUNT_MOMENTUM_THRESHOLD = 60  # Minimum momentum to attempt a taunt
SIGNATURE_MOMENTUM_THRESHOLD = 55  # Minimum momentum to use a signature move
FINISHER_MOMENTUM_THRESHOLD = 75  # Momentum at which finisher becomes available
FINISH_MOMENTUM_BONUS_THRESHOLD = 80  # Extra finish chance when momentum exceeds this
CAGE_ESCAPE_MOMENTUM_THRESHOLD = 80  # Momentum needed to attempt cage escape
LADDER_CLIMB_MOMENTUM_THRESHOLD = 70  # Momentum needed to attempt ladder climb

# ---------------------------------------------------------------------------
# Probability constants
# ---------------------------------------------------------------------------

TAUNT_CHANCE = 0.15  # Chance of a taunt when momentum is high
COCKY_BACKFIRE_CHANCE = 0.25  # Chance a cocky taunt backfires
SIGNATURE_CHANCE = 0.20  # Chance of using a signature move
STIPULATION_SPOT_CHANCE = 0.25  # Chance of a stipulation-specific spot

BOTCH_DIFFICULTY_FACTOR = 0.04  # Multiplier for move difficulty on botch chance
BOTCH_AERIAL_BONUS = 0.15  # Extra botch chance for aerial moves
BOTCH_MAX_CHANCE = 0.12  # Maximum botch chance (cap)
BOTCH_MINOR_THRESHOLD = 0.6  # Below this severity roll = minor botch
BOTCH_BAD_THRESHOLD = 0.9  # Below this severity roll = bad botch (above = dangerous)

REVERSAL_BASE_CHANCE_DIVISOR = 500  # Divisor for computing reversal chance from stats
REVERSAL_DAMAGE_MULTIPLIER = 0.7  # Reversals do this fraction of normal damage

INTERFERENCE_CATCH_CHANCE = 0.20  # Chance referee catches interference
INTERFERENCE_DQ_CHANCE = 0.50  # Chance caught interference leads to DQ (vs warning)
INTERFERENCE_MAX_CHANCE = 0.35  # Maximum interference chance per opportunity
INTERFERENCE_DAMAGE = 12  # Damage dealt by successful interference
INTERFERENCE_MOMENTUM_LOSS = 15  # Momentum lost by interference victim
INTERFERENCE_MOMENTUM_GAIN = 10  # Momentum gained by interference beneficiary

NEAR_FALL_CHANCE = 0.25  # Chance of a near-fall in the finishing stretch
NEAR_FALL_HEALTH_THRESHOLD = 50  # Defender health must be below this for near-fall
MULTI_NEAR_FALL_CHANCE = 0.20  # Near-fall chance in multi-person matches

UPSET_CHANCE = 0.08  # Chance of upset (wrong winner finishing)
SHOOT_MAX_CHANCE = 0.06  # Maximum chance of going into business
SHOOT_EGO_THRESHOLD = 70  # Ego must exceed this for shoot chance
SHOOT_FRUSTRATION_THRESHOLD = 60  # Frustration must exceed this for shoot chance
SHOOT_MORALE_THRESHOLD = 30  # Morale must be below this for shoot chance
SHOOT_TITLE_MULTIPLIER = 1.5  # Multiplier for title match shoot chance

ELIMINATION_ENDURANCE_THRESHOLD = 15  # Endurance below which elimination can happen
ELIMINATION_CHANCE = 0.35  # Chance of elimination when endurance is low

FACTION_BEATDOWN_CHANCE = 0.25  # Chance of post-match heel faction beatdown
FACTION_SAVE_CHANCE = 0.15  # Chance of post-match face faction save

# ---------------------------------------------------------------------------
# Damage modifiers and floors
# ---------------------------------------------------------------------------

BASE_DAMAGE_MIN = 1  # Minimum damage for a standard move
SIGNATURE_DAMAGE_MIN = 3  # Minimum damage for a signature move
STAT_BASELINE = 50  # Baseline stat value for damage scaling (attack/50)
DEFENSE_DIVISOR = 200  # Divisor for defense stat in damage formula
STAMINA_FLOOR = 0  # Minimum stamina value
HOMETOWN_DAMAGE_MULTIPLIER = 1.1  # Damage multiplier for hometown advantage
DANGEROUS_BOTCH_DAMAGE_MULTIPLIER = 1.3  # Damage multiplier for dangerous (sev 3) botch

FINISHER_DAMAGE = 20  # Standard finisher damage
SHOOT_FINISHER_DAMAGE = 25  # Damage when going into business (unprotected)

# ---------------------------------------------------------------------------
# Momentum shift values
# ---------------------------------------------------------------------------

REVERSAL_MOMENTUM_GAIN = 8  # Momentum gained by the reverser
REVERSAL_MOMENTUM_LOSS = 8  # Momentum lost by the reversed attacker
NORMAL_HIT_MOMENTUM_GAIN = 5  # Momentum gained on normal offensive move
NORMAL_HIT_MOMENTUM_LOSS = 3  # Momentum lost by defender on normal hit

TAUNT_MOMENTUM_DEFAULT = 5  # Default momentum gain from taunt
TAUNT_MOMENTUM_INTENSE = 10  # Intense style taunt momentum gain
TAUNT_MOMENTUM_COCKY = 3  # Cocky style taunt momentum gain

# ---------------------------------------------------------------------------
# Stamina drain
# ---------------------------------------------------------------------------

ATTACKER_STAMINA_DRAIN_MIN = 1.5  # Minimum stamina drain for attacker per spot
ATTACKER_STAMINA_DRAIN_MAX = 3.5  # Maximum stamina drain for attacker per spot
DEFENDER_STAMINA_DRAIN_MIN = 0.5  # Minimum stamina drain for defender per spot
DEFENDER_STAMINA_DRAIN_MAX = 1.5  # Maximum stamina drain for defender per spot

# ---------------------------------------------------------------------------
# Endurance drain
# ---------------------------------------------------------------------------

ENDURANCE_DRAIN_FACTOR = 0.8  # Fraction of damage applied to endurance

# ---------------------------------------------------------------------------
# Match finish chances
# ---------------------------------------------------------------------------

FINISH_BASE_CHANCE = 0.3  # Base chance of finishing the match
FINISH_FINISHER_READY_CHANCE = 0.6  # Chance when finisher is available
FINISH_LOW_HEALTH_BONUS = 0.3  # Bonus when defender health < 30
FINISH_HIGH_MOMENTUM_BONUS = 0.2  # Bonus when attacker momentum > threshold
DEFENDER_LOW_HEALTH_THRESHOLD = 30  # Defender health threshold for finish bonus

# ---------------------------------------------------------------------------
# Rating calculation bonuses
# ---------------------------------------------------------------------------

VARIETY_BONUS_PER_TYPE = 0.1  # Rating bonus per unique move type used
VARIETY_BONUS_CAP = 0.5  # Maximum variety bonus
NEAR_FALL_BONUS_WEIGHT = 0.15  # Rating bonus per near-fall
NEAR_FALL_BONUS_CAP = 0.5  # Maximum near-fall rating bonus
REVERSAL_BONUS_WEIGHT = 0.08  # Rating bonus per reversal
REVERSAL_BONUS_CAP = 0.4  # Maximum reversal rating bonus
LENGTH_BONUS_DIVISOR = 30  # Ticks divisor for length bonus
LENGTH_BONUS_CAP = 0.3  # Maximum length bonus
LENGTH_BONUS_MIN_TICKS = 10  # Minimum ticks to earn length bonus
TITLE_MATCH_RATING_BONUS = 0.3  # Rating bonus for title matches
RIVALRY_HEAT_RATING_DIVISOR = (
    200.0  # Divisor for converting rivalry heat to rating bonus
)
RIVALRY_HEAT_RATING_CAP = 0.5  # Maximum rivalry heat rating bonus
INTERFERENCE_RATING_PENALTY = -0.2  # Rating penalty for interference
SIGNATURE_BONUS_WEIGHT = 0.1  # Rating bonus per signature move spot
SIGNATURE_BONUS_CAP = 0.3  # Maximum signature rating bonus
CAGE_CELL_STIP_BONUS = 0.2  # Rating bonus for cage/cell stipulation
LADDER_TABLE_STIP_BONUS = 0.25  # Rating bonus for ladder/table stipulation
GENERIC_STIP_BONUS = 0.1  # Rating bonus for other stipulations
RATING_MIN = 0.5  # Minimum match rating
RATING_MAX = 5.0  # Maximum match rating
RATING_NOISE_MIN = -0.3  # Minimum random rating noise
RATING_NOISE_MAX = 0.3  # Maximum random rating noise

# Botch penalties on rating
BOTCH_RATING_PENALTY_PER = 0.15  # Rating penalty per botch
DANGEROUS_BOTCH_EXTRA_PENALTY = 0.3  # Extra rating penalty for dangerous botches

# Card position match rating bonus
GOOD_OPENER_BONUS = 0.0  # (implicit: openers get no extra bonus)
MAIN_EVENT_TOP_BONUS = (
    0.0  # (main events get longer matches, which gives indirect bonus)
)

# ---------------------------------------------------------------------------
# Tag match constants
# ---------------------------------------------------------------------------

TAG_IN_TICKS_THRESHOLD = 5  # Minimum ticks in ring before tag-in considered
TAG_IN_STAMINA_THRESHOLD = 60  # Stamina below which tag-in is considered
TAG_IN_CHANCE = 0.35  # Chance of making a tag when conditions met
TAG_IN_MOMENTUM_BOOST = 10  # Momentum boost for fresh tag partner

HOT_TAG_TICKS_THRESHOLD = 6  # Minimum ticks beaten down before hot tag
HOT_TAG_HEALTH_THRESHOLD = 50  # Health below which hot tag is possible
HOT_TAG_CHANCE = 0.30  # Chance of hot tag when conditions met
HOT_TAG_MOMENTUM_BOOST = 25  # Momentum boost for hot tag partner

DOUBLE_TEAM_CHANCE = 0.12  # Chance of double-team move each tick

# ---------------------------------------------------------------------------
# Control switch / comeback
# ---------------------------------------------------------------------------

COMEBACK_LOW_HEALTH_THRESHOLD = 40  # Health below which fighting spirit kicks in
COMEBACK_LOW_HEALTH_BONUS = 0.15  # Bonus comeback chance at low health

# ---------------------------------------------------------------------------
# Stat modifier calculations (for simulate_match_from_db)
# ---------------------------------------------------------------------------

MORALE_MODIFIER_BASE = 0.85  # Base of morale modifier range
MORALE_MODIFIER_RANGE = 0.3  # Range of morale modifier (0.85 to 1.15)
RING_RUST_THRESHOLD_DAYS = 14  # Days before ring rust kicks in
RING_RUST_DIVISOR = 500  # Divisor for ring rust penalty
RING_RUST_FLOOR = 0.85  # Minimum ring rust modifier
CONDITIONING_MODIFIER_BASE = 0.85  # Base of conditioning modifier
CONDITIONING_MODIFIER_RANGE = 0.15  # Range of conditioning modifier (0.85 to 1.0)

# ---------------------------------------------------------------------------
# Post-match condition wear
# ---------------------------------------------------------------------------

STAMINA_WEAR_FACTOR = 0.5  # Fraction of stamina loss applied to condition
HEALTH_WEAR_FACTOR = 0.3  # Fraction of health loss applied to condition
INJURY_HEALTH_THRESHOLD = 20  # Health below which injury check occurs
DEFAULT_INJURY_PRONE = 30  # Default injury_prone stat if not found
INJURY_PRONE_DIVISOR = 200  # Divisor for injury probability

# ---------------------------------------------------------------------------
# Trust penalty
# ---------------------------------------------------------------------------

LOW_TRUST_THRESHOLD = 30  # Trust below which botch penalty applies
LOW_TRUST_PENALTY_DIVISOR = 300  # Divisor for computing trust botch penalty

# ---------------------------------------------------------------------------
# Crowd heat
# ---------------------------------------------------------------------------

RIVALRY_HEAT_CROWD_FACTOR = 0.15  # Fraction of rivalry heat added to crowd base
CROWD_HEAT_MIN = 0  # Minimum crowd heat
CROWD_HEAT_MAX = 100  # Maximum crowd heat

# ---------------------------------------------------------------------------
# Highlight tier thresholds
# ---------------------------------------------------------------------------

HIGHLIGHT_DAMAGE_THRESHOLD = 10  # Damage at which a spot becomes a highlight
