"""
Match DB Integration

Extracted from match_engine.py — functions that bridge between the DB models
and the match simulation engine.  Includes ``simulate_match_from_db`` (the
main entry point used by world_ticker) and ``_generate_post_match_angle``.
"""

import random
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB,
    WrestlerStatsDB,
    MatchDB,
    MatchParticipantDB,
    MatchEventDB,
)
from core_engine.match_constants import (
    STAMINA_WEAR_FACTOR,
    HEALTH_WEAR_FACTOR,
    INJURY_HEALTH_THRESHOLD,
    DEFAULT_INJURY_PRONE,
    INJURY_PRONE_DIVISOR,
    LOW_TRUST_THRESHOLD,
    LOW_TRUST_PENALTY_DIVISOR,
    MORALE_MODIFIER_BASE,
    MORALE_MODIFIER_RANGE,
    RING_RUST_THRESHOLD_DAYS,
    RING_RUST_DIVISOR,
    RING_RUST_FLOOR,
    CONDITIONING_MODIFIER_BASE,
    CONDITIONING_MODIFIER_RANGE,
    FACTION_BEATDOWN_CHANCE,
    FACTION_SAVE_CHANCE,
    HIGHLIGHT_DAMAGE_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: Stat modifier calculation
# ---------------------------------------------------------------------------


def _build_stat_modifiers(
    morale: float, ring_rust_days: int, conditioning: float
) -> float:
    """Compute a combined stat modifier from morale, ring rust, and conditioning.

    Returns a multiplier (roughly 0.6-1.15) applied to all wrestler stats
    before a match simulation.
    """
    # Morale affects performance: range MORALE_MODIFIER_BASE to BASE+RANGE
    stat_modifier = MORALE_MODIFIER_BASE + (morale / 100) * MORALE_MODIFIER_RANGE

    # Ring rust penalty for wrestlers who haven't competed recently
    if ring_rust_days > RING_RUST_THRESHOLD_DAYS:
        stat_modifier *= max(
            RING_RUST_FLOOR, 1.0 - (ring_rust_days / RING_RUST_DIVISOR)
        )

    # Conditioning modifier
    cond_modifier = (
        CONDITIONING_MODIFIER_BASE + (conditioning / 100) * CONDITIONING_MODIFIER_RANGE
    )
    stat_modifier *= cond_modifier

    return stat_modifier


# ---------------------------------------------------------------------------
# Run a match from DB models
# ---------------------------------------------------------------------------


def simulate_match_from_db(db: Session, match: MatchDB, game_date: str = None):
    """Load match data from DB, simulate, and persist results.

    Returns a :class:`MatchResult`.
    """
    # Late imports to avoid circular dependency at module load time
    from core_engine.match_engine import (
        MatchSimulator,
        MatchParticipantState,
        ManagerContext,
        MatchResult,
    )

    participants_db = (
        db.query(MatchParticipantDB)
        .filter(
            MatchParticipantDB.match_id == match.id,
            MatchParticipantDB.role == "competitor",
        )
        .all()
    )

    if len(participants_db) < 2:
        return MatchResult(narrative_summary="Not enough competitors")

    # Build participant states with morale modifier
    participant_states = []
    for p in participants_db:
        wrestler = (
            db.query(GameWrestlerDB).filter(GameWrestlerDB.id == p.wrestler_id).first()
        )
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == p.wrestler_id)
            .first()
        )

        if not wrestler or not stats:
            continue

        morale = wrestler.morale if wrestler.morale is not None else 50
        ring_rust = getattr(wrestler, "ring_rust_days", 0) or 0
        conditioning = getattr(stats, "conditioning_level", 70) or 70
        stat_modifier = _build_stat_modifiers(morale, ring_rust, conditioning)

        # Load signature moves
        sig_moves = []
        if wrestler.signature_moves:
            for sig in wrestler.signature_moves:
                if isinstance(sig, (list, tuple)) and len(sig) >= 3:
                    sig_moves.append(tuple(sig))

        # Load charisma style
        personality = wrestler.personality_traits or {}
        charisma_style = (
            personality.get("charisma_style", "humble")
            if isinstance(personality, dict)
            else "humble"
        )

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
            bond = (
                db.query(ManagerClientDB)
                .filter_by(client_wrestler_id=p_state.wrestler_id, is_active=True)
                .first()
            )
            if bond:
                mgr = db.query(ManagerDB).filter_by(id=bond.manager_id).first()
                if mgr:
                    managers.append(
                        ManagerContext(
                            manager_id=mgr.id,
                            manager_name=mgr.name,
                            client_wrestler_id=p_state.wrestler_id,
                            interference_skill=mgr.interference_skill or 50,
                            cunning=mgr.cunning or 50,
                            specialization=bond.specialization or "all_around",
                        )
                    )
    except Exception:
        pass  # Manager integration is optional

    # Calculate rivalry heat and trust between participants
    rivalry_heat = 0
    trust_penalty = 0.0
    try:
        from models.game_models import WrestlerRelationshipDB

        if len(participant_states) >= 2 and match.world_id:
            rel = (
                db.query(WrestlerRelationshipDB)
                .filter(
                    WrestlerRelationshipDB.world_id == match.world_id,
                    WrestlerRelationshipDB.wrestler1_id.in_(
                        [
                            participant_states[0].wrestler_id,
                            participant_states[1].wrestler_id,
                        ]
                    ),
                    WrestlerRelationshipDB.wrestler2_id.in_(
                        [
                            participant_states[0].wrestler_id,
                            participant_states[1].wrestler_id,
                        ]
                    ),
                )
                .first()
            )
            if rel:
                rivalry_heat = rel.rivalry_heat or 0
                # Low trust = higher botch chance (wrestlers don't protect each other)
                trust = rel.trust_level if rel.trust_level is not None else 50
                if trust < LOW_TRUST_THRESHOLD:
                    trust_penalty = (
                        LOW_TRUST_THRESHOLD - trust
                    ) / LOW_TRUST_PENALTY_DIVISOR
    except Exception:
        pass  # Rivalry heat is optional

    # Load frustration and morale for going-into-business checks
    try:
        from models.game_models import WrestlerGoalDB

        for p_state in participant_states:
            wrestler = (
                db.query(GameWrestlerDB)
                .filter(GameWrestlerDB.id == p_state.wrestler_id)
                .first()
            )
            if wrestler:
                p_state._morale = wrestler.morale or 50
                # Get max frustration from active goals
                max_frust = (
                    db.query(WrestlerGoalDB)
                    .filter(
                        WrestlerGoalDB.wrestler_id == p_state.wrestler_id,
                        WrestlerGoalDB.status == "active",
                    )
                    .all()
                )
                p_state._frustration = max(
                    (g.frustration for g in max_frust), default=0
                )
                # Get ego from backstory
                from models.game_models import WrestlerBackstoryDB

                backstory = (
                    db.query(WrestlerBackstoryDB)
                    .filter(WrestlerBackstoryDB.wrestler_id == p_state.wrestler_id)
                    .first()
                )
                if backstory and backstory.real_personality:
                    p_state.stats["ego"] = backstory.real_personality.get("ego", 50)
    except Exception:
        pass  # Frustration/ego loading is optional

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
    simulator._trust_penalty = trust_penalty
    result = simulator.simulate(participant_states)

    # Apply chemistry bonus from wrestler relationships
    try:
        from core_engine.match_aftermath import get_chemistry_bonus

        if len(participant_states) >= 2 and match.world_id:
            chem_bonus = get_chemistry_bonus(
                db,
                match.world_id,
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
            "tick": s.tick,
            "attacker": s.attacker_id,
            "defender": s.defender_id,
            "move": s.move_name,
            "move_type": s.move_type,
            "damage": s.damage,
            "reversed": s.was_reversed,
            "is_near_fall": s.is_near_fall,
            "is_finisher": s.is_finisher,
            "is_finish": s.is_finish,
            "crowd_reaction": s.crowd_reaction,
            "highlight_tier": (
                3
                if s.is_finisher or s.is_finish
                else 2
                if s.is_near_fall
                or s.was_reversed
                or s.damage >= HIGHLIGHT_DAMAGE_THRESHOLD
                else 1
            ),
            "description": s.description,
            "is_botch": s.is_botch,
            "botch_severity": s.botch_severity,
            "is_shoot": s.is_shoot,
        }
        for s in result.spots
    ]

    # Persist individual match events
    for spot in result.spots:
        db.add(
            MatchEventDB(
                match_id=match.id,
                tick=spot.tick,
                acting_wrestler_id=spot.attacker_id,
                target_wrestler_id=spot.defender_id,
                event_type=spot.move_type,
                description=spot.description,
                crowd_reaction=spot.crowd_reaction,
                heat_change=spot.heat_change,
                damage=spot.damage,
            )
        )

    # Update winner's participation record
    for p in participants_db:
        if p.wrestler_id == result.winner_id:
            p.is_winner = True
        p.performance_rating = result.match_rating

    # Wear on wrestlers' condition
    for p_state in participant_states:
        wrestler = (
            db.query(GameWrestlerDB)
            .filter(GameWrestlerDB.id == p_state.wrestler_id)
            .first()
        )
        if wrestler:
            stamina_loss = int((100 - p_state.stamina) * STAMINA_WEAR_FACTOR)
            health_loss = int((100 - p_state.health) * HEALTH_WEAR_FACTOR)
            wrestler.condition = max(0, wrestler.condition - stamina_loss - health_loss)

            # Injury risk check
            if p_state.health < INJURY_HEALTH_THRESHOLD:
                injury_prone = DEFAULT_INJURY_PRONE
                s = (
                    db.query(WrestlerStatsDB)
                    .filter(WrestlerStatsDB.wrestler_id == wrestler.id)
                    .first()
                )
                if s:
                    injury_prone = s.injury_prone
                if random.random() < injury_prone / INJURY_PRONE_DIVISOR:
                    wrestler.is_injured = True
                    weeks = random.randint(2, 12)
                    from game_service.world_ticker import advance_game_date

                    # Use the match's actual game date for return date calculation
                    match_date = game_date or getattr(match, "game_date", None)
                    if not match_date and match.world_id:
                        from models.game_models import WorldDB

                        world = (
                            db.query(WorldDB)
                            .filter(WorldDB.id == match.world_id)
                            .first()
                        )
                        if world:
                            match_date = world.current_game_date
                    if match_date:
                        wrestler.injury_return_date = advance_game_date(
                            match_date, weeks * 7
                        )
                    else:
                        logger.warning(
                            "No game_date available for injury return date; skipping return date"
                        )
                        wrestler.injury_return_date = None

    # Generate post-match angle (faction run-ins, beatdowns)
    result.post_match_angle = _generate_post_match_angle(
        db, match, result, participant_states
    )

    return result


def _generate_post_match_angle(
    db: Session,
    match: MatchDB,
    result,
    participants,
) -> Optional[Dict[str, Any]]:
    """Check if a post-match angle occurs — faction attacks, saves, etc."""
    from core_engine.match_engine import POST_MATCH_ATTACK, POST_MATCH_SAVE

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
        winner_member = (
            db.query(StableMemberDB)
            .filter_by(wrestler_id=result.winner_id, is_active=True)
            .first()
        )
        if winner_member:
            stable = (
                db.query(StableDB)
                .filter_by(id=winner_member.stable_id, is_active=True)
                .first()
            )
            if (
                stable
                and stable.alignment == "heel"
                and random.random() < FACTION_BEATDOWN_CHANCE
            ):
                # Faction beatdown on the loser
                stablemates = (
                    db.query(StableMemberDB)
                    .filter_by(stable_id=stable.id, is_active=True)
                    .all()
                )
                attacker_ids = [
                    m.wrestler_id
                    for m in stablemates
                    if m.wrestler_id != result.winner_id
                ]
                if attacker_ids:
                    attackers = (
                        db.query(GameWrestlerDB)
                        .filter(GameWrestlerDB.id.in_(attacker_ids[:2]))
                        .all()
                    )
                    attacker_names = " & ".join(a.name for a in attackers)
                    victim = db.query(GameWrestlerDB).filter_by(id=loser_id).first()
                    desc = random.choice(POST_MATCH_ATTACK).format(
                        attackers=f"{stable.name} ({attacker_names})",
                        victim=victim.name if victim else "the loser",
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
        loser_member = (
            db.query(StableMemberDB)
            .filter_by(wrestler_id=loser_id, is_active=True)
            .first()
        )
        if loser_member:
            stable = (
                db.query(StableDB)
                .filter_by(id=loser_member.stable_id, is_active=True)
                .first()
            )
            if (
                stable
                and stable.alignment == "face"
                and random.random() < FACTION_SAVE_CHANCE
            ):
                stablemates = (
                    db.query(StableMemberDB)
                    .filter_by(stable_id=stable.id, is_active=True)
                    .all()
                )
                saver_ids = [
                    m.wrestler_id for m in stablemates if m.wrestler_id != loser_id
                ]
                if saver_ids:
                    savers = (
                        db.query(GameWrestlerDB)
                        .filter(GameWrestlerDB.id.in_(saver_ids[:2]))
                        .all()
                    )
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
