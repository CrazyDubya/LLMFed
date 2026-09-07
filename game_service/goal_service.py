"""
Career Goals Service — Goal creation, evaluation, and completion checks.

Extracted from wrestler_lifecycle_service.py (Group 2).
"""

import logging
from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB,
    ChampionshipDB,
    MatchParticipantDB,
    MatchDB,
    ShowDB,
    ShowSegmentDB,
    WrestlerPushDB,
    WrestlerGoalDB,
    WrestlerHistoryDB,
)
from game_service.lifecycle_constants import (
    GOAL_COMPLETE_MORALE_BONUS,
    GOAL_COMPLETE_SATISFACTION_BONUS,
    GOAL_FRUSTRATION_PER_WEEK,
    GOAL_FRUSTRATION_MORALE_THRESHOLD,
    GOAL_FRUSTRATION_MORALE_PENALTY,
    GOAL_FRUSTRATION_ALIGNMENT_THRESHOLD,
    GOAL_FRUSTRATION_ALIGNMENT_SHIFT,
    GLASS_CEILING_WEEKS,
    GLASS_CEILING_FRUSTRATION_BONUS,
    TITLE_GOAL_TYPES,
    LOW_SATISFACTION_THRESHOLD,
    LOW_SATISFACTION_MORALE_PENALTY,
    HIGH_SATISFACTION_THRESHOLD,
    HIGH_SATISFACTION_MORALE_BONUS,
    GOAL_PROVE_MYSELF_POP,
    GOAL_LEGACY_THRESHOLD,
    GOAL_TOP_DRAW_RATING,
    GOAL_EARN_RESPECT_POP,
    GOAL_EARN_RESPECT_MORALE,
    GOAL_HEADLINE_POP,
)

logger = logging.getLogger(__name__)


def create_wrestler_goals(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Create structured goal records from the wrestler's career_goals JSON."""
    goals = wrestler.career_goals or []
    for goal_type in goals:
        existing = (
            db.query(WrestlerGoalDB)
            .filter(
                WrestlerGoalDB.wrestler_id == wrestler.id,
                WrestlerGoalDB.goal_type == goal_type,
                WrestlerGoalDB.status == "active",
            )
            .first()
        )
        if not existing:
            db.add(
                WrestlerGoalDB(
                    wrestler_id=wrestler.id,
                    goal_type=goal_type,
                    set_date=game_date,
                )
            )


def evaluate_goals(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Check progress on all active goals. Returns list of completed goal types."""
    active = (
        db.query(WrestlerGoalDB)
        .filter(
            WrestlerGoalDB.wrestler_id == wrestler.id,
            WrestlerGoalDB.status == "active",
        )
        .all()
    )

    completed = []
    for goal in active:
        if _check_goal_completed(db, wrestler, goal):
            goal.status = "completed"
            goal.completed_date = game_date
            completed.append(goal.goal_type)

            wrestler.morale = min(
                100, (wrestler.morale or 50) + GOAL_COMPLETE_MORALE_BONUS
            )
            wrestler.satisfaction = min(
                100, (wrestler.satisfaction or 50) + GOAL_COMPLETE_SATISFACTION_BONUS
            )

            db.add(
                WrestlerHistoryDB(
                    wrestler_id=wrestler.id,
                    game_date=game_date,
                    event_type="goal_completed",
                    description=f"Achieved career goal: {goal.goal_type}",
                )
            )
        else:
            # Frustration grows when stuck
            goal.frustration = min(
                100, (goal.frustration or 0) + GOAL_FRUSTRATION_PER_WEEK
            )

            if goal.frustration > GOAL_FRUSTRATION_MORALE_THRESHOLD:
                wrestler.morale = max(
                    0, (wrestler.morale or 50) - GOAL_FRUSTRATION_MORALE_PENALTY
                )
                # Frustrated faces drift heel
                if (
                    wrestler.alignment == "face"
                    and goal.frustration > GOAL_FRUSTRATION_ALIGNMENT_THRESHOLD
                ):
                    wrestler.alignment_momentum = (
                        wrestler.alignment_momentum or 0
                    ) + GOAL_FRUSTRATION_ALIGNMENT_SHIFT

    # Glass ceiling detection
    push = (
        db.query(WrestlerPushDB)
        .filter(
            WrestlerPushDB.wrestler_id == wrestler.id,
        )
        .first()
    )
    if push and (push.weeks_at_tier or 0) > GLASS_CEILING_WEEKS:
        title_goals = [g for g in active if g.goal_type in TITLE_GOAL_TYPES]
        for g in title_goals:
            g.frustration = min(
                100, (g.frustration or 0) + GLASS_CEILING_FRUSTRATION_BONUS
            )

    # Satisfaction influences morale
    sat = wrestler.satisfaction or 50
    if sat < LOW_SATISFACTION_THRESHOLD:
        wrestler.morale = max(
            0, (wrestler.morale or 50) - LOW_SATISFACTION_MORALE_PENALTY
        )
    elif sat > HIGH_SATISFACTION_THRESHOLD:
        wrestler.morale = min(
            100, (wrestler.morale or 50) + HIGH_SATISFACTION_MORALE_BONUS
        )

    return completed


def _check_goal_completed(
    db: Session, wrestler: GameWrestlerDB, goal: WrestlerGoalDB
) -> bool:
    """Check if a specific goal has been achieved."""
    gt = goal.goal_type

    if gt in ("win_title", "become_champion", "win_first_title", "one_more_title_run"):
        # Check if wrestler currently holds any title
        champ = (
            db.query(ChampionshipDB)
            .filter(
                ChampionshipDB.current_holder_id == wrestler.id,
            )
            .first()
        )
        return champ is not None

    if gt == "main_event_ppv":
        # Check if wrestler main evented a PPV show
        ppv_main = (
            db.query(MatchParticipantDB)
            .join(MatchDB)
            .join(ShowSegmentDB)
            .join(ShowDB)
            .filter(
                MatchParticipantDB.wrestler_id == wrestler.id,
                ShowDB.show_type == "ppv",
                MatchDB.is_completed == True,
            )
            .first()
        )
        return ppv_main is not None

    if gt in ("have_5_star_match", "5_star_match"):
        best = (
            db.query(MatchParticipantDB)
            .join(MatchDB)
            .filter(
                MatchParticipantDB.wrestler_id == wrestler.id,
                MatchDB.match_rating >= 4.8,
            )
            .first()
        )
        return best is not None

    if gt == "defeat_rival":
        if goal.target_entity_id:
            win = (
                db.query(MatchParticipantDB)
                .join(MatchDB)
                .filter(
                    MatchParticipantDB.wrestler_id == wrestler.id,
                    MatchParticipantDB.is_winner == True,
                    MatchDB.winner_id == wrestler.id,
                )
                .first()
            )
            return win is not None
        return False

    if gt == "prove_myself":
        return (wrestler.popularity or 0) >= GOAL_PROVE_MYSELF_POP

    if gt in ("build_legacy", "cement_legacy"):
        return (wrestler.legacy_score or 0) >= GOAL_LEGACY_THRESHOLD

    if gt == "become_top_draw":
        return (wrestler.draw_rating or 0) >= GOAL_TOP_DRAW_RATING

    if gt in ("earn_respect", "prove_doubters_wrong"):
        return (wrestler.popularity or 0) >= GOAL_EARN_RESPECT_POP and (
            wrestler.morale or 0
        ) >= GOAL_EARN_RESPECT_MORALE

    if gt == "make_it_to_main_event":
        push = (
            db.query(WrestlerPushDB)
            .filter(
                WrestlerPushDB.wrestler_id == wrestler.id,
                WrestlerPushDB.push_tier == "main_event",
            )
            .first()
        )
        return push is not None

    if gt == "headline_biggest_show":
        return (wrestler.popularity or 0) >= GOAL_HEADLINE_POP

    return False
