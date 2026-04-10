"""
Wrestler Lifecycle Service — aging, goals, politics, developmental,
legacy/HoF, physical identity & conditioning.

Goals: goal_service.py | Politics: politics_service.py | Data: lifecycle_constants.py
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB, WrestlerStatsDB, GameFederationDB, ContractDB,
    ChampionshipHistoryDB, MatchParticipantDB, MatchDB,
    ShowDB, ShowSegmentDB, WrestlerPushDB,
    GameNarrativeLogDB,
    MentorshipDB, CareerHighlightDB, HallOfFameDB,
    GimmickHistoryDB, WrestlerBackstoryDB, LifeEventDB,
)
import game_service.lifecycle_constants as LC

# Re-exports so existing imports from this module keep working
from game_service.goal_service import (          # noqa: F401
    create_wrestler_goals, evaluate_goals, _check_goal_completed,
)
from game_service.politics_service import (      # noqa: F401
    update_locker_room_dynamics, apply_politics_to_booking,
)

logger = logging.getLogger(__name__)


# -- Shared helpers ----------------------------------------------------------

def _get_wrestler_stats(db: Session, wrestler_id: str) -> Optional[WrestlerStatsDB]:
    """Fetch a wrestler's stats row (returns None if missing)."""
    return db.query(WrestlerStatsDB).filter(
        WrestlerStatsDB.wrestler_id == wrestler_id
    ).first()


# -- Group 1: Aging, Physical Decline & Career Arc --------------------------

def update_career_phase(wrestler: GameWrestlerDB):
    """Derive career phase from age and peak_age."""
    age = wrestler.age or 25
    peak = wrestler.peak_age or 28
    exp = wrestler.experience_years or 0

    if exp < LC.CAREER_PHASE_ROOKIE_MAX_EXP:
        wrestler.career_phase = "rookie"
    elif age < peak + LC.CAREER_PHASE_RISING_OFFSET:
        wrestler.career_phase = "rising"
    elif age < peak + LC.CAREER_PHASE_PRIME_OFFSET:
        wrestler.career_phase = "prime"
    elif age < peak + LC.CAREER_PHASE_VETERAN_OFFSET:
        wrestler.career_phase = "veteran"
    else:
        wrestler.career_phase = "declining"


def age_wrestlers(db: Session, world_id: str, game_date: str):
    """Annual aging — run on Jan 1 each game year. Increments age, applies stat decay."""
    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == True,
    ).all()

    for w in wrestlers:
        w.age = (w.age or 25) + 1
        w.experience_years = (w.experience_years or 0) + 1
        update_career_phase(w)

        peak = w.peak_age or 28
        if w.age > peak:
            stats = _get_wrestler_stats(db, w.id)
            if not stats:
                continue

            years_past = w.age - peak
            decline = min(years_past, LC.MAX_DECLINE_PER_YEAR)

            for attr in LC.EARLY_DECLINE_STATS:
                old = getattr(stats, attr, 50)
                setattr(stats, attr, max(LC.MIN_STAT_FLOOR, old - random.randint(1, decline)))

            if years_past > LC.LATE_DECLINE_YEARS_THRESHOLD:
                for attr in LC.LATE_DECLINE_STATS:
                    old = getattr(stats, attr, 50)
                    setattr(stats, attr, max(LC.MIN_STAT_FLOOR, old - random.randint(0, decline - 1)))

            for attr in LC.IMPROVING_STATS:
                old = getattr(stats, attr, 50)
                setattr(stats, attr, min(LC.MAX_STAT_CAP, old + random.randint(0, LC.IMPROVING_STAT_MAX_GAIN)))


def calculate_retirement_pressure(wrestler: GameWrestlerDB) -> int:
    """Calculate how likely a wrestler is to retire (replaces flat 1% random)."""
    rp = LC.RETIREMENT_PRESSURE
    pressure = 0
    phase = wrestler.career_phase or "prime"

    if phase == "declining":
        pressure += rp["declining_phase"]
    elif phase == "veteran":
        pressure += rp["veteran_phase"]

    if (wrestler.morale or 50) < rp["low_morale_threshold"]:
        pressure += rp["low_morale_bonus"]

    if wrestler.is_injured and (wrestler.age or 25) > rp["injured_age_threshold"]:
        pressure += rp["injured_bonus"]

    if (wrestler.popularity or 50) < rp["low_pop_threshold"] and (wrestler.age or 25) > rp["low_pop_age_threshold"]:
        pressure += rp["low_pop_bonus"]

    if (wrestler.age or 25) > rp["old_age_threshold"]:
        pressure += rp["old_age_bonus"]

    return pressure


def calculate_ring_rust_modifier(wrestler: GameWrestlerDB) -> float:
    """Ring rust modifier for match engine (0.85 - 1.0)."""
    rust = wrestler.ring_rust_days or 0
    if rust <= LC.RING_RUST_NO_PENALTY_DAYS:
        return 1.0
    return max(LC.RING_RUST_MIN_MODIFIER, 1.0 - (rust / LC.RING_RUST_DIVISOR))


# -- Group 4: Developmental Pipeline ----------------------------------------

def assign_mentor(db: Session, federation: GameFederationDB,
                  protege: GameWrestlerDB, mentor: GameWrestlerDB,
                  game_date: str) -> Optional[MentorshipDB]:
    """Assign a veteran mentor to a young wrestler."""
    mentor_stats = _get_wrestler_stats(db, mentor.id)
    if not mentor_stats or (mentor_stats.psychology or 0) < LC.MENTOR_MIN_PSYCHOLOGY:
        return None

    bonus = ((mentor_stats.psychology or 50) + (mentor_stats.work_ethic or 50)) / LC.MENTOR_BONUS_DIVISOR
    m = MentorshipDB(
        world_id=federation.world_id,
        mentor_id=mentor.id,
        protege_id=protege.id,
        federation_id=federation.id,
        started_date=game_date,
        skill_focus=mentor.finisher_type or "technical",
        mentor_bonus=round(bonus, 2),
    )
    db.add(m)
    return m


def auto_assign_mentors(db: Session, federation: GameFederationDB, game_date: str):
    """NPC federation auto-assigns mentors to unmentored rookies."""
    contracts = db.query(ContractDB).filter(
        ContractDB.federation_id == federation.id,
        ContractDB.status == "active",
    ).all()
    wrestler_ids = [c.wrestler_id for c in contracts]
    if not wrestler_ids:
        return

    rookies = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id.in_(wrestler_ids),
        GameWrestlerDB.is_active == True,
        GameWrestlerDB.career_phase == "rookie",
    ).all()

    mentored_ids = set(
        m.protege_id for m in db.query(MentorshipDB).filter(
            MentorshipDB.federation_id == federation.id,
            MentorshipDB.is_active == True,
        ).all()
    )
    mentoring_ids = set(
        m.mentor_id for m in db.query(MentorshipDB).filter(
            MentorshipDB.federation_id == federation.id,
            MentorshipDB.is_active == True,
        ).all()
    )

    veterans = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id.in_(wrestler_ids),
        GameWrestlerDB.is_active == True,
        GameWrestlerDB.career_phase.in_(["veteran", "declining"]),
        GameWrestlerDB.is_injured == False,
    ).all()

    for rookie in rookies:
        if rookie.id in mentored_ids:
            continue
        for vet in veterans:
            if vet.id in mentoring_ids:
                continue
            m = assign_mentor(db, federation, rookie, vet, game_date)
            if m:
                mentoring_ids.add(vet.id)
                mentored_ids.add(rookie.id)
                break


def check_debut_readiness(db: Session, wrestler: GameWrestlerDB) -> bool:
    """Check if a developmental wrestler is ready for a TV tryout."""
    push = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.wrestler_id == wrestler.id,
        WrestlerPushDB.push_tier == "developmental",
    ).first()
    if not push or (push.weeks_at_tier or 0) < LC.DEBUT_MIN_WEEKS:
        return False

    stats = _get_wrestler_stats(db, wrestler.id)
    if not stats:
        return False

    avg_ring = sum(getattr(stats, a, 50) or 50 for a in LC.DEBUT_RING_STATS) / len(LC.DEBUT_RING_STATS)
    return avg_ring > LC.DEBUT_MIN_AVG_RING and (stats.psychology or 0) > LC.DEBUT_MIN_PSYCHOLOGY


def training_with_mentor(db: Session, wrestler_id: str, stat_name: str) -> int:
    """Enhanced training gain when wrestler has an active mentor.
    Returns bonus gain on top of base training."""
    mentorship = db.query(MentorshipDB).filter(
        MentorshipDB.protege_id == wrestler_id,
        MentorshipDB.is_active == True,
    ).first()
    if not mentorship:
        return 0

    bonus = 0
    if stat_name == mentorship.skill_focus:
        bonus = max(1, int(mentorship.mentor_bonus * LC.MENTOR_SPECIALTY_MULTIPLIER))
    elif stat_name == "psychology":
        bonus = LC.MENTOR_PSYCHOLOGY_BONUS

    if random.random() < LC.MENTOR_SELF_IMPROVE_CHANCE:
        mentor_stats = _get_wrestler_stats(db, mentorship.mentor_id)
        if mentor_stats and (mentor_stats.psychology or 0) < LC.MAX_STAT_CAP:
            mentor_stats.psychology = min(LC.MAX_STAT_CAP, (mentor_stats.psychology or 50) + 1)

    return bonus


# -- Group 5: Legacy, Hall of Fame & Nostalgia ------------------------------

def record_career_highlight(db: Session, wrestler_id: str, highlight_type: str,
                            description: str, game_date: str,
                            significance: int = 5, match_id: str = None):
    """Record a notable career moment."""
    db.add(CareerHighlightDB(
        wrestler_id=wrestler_id,
        highlight_type=highlight_type,
        description=description,
        game_date=game_date,
        significance=significance,
        match_id=match_id,
    ))


def check_match_highlights(db: Session, match: MatchDB, wrestler_id: str,
                           game_date: str):
    """Check if a match produced career highlights."""
    rating = match.match_rating or 0

    if rating >= LC.HIGHLIGHT_STAR_THRESHOLD:
        record_career_highlight(
            db, wrestler_id, "5_star_classic",
            f"A {rating}-star classic",
            game_date,
            significance=min(LC.HIGHLIGHT_MAX_SIGNIFICANCE,
                             int(rating * LC.HIGHLIGHT_SIGNIFICANCE_MULTIPLIER)),
            match_id=match.id,
        )

    if match.is_title_match and match.winner_id == wrestler_id:
        prev_reigns = db.query(ChampionshipHistoryDB).filter(
            ChampionshipHistoryDB.wrestler_id == wrestler_id,
        ).count()
        if prev_reigns <= 1:
            record_career_highlight(
                db, wrestler_id, "first_title_win",
                "Won their first championship",
                game_date, significance=8, match_id=match.id,
            )


def compute_legacy_score(db: Session, wrestler_id: str) -> int:
    """Compute a wrestler's legacy score from their career."""
    highlights = db.query(CareerHighlightDB).filter(
        CareerHighlightDB.wrestler_id == wrestler_id,
    ).count()

    reigns = db.query(ChampionshipHistoryDB).filter(
        ChampionshipHistoryDB.wrestler_id == wrestler_id,
    ).count()

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id,
    ).first()
    years = wrestler.experience_years or 0 if wrestler else 0

    participations = db.query(MatchParticipantDB).join(MatchDB).filter(
        MatchParticipantDB.wrestler_id == wrestler_id,
        MatchDB.is_completed == True,
        MatchDB.match_rating != None,
    ).all()
    avg_rating = (
        sum(p.performance_rating or 3.0 for p in participations) / len(participations)
        if participations else 0
    )

    return int(
        (highlights * LC.LEGACY_HIGHLIGHT_WEIGHT)
        + (reigns * LC.LEGACY_REIGN_WEIGHT)
        + (avg_rating * LC.LEGACY_RATING_WEIGHT)
        + (years * LC.LEGACY_YEARS_WEIGHT)
    )


def hall_of_fame_ceremony(db: Session, world_id: str, game_date: str):
    """Annual Hall of Fame induction — run on April 1 each game year."""
    inducted_ids = set(
        h.wrestler_id for h in db.query(HallOfFameDB).filter(
            HallOfFameDB.world_id == world_id,
        ).all()
    )

    eligible = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == False,
        GameWrestlerDB.retirement_date != None,
    ).all()

    best = None
    best_score = 0
    for w in eligible:
        if w.id in inducted_ids:
            continue
        score = compute_legacy_score(db, w.id)
        w.legacy_score = score
        if score > best_score and score > LC.HOF_MIN_LEGACY:
            best = w
            best_score = score

    if best:
        best.is_hall_of_famer = True
        best.legacy_score = best_score
        db.add(HallOfFameDB(
            world_id=world_id,
            wrestler_id=best.id,
            inducted_date=game_date,
            legacy_score=best_score,
        ))
        db.add(GameNarrativeLogDB(
            world_id=world_id,
            game_date=game_date,
            tick=0,
            event_type="hall_of_fame",
            description=f"HALL OF FAME: {best.name} inducted! (Legacy score: {best_score})",
            involved_entities=[best.id],
            importance=10,
        ))
        return best
    return None


def apply_nostalgia_pop(wrestler: GameWrestlerDB, game_date: str,
                        last_appearance: str) -> int:
    """Apply a nostalgia popularity boost for a returning legend. Returns bonus amount."""
    if not last_appearance:
        return 0
    try:
        d1 = datetime.strptime(last_appearance, "%Y-%m-%d")
        d2 = datetime.strptime(game_date, "%Y-%m-%d")
        days_absent = (d2 - d1).days
    except (ValueError, TypeError):
        return 0

    if days_absent < LC.NOSTALGIA_MIN_DAYS_ABSENT or (wrestler.legacy_score or 0) < LC.NOSTALGIA_MIN_LEGACY:
        return 0

    pop_bonus = min(LC.NOSTALGIA_MAX_BONUS, (days_absent // LC.NOSTALGIA_DAYS_PER_UNIT) * LC.NOSTALGIA_PER_UNIT)
    wrestler.popularity = min(LC.MAX_STAT_CAP, (wrestler.popularity or 50) + pop_bonus)
    return pop_bonus


# -- Group 6: Physical Identity, Specialization & Conditioning --------------

def derive_body_type(height_cm: int, weight_kg: int) -> str:
    """Derive body_type from height and weight."""
    for threshold, btype in LC.BODY_TYPE_THRESHOLDS:
        if weight_kg < threshold:
            return btype
    return LC.BODY_TYPE_DEFAULT


def generate_physical_attributes() -> dict:
    """Generate height_cm, weight_kg, body_type for a wrestler."""
    height = random.randint(*LC.HEIGHT_RANGE)
    base_weight = int(height * LC.HEIGHT_WEIGHT_FACTOR + random.randint(*LC.WEIGHT_OFFSET_RANGE))
    weight = max(LC.WEIGHT_MIN, min(LC.WEIGHT_MAX, base_weight))
    return {
        "height_cm": height,
        "weight_kg": weight,
        "body_type": derive_body_type(height, weight),
    }


def calculate_body_modifier(attacker_weight: int, defender_weight: int) -> dict:
    """Calculate stat modifiers based on weight difference."""
    diff = (attacker_weight or 100) - (defender_weight or 100)
    if diff > LC.BODY_MOD_HEAVY_DIFF:
        return dict(LC.BODY_MOD_HEAVY)
    elif diff < -LC.BODY_MOD_HEAVY_DIFF:
        return dict(LC.BODY_MOD_LIGHT)
    return dict(LC.BODY_MOD_NEUTRAL)


def calculate_stipulation_bonus(stats: WrestlerStatsDB, stipulation: str) -> float:
    """Stipulation specialist bonus multiplier (1.0 - 1.5)."""
    if not stipulation:
        return 1.0
    attr = LC.STIPULATION_SPECIALIST_MAP.get(stipulation.lower().replace(" ", "_"))
    if not attr:
        return 1.0
    spec = getattr(stats, attr, 0) or 0
    return 1.0 + (spec / LC.STIPULATION_BONUS_DIVISOR)


def update_conditioning(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Update conditioning based on recent workload."""
    stats = _get_wrestler_stats(db, wrestler.id)
    if not stats:
        return

    try:
        week_ago = (datetime.strptime(game_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return

    matches_this_week = (
        db.query(MatchParticipantDB)
        .join(MatchDB)
        .join(ShowSegmentDB, ShowSegmentDB.match_id == MatchDB.id)
        .join(ShowDB, ShowDB.id == ShowSegmentDB.show_id)
        .filter(
            MatchParticipantDB.wrestler_id == wrestler.id,
            MatchDB.is_completed == True,
            ShowDB.game_date >= week_ago,
            ShowDB.game_date <= game_date,
        ).count()
    )

    cond = stats.conditioning_level or LC.CONDITIONING_DEFAULT
    if matches_this_week >= LC.CONDITIONING_OVERWORK_THRESHOLD:
        cond = max(LC.CONDITIONING_MIN, cond - LC.CONDITIONING_OVERWORK_PENALTY)
    elif matches_this_week == 0 and not wrestler.is_injured:
        cond = min(LC.MAX_STAT_CAP, cond + LC.CONDITIONING_REST_GAIN)
    else:
        cond = min(LC.MAX_STAT_CAP, cond + LC.CONDITIONING_WORK_GAIN)
    stats.conditioning_level = cond


def grow_specialization(stats: WrestlerStatsDB, stipulation: str):
    """Increase specialization from working a stipulation match."""
    if not stipulation:
        return
    attr = LC.STIPULATION_SPECIALIST_MAP.get(stipulation.lower().replace(" ", "_"))
    if attr:
        old = getattr(stats, attr, 0) or 0
        setattr(stats, attr, min(LC.MAX_STAT_CAP, old + LC.SPECIALIZATION_GROWTH))


# -- Group 7: Persona — Gimmick Evolution & Life Events --------------------

def tick_persona(db: Session, world_id: str, game_date: str):
    """Weekly persona tick: gimmick staleness, life events, gimmick evolution."""
    from game_service import persona_service

    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == True,
    ).all()

    for wrestler in wrestlers:
        backstory = db.query(WrestlerBackstoryDB).filter(
            WrestlerBackstoryDB.wrestler_id == wrestler.id,
        ).first()
        if not backstory:
            persona_service.generate_backstory(db, wrestler)

        gimmick = db.query(GimmickHistoryDB).filter(
            GimmickHistoryDB.wrestler_id == wrestler.id,
            GimmickHistoryDB.is_active == True,
        ).first()
        if not gimmick:
            persona_service.generate_initial_gimmick(db, wrestler, game_date)
            continue

        persona_service.tick_gimmick_staleness(db, wrestler, game_date)
        persona_service.evolve_gimmick(db, wrestler, game_date)

        if wrestler.is_npc:
            pressure = persona_service.check_repackaging_pressure(db, wrestler)
            if pressure["pressure"] > 80:
                persona_service.execute_gimmick_change(
                    db, wrestler, game_date, pressure["reason"]
                )

        persona_service.generate_life_event(db, wrestler.id, world_id, game_date)

        active_events = db.query(LifeEventDB).filter(
            LifeEventDB.wrestler_id == wrestler.id,
            LifeEventDB.is_active == True,
        ).all()
        for event in active_events:
            persona_service.process_life_event_effects(db, event)

    db.flush()
