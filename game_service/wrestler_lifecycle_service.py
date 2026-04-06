"""
Wrestler Lifecycle Service — Groups 1-6

Handles: aging & decline, career goals, backstage politics,
developmental pipeline, legacy/Hall of Fame, physical identity & conditioning.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB, WrestlerStatsDB, GameFederationDB, ContractDB,
    ChampionshipDB, ChampionshipHistoryDB, MatchParticipantDB, MatchDB,
    ShowDB, ShowSegmentDB, WrestlerPushDB, BookingVisionDB,
    GameNarrativeLogDB, WrestlerHistoryDB,
    WrestlerGoalDB, MentorshipDB, CareerHighlightDB, HallOfFameDB,
    GimmickHistoryDB, WrestlerBackstoryDB, LifeEventDB,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Group 1: Aging, Physical Decline & Career Arc
# ---------------------------------------------------------------------------

def update_career_phase(wrestler: GameWrestlerDB):
    """Derive career phase from age and peak_age."""
    age = wrestler.age or 25
    peak = wrestler.peak_age or 28
    exp = wrestler.experience_years or 0

    if exp < 2:
        wrestler.career_phase = "rookie"
    elif age < peak - 2:
        wrestler.career_phase = "rising"
    elif age < peak + 4:
        wrestler.career_phase = "prime"
    elif age < peak + 8:
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

        # Physical stat decline past peak
        peak = w.peak_age or 28
        if w.age > peak:
            stats = db.query(WrestlerStatsDB).filter(
                WrestlerStatsDB.wrestler_id == w.id
            ).first()
            if not stats:
                continue

            years_past = w.age - peak
            decline = min(years_past, 5)  # Max 5 pts/year decline

            # Physical stats decay first
            for attr in ("speed", "aerial", "stamina"):
                old = getattr(stats, attr, 50)
                setattr(stats, attr, max(5, old - random.randint(1, decline)))

            # Power/toughness decay later
            if years_past > 3:
                for attr in ("power", "toughness"):
                    old = getattr(stats, attr, 50)
                    setattr(stats, attr, max(5, old - random.randint(0, decline - 1)))

            # Mental stats IMPROVE with age
            for attr in ("psychology", "selling"):
                old = getattr(stats, attr, 50)
                setattr(stats, attr, min(100, old + random.randint(0, 2)))


def calculate_retirement_pressure(wrestler: GameWrestlerDB) -> int:
    """Calculate how likely a wrestler is to retire (replaces flat 1% random)."""
    pressure = 0
    phase = wrestler.career_phase or "prime"

    if phase == "declining":
        pressure += 10
    elif phase == "veteran":
        pressure += 3

    if (wrestler.morale or 50) < 30:
        pressure += 15

    if wrestler.is_injured and (wrestler.age or 25) > 35:
        pressure += 20

    if (wrestler.popularity or 50) < 20 and (wrestler.age or 25) > 36:
        pressure += 10

    if (wrestler.age or 25) > 42:
        pressure += 15

    return pressure


def calculate_ring_rust_modifier(wrestler: GameWrestlerDB) -> float:
    """Ring rust modifier for match engine (0.85 - 1.0)."""
    rust = wrestler.ring_rust_days or 0
    if rust <= 14:
        return 1.0
    return max(0.85, 1.0 - (rust / 500))


# ---------------------------------------------------------------------------
# Group 2: Career Goals
# ---------------------------------------------------------------------------

def create_wrestler_goals(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Create structured goal records from the wrestler's career_goals JSON."""
    goals = wrestler.career_goals or []
    for goal_type in goals:
        existing = db.query(WrestlerGoalDB).filter(
            WrestlerGoalDB.wrestler_id == wrestler.id,
            WrestlerGoalDB.goal_type == goal_type,
            WrestlerGoalDB.status == "active",
        ).first()
        if not existing:
            db.add(WrestlerGoalDB(
                wrestler_id=wrestler.id,
                goal_type=goal_type,
                set_date=game_date,
            ))


def evaluate_goals(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Check progress on all active goals. Returns list of completed goal types."""
    active = db.query(WrestlerGoalDB).filter(
        WrestlerGoalDB.wrestler_id == wrestler.id,
        WrestlerGoalDB.status == "active",
    ).all()

    completed = []
    for goal in active:
        if _check_goal_completed(db, wrestler, goal):
            goal.status = "completed"
            goal.completed_date = game_date
            completed.append(goal.goal_type)

            wrestler.morale = min(100, (wrestler.morale or 50) + 10)
            wrestler.satisfaction = min(100, (wrestler.satisfaction or 50) + 15)

            db.add(WrestlerHistoryDB(
                wrestler_id=wrestler.id,
                game_date=game_date,
                event_type="goal_completed",
                description=f"Achieved career goal: {goal.goal_type}",
            ))
        else:
            # Frustration grows when stuck
            goal.frustration = min(100, (goal.frustration or 0) + 1)

            if goal.frustration > 80:
                wrestler.morale = max(0, (wrestler.morale or 50) - 3)
                # Frustrated faces drift heel
                if wrestler.alignment == "face" and goal.frustration > 90:
                    wrestler.alignment_momentum = (wrestler.alignment_momentum or 0) - 5

    # Glass ceiling detection
    push = db.query(WrestlerPushDB).filter(
        WrestlerPushDB.wrestler_id == wrestler.id,
    ).first()
    if push and (push.weeks_at_tier or 0) > 26:
        title_goals = [g for g in active if g.goal_type in (
            "win_title", "become_champion", "win_first_title",
            "main_event_ppv", "one_more_title_run",
        )]
        for g in title_goals:
            g.frustration = min(100, (g.frustration or 0) + 3)

    # Satisfaction influences morale
    sat = wrestler.satisfaction or 50
    if sat < 30:
        wrestler.morale = max(0, (wrestler.morale or 50) - 2)
    elif sat > 70:
        wrestler.morale = min(100, (wrestler.morale or 50) + 1)

    return completed


def _check_goal_completed(db: Session, wrestler: GameWrestlerDB, goal: WrestlerGoalDB) -> bool:
    """Check if a specific goal has been achieved."""
    gt = goal.goal_type

    if gt in ("win_title", "become_champion", "win_first_title", "one_more_title_run"):
        # Check if wrestler currently holds any title
        champ = db.query(ChampionshipDB).filter(
            ChampionshipDB.current_holder_id == wrestler.id,
        ).first()
        return champ is not None

    if gt == "main_event_ppv":
        # Check if wrestler main evented a PPV show
        ppv_main = db.query(MatchParticipantDB).join(MatchDB).join(ShowSegmentDB).join(ShowDB).filter(
            MatchParticipantDB.wrestler_id == wrestler.id,
            ShowDB.show_type == "ppv",
            MatchDB.is_completed == True,
        ).first()
        return ppv_main is not None

    if gt in ("have_5_star_match", "5_star_match"):
        best = db.query(MatchParticipantDB).join(MatchDB).filter(
            MatchParticipantDB.wrestler_id == wrestler.id,
            MatchDB.match_rating >= 4.8,
        ).first()
        return best is not None

    if gt == "defeat_rival":
        if goal.target_entity_id:
            win = db.query(MatchParticipantDB).join(MatchDB).filter(
                MatchParticipantDB.wrestler_id == wrestler.id,
                MatchParticipantDB.is_winner == True,
                MatchDB.winner_id == wrestler.id,
            ).first()
            return win is not None
        return False

    if gt == "prove_myself":
        return (wrestler.popularity or 0) >= 50

    if gt in ("build_legacy", "cement_legacy"):
        return (wrestler.legacy_score or 0) >= 50

    if gt == "become_top_draw":
        return (wrestler.draw_rating or 0) >= 80

    if gt in ("earn_respect", "prove_doubters_wrong"):
        return (wrestler.popularity or 0) >= 60 and (wrestler.morale or 0) >= 60

    if gt == "make_it_to_main_event":
        push = db.query(WrestlerPushDB).filter(
            WrestlerPushDB.wrestler_id == wrestler.id,
            WrestlerPushDB.push_tier == "main_event",
        ).first()
        return push is not None

    if gt == "headline_biggest_show":
        return (wrestler.popularity or 0) >= 75

    return False


# ---------------------------------------------------------------------------
# Group 3: Backstage Politics & Locker Room Power
# ---------------------------------------------------------------------------

def update_locker_room_dynamics(db: Session, federation: GameFederationDB, game_date: str):
    """Weekly locker room standing/influence calculation and morale contagion."""
    contracts = db.query(ContractDB).filter(
        ContractDB.federation_id == federation.id,
        ContractDB.status == "active",
    ).all()
    wrestler_ids = [c.wrestler_id for c in contracts]
    if not wrestler_ids:
        return

    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id.in_(wrestler_ids),
        GameWrestlerDB.is_active == True,
    ).all()

    leaders = []
    toxic_count = 0

    for w in wrestlers:
        stats = db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == w.id
        ).first()
        if not stats:
            continue

        politics = stats.backstage_politics or 50
        tenure = min((w.experience_years or 0) * 2, 20)
        pop = (w.popularity or 50) // 5
        w.creative_influence = min(100, politics + tenure + pop)

        work = stats.work_ethic or 50
        if politics > 80 and (w.popularity or 0) > 70:
            w.locker_room_standing = "leader"
            leaders.append(w)
        elif politics > 60 and work > 60:
            w.locker_room_standing = "respected"
        elif politics < 30 and work < 40:
            w.locker_room_standing = "disliked"
        elif politics > 70 and work < 30:
            w.locker_room_standing = "toxic"
            toxic_count += 1
        else:
            w.locker_room_standing = "neutral"

    # Morale contagion
    if leaders:
        avg_leader_morale = sum(l.morale or 50 for l in leaders) / len(leaders)
        shift = int((avg_leader_morale - 50) / 20)  # -2 to +2
        for w in wrestlers:
            if w not in leaders and shift != 0:
                w.morale = max(0, min(100, (w.morale or 50) + shift))

    if toxic_count > 0:
        for w in wrestlers:
            if (w.locker_room_standing or "neutral") != "toxic":
                w.morale = max(0, (w.morale or 50) - toxic_count)


def apply_politics_to_booking(db: Session, wrestler: GameWrestlerDB,
                              planned_finish: str) -> str:
    """Creative control: high-influence veterans may refuse clean losses.
    Returns potentially modified finish type."""
    influence = wrestler.creative_influence or 0
    if influence > 75 and planned_finish in ("pinfall", "submission"):
        if random.random() < influence / 200:
            return random.choice(["count_out", "disqualification"])
    return planned_finish


# ---------------------------------------------------------------------------
# Group 4: Developmental Pipeline
# ---------------------------------------------------------------------------

def assign_mentor(db: Session, federation: GameFederationDB,
                  protege: GameWrestlerDB, mentor: GameWrestlerDB,
                  game_date: str) -> Optional[MentorshipDB]:
    """Assign a veteran mentor to a young wrestler."""
    mentor_stats = db.query(WrestlerStatsDB).filter(
        WrestlerStatsDB.wrestler_id == mentor.id
    ).first()
    if not mentor_stats or (mentor_stats.psychology or 0) < 50:
        return None

    bonus = ((mentor_stats.psychology or 50) + (mentor_stats.work_ethic or 50)) / 200
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

    # Find rookies without mentors
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

    # Find available veterans
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
    if not push or (push.weeks_at_tier or 0) < 8:
        return False

    stats = db.query(WrestlerStatsDB).filter(
        WrestlerStatsDB.wrestler_id == wrestler.id
    ).first()
    if not stats:
        return False

    avg_ring = (
        (stats.power or 50) + (stats.technical or 50) +
        (stats.aerial or 50) + (stats.brawling or 50)
    ) / 4

    return avg_ring > 45 and (stats.psychology or 0) > 35


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
    # Mentor's specialty gives extra bonus
    if stat_name == mentorship.skill_focus:
        bonus = max(1, int(mentorship.mentor_bonus * 2))
    elif stat_name == "psychology":
        bonus = 1  # Proteges always learn psychology faster

    # Small chance mentor's psychology improves too (teaching deepens understanding)
    if random.random() < 0.1:
        mentor_stats = db.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == mentorship.mentor_id
        ).first()
        if mentor_stats and (mentor_stats.psychology or 0) < 100:
            mentor_stats.psychology = min(100, (mentor_stats.psychology or 50) + 1)

    return bonus


# ---------------------------------------------------------------------------
# Group 5: Legacy, Hall of Fame & Nostalgia
# ---------------------------------------------------------------------------

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

    if rating >= 4.5:
        record_career_highlight(
            db, wrestler_id, "5_star_classic",
            f"A {rating}-star classic",
            game_date, significance=min(10, int(rating * 2)),
            match_id=match.id,
        )

    # First title win
    if match.is_title_match and match.winner_id == wrestler_id:
        prev_reigns = db.query(ChampionshipHistoryDB).filter(
            ChampionshipHistoryDB.wrestler_id == wrestler_id,
        ).count()
        if prev_reigns <= 1:  # This is the first reign
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

    # Average match rating
    participations = db.query(MatchParticipantDB).join(MatchDB).filter(
        MatchParticipantDB.wrestler_id == wrestler_id,
        MatchDB.is_completed == True,
        MatchDB.match_rating != None,
    ).all()
    if participations:
        avg_rating = sum(
            p.performance_rating or 3.0 for p in participations
        ) / len(participations)
    else:
        avg_rating = 0

    return int((highlights * 5) + (reigns * 10) + (avg_rating * 8) + (years * 2))


def hall_of_fame_ceremony(db: Session, world_id: str, game_date: str):
    """Annual Hall of Fame induction — run on April 1 each game year."""
    # Find eligible: retired, not inducted, legacy > 50
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
        if score > best_score and score > 50:
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

    if days_absent < 90 or (wrestler.legacy_score or 0) < 30:
        return 0

    pop_bonus = min(30, (days_absent // 30) * 5)
    wrestler.popularity = min(100, (wrestler.popularity or 50) + pop_bonus)
    return pop_bonus


# ---------------------------------------------------------------------------
# Group 6: Physical Identity, Specialization & Conditioning
# ---------------------------------------------------------------------------

def derive_body_type(height_cm: int, weight_kg: int) -> str:
    """Derive body_type from height and weight."""
    bmi_like = weight_kg / (height_cm / 100) ** 2
    if weight_kg < 85:
        return "cruiserweight"
    elif weight_kg < 110:
        return "average"
    elif weight_kg < 140:
        return "big_man"
    else:
        return "super_heavyweight"


def generate_physical_attributes() -> dict:
    """Generate height_cm, weight_kg, body_type for a wrestler."""
    height = random.randint(165, 205)
    # Weight correlates loosely with height
    base_weight = int(height * 0.5 + random.randint(-10, 20))
    weight = max(70, min(160, base_weight))
    return {
        "height_cm": height,
        "weight_kg": weight,
        "body_type": derive_body_type(height, weight),
    }


def calculate_body_modifier(attacker_weight: int, defender_weight: int) -> dict:
    """Calculate stat modifiers based on weight difference."""
    diff = (attacker_weight or 100) - (defender_weight or 100)
    mods = {"power": 1.0, "speed": 1.0, "aerial": 1.0}

    if diff > 30:  # Much heavier
        mods["power"] = 1.15
        mods["aerial"] = 0.85
    elif diff < -30:  # Much lighter
        mods["speed"] = 1.15
        mods["power"] = 0.85
        mods["aerial"] = 1.10

    return mods


def calculate_stipulation_bonus(stats: WrestlerStatsDB, stipulation: str) -> float:
    """Stipulation specialist bonus multiplier (1.0 - 1.5)."""
    if not stipulation:
        return 1.0

    mapping = {
        "cage": stats.cage_specialist or 0,
        "hell_in_a_cell": stats.cage_specialist or 0,
        "ladder": stats.ladder_specialist or 0,
        "tables": stats.hardcore_specialist or 0,
        "no_dq": stats.hardcore_specialist or 0,
        "falls_count_anywhere": stats.hardcore_specialist or 0,
        "extreme_rules": stats.hardcore_specialist or 0,
        "street_fight": stats.hardcore_specialist or 0,
    }
    spec = mapping.get(stipulation.lower().replace(" ", "_"), 0)
    return 1.0 + (spec / 200)


def update_conditioning(db: Session, wrestler: GameWrestlerDB, game_date: str):
    """Update conditioning based on recent workload."""
    stats = db.query(WrestlerStatsDB).filter(
        WrestlerStatsDB.wrestler_id == wrestler.id
    ).first()
    if not stats:
        return

    # Count matches in last 7 days
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

    cond = stats.conditioning_level or 70
    if matches_this_week >= 3:
        cond = max(20, cond - 5)
    elif matches_this_week == 0 and not wrestler.is_injured:
        cond = min(100, cond + 3)
    else:
        cond = min(100, cond + 1)
    stats.conditioning_level = cond


def grow_specialization(stats: WrestlerStatsDB, stipulation: str):
    """Increase specialization from working a stipulation match."""
    if not stipulation:
        return

    mapping = {
        "cage": "cage_specialist",
        "hell_in_a_cell": "cage_specialist",
        "ladder": "ladder_specialist",
        "tables": "hardcore_specialist",
        "no_dq": "hardcore_specialist",
        "extreme_rules": "hardcore_specialist",
        "street_fight": "hardcore_specialist",
    }
    attr = mapping.get(stipulation.lower().replace(" ", "_"))
    if attr:
        old = getattr(stats, attr, 0) or 0
        setattr(stats, attr, min(100, old + 2))


# ---------------------------------------------------------------------------
# Group 7: Persona — Gimmick Evolution & Life Events
# ---------------------------------------------------------------------------

def tick_persona(db: Session, world_id: str, game_date: str):
    """Weekly persona tick: gimmick staleness, life events, gimmick evolution.

    Called from world ticker on Fridays.
    """
    from game_service import persona_service

    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == True,
    ).all()

    for wrestler in wrestlers:
        # Ensure persona data exists (migration for pre-existing wrestlers)
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

        # Tick gimmick staleness
        persona_service.tick_gimmick_staleness(db, wrestler, game_date)

        # Evolve gimmick depth/fan investment based on recent activity
        persona_service.evolve_gimmick(db, wrestler, game_date)

        # Check for repackaging pressure (NPC only)
        if wrestler.is_npc:
            pressure = persona_service.check_repackaging_pressure(db, wrestler)
            if pressure["pressure"] > 80:
                persona_service.execute_gimmick_change(
                    db, wrestler, game_date, pressure["reason"]
                )

        # Life event roll (~3% per wrestler per week)
        persona_service.generate_life_event(db, wrestler.id, world_id, game_date)

        # Process effects of active life events
        active_events = db.query(LifeEventDB).filter(
            LifeEventDB.wrestler_id == wrestler.id,
            LifeEventDB.is_active == True,
        ).all()
        for event in active_events:
            persona_service.process_life_event_effects(db, event)

    db.flush()
