"""
SQLAlchemy models for the LLMFed wrestling world game.

These models define the full persistent world schema: users, players, wrestlers,
federations, shows, matches, storylines, championships, contracts, and narrative logs.

This module acts as a barrel file — all models are defined in focused submodules
and re-exported here so that existing ``from models.game_models import X`` imports
continue to work without changes.
"""

import enum

from models.db_models import Base  # noqa: F401 — re-export for consumers

# Re-export every model from the submodules
from models.core_models import *        # noqa: F401,F403
from models.federation_models import *  # noqa: F401,F403
from models.wrestler_models import *    # noqa: F401,F403
from models.show_models import *        # noqa: F401,F403
from models.social_models import *      # noqa: F401,F403


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlayerType(str, enum.Enum):
    PROMOTER = "promoter"
    WRESTLER = "wrestler"


class WrestlerAlignment(str, enum.Enum):
    FACE = "face"          # Good guy
    HEEL = "heel"          # Bad guy
    TWEENER = "tweener"    # In between


class ShowType(str, enum.Enum):
    WEEKLY = "weekly"
    PPV = "ppv"
    SPECIAL = "special"
    HOUSE_SHOW = "house_show"


class SegmentType(str, enum.Enum):
    MATCH = "match"
    PROMO = "promo"
    BACKSTAGE = "backstage"
    INTERVIEW = "interview"
    ENTRANCE = "entrance"
    ANGLE = "angle"         # Storyline progression


class MatchType(str, enum.Enum):
    SINGLES = "singles"
    TAG_TEAM = "tag_team"
    TRIPLE_THREAT = "triple_threat"
    FATAL_FOUR_WAY = "fatal_four_way"
    BATTLE_ROYAL = "battle_royal"
    LADDER = "ladder"
    CAGE = "cage"
    HELL_IN_A_CELL = "hell_in_a_cell"
    ROYAL_RUMBLE = "royal_rumble"
    TABLES = "tables"
    IRON_MAN = "iron_man"


class MatchFinish(str, enum.Enum):
    PINFALL = "pinfall"
    SUBMISSION = "submission"
    COUNT_OUT = "count_out"
    DQ = "disqualification"
    NO_CONTEST = "no_contest"
    STIPULATION = "stipulation"  # Ladder grab, cage escape, etc.


class ContractStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    OFFERED = "offered"


class StorylineStatus(str, enum.Enum):
    BREWING = "brewing"       # Building tension
    ACTIVE = "active"         # In full swing
    CLIMAX = "climax"         # Approaching blowoff
    RESOLVED = "resolved"     # Finished
    ABANDONED = "abandoned"   # Dropped


class StorylineType(str, enum.Enum):
    FEUD = "feud"
    ALLIANCE = "alliance"
    BETRAYAL = "betrayal"
    CHAMPIONSHIP_CHASE = "championship_chase"
    DEBUT = "debut"
    RETURN = "return"
    RETIREMENT = "retirement"
    MYSTERY = "mystery"
    FACTION_WAR = "faction_war"
    POWER_STRUGGLE = "power_struggle"
    MANAGER_BETRAYAL = "manager_betrayal"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionType(str, enum.Enum):
    # Promoter actions
    BOOK_SHOW = "book_show"
    BOOK_MATCH = "book_match"
    SIGN_WRESTLER = "sign_wrestler"
    RELEASE_WRESTLER = "release_wrestler"
    CREATE_CHAMPIONSHIP = "create_championship"
    SET_STORYLINE = "set_storyline"
    SET_TV_DEAL = "set_tv_deal"
    # Wrestler actions
    TRAIN = "train"
    CUT_PROMO = "cut_promo"
    CHALLENGE = "challenge"
    FORM_TAG_TEAM = "form_tag_team"
    ACCEPT_CONTRACT = "accept_contract"
    REJECT_CONTRACT = "reject_contract"
    REQUEST_RELEASE = "request_release"
    # Faction/manager actions
    FORM_STABLE = "form_stable"
    JOIN_STABLE = "join_stable"
    LEAVE_STABLE = "leave_stable"
    ASSIGN_MANAGER = "assign_manager"
    CREATE_MANAGER = "create_manager"
    # Narrative control
    CREATE_STORYLINE = "create_storyline"
    ADVANCE_STORYLINE = "advance_storyline"
    DISSOLVE_STABLE = "dissolve_stable"
    REMOVE_MANAGER = "remove_manager"


class StableRole(str, enum.Enum):
    LEADER = "leader"
    ENFORCER = "enforcer"
    MOUTHPIECE = "mouthpiece"
    LIEUTENANT = "lieutenant"
    MEMBER = "member"
    RECRUIT = "recruit"


class ManagerArchetype(str, enum.Enum):
    SCHEMING_MANAGER = "scheming_manager"
    CORPORATE_SUIT = "corporate_suit"
    FLAMBOYANT_MOUTHPIECE = "flamboyant_mouthpiece"
    ENFORCER_TYPE = "enforcer_type"
    OLD_SCHOOL = "old_school"


class ManagerRole(str, enum.Enum):
    MANAGER = "manager"
    VALET = "valet"
    ADVOCATE = "advocate"
    HANDLER = "handler"


class ManagerSpecialization(str, enum.Enum):
    PROMO_BOOST = "promo_boost"
    INTERFERENCE = "interference"
    NEGOTIATION = "negotiation"
    DISTRACTION = "distraction"
    ALL_AROUND = "all_around"
