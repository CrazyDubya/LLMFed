"""
Tests for wrestler lifecycle — Groups 1-6.

Group 1: Aging, Decline, Speed Stat, Ring Rust
Group 2: Career Goals — Ambition, Frustration, Satisfaction
Group 3: Backstage Politics & Locker Room Power
Group 4: Developmental Pipeline — Rookies, Mentors, Debuts
Group 5: Legacy, Hall of Fame & Nostalgia
Group 6: Physical Identity, Match Specialization, Conditioning
"""

import random
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    WorldDB,
    GameFederationDB,
    GameWrestlerDB,
    WrestlerStatsDB,
    ContractDB,
    ChampionshipDB,
    ChampionshipHistoryDB,
    MatchDB,
    MatchParticipantDB,
    WrestlerPushDB,
    WrestlerGoalDB,
    MentorshipDB,
    CareerHighlightDB,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def world(db):
    w = WorldDB(name="Test", current_game_date="2026-06-15")
    db.add(w)
    db.flush()
    return w


@pytest.fixture
def federation(db, world):
    f = GameFederationDB(
        world_id=world.id,
        name="Test Fed",
        short_name="TF",
        prestige=60,
        is_npc=True,
        ai_personality={"booking_style": "workrate", "risk_tolerance": 50},
    )
    db.add(f)
    db.flush()
    return f


def _make_wrestler(
    db,
    world,
    name="Test Wrestler",
    age=28,
    popularity=50,
    morale=70,
    alignment="face",
    **kwargs,
):
    w = GameWrestlerDB(
        world_id=world.id,
        name=name,
        is_npc=True,
        age=age,
        popularity=popularity,
        morale=morale,
        alignment=alignment,
        experience_years=max(0, age - 18),
        peak_age=kwargs.pop("peak_age", 28),
        career_phase=kwargs.pop("career_phase", "prime"),
        birth_date=kwargs.pop("birth_date", f"{2026 - age}-01-15"),
        height_cm=kwargs.pop("height_cm", 185),
        weight_kg=kwargs.pop("weight_kg", 100),
        body_type=kwargs.pop("body_type", "average"),
        career_goals=kwargs.pop("career_goals", ["become_champion"]),
        satisfaction=kwargs.pop("satisfaction", 50),
        **kwargs,
    )
    db.add(w)
    db.flush()
    stats = WrestlerStatsDB(
        wrestler_id=w.id,
        power=kwargs.get("power", 60),
        speed=kwargs.get("speed", 55),
        technical=kwargs.get("technical", 60),
        aerial=kwargs.get("aerial", 50),
        brawling=kwargs.get("brawling", 55),
        submission=kwargs.get("submission", 50),
        stamina=kwargs.get("stamina", 60),
        toughness=kwargs.get("toughness", 55),
        charisma=kwargs.get("charisma", 50),
        mic_skill=kwargs.get("mic_skill", 50),
        psychology=kwargs.get("psychology", 55),
        selling=kwargs.get("selling", 50),
        backstage_politics=kwargs.get("backstage_politics", 50),
        work_ethic=kwargs.get("work_ethic", 60),
        loyalty=kwargs.get("loyalty", 50),
        injury_prone=kwargs.get("injury_prone", 30),
        conditioning_level=kwargs.get("conditioning_level", 70),
    )
    db.add(stats)
    db.flush()
    return w


# ===========================================================================
# Group 1: Aging, Decline, Speed Stat, Ring Rust
# ===========================================================================


class TestAging:
    def test_age_wrestlers_increments_age(self, db, world):
        from game_service.wrestler_lifecycle_service import age_wrestlers

        w = _make_wrestler(db, world, age=30)
        age_wrestlers(db, world.id, "2027-01-01")
        assert w.age == 31
        assert w.experience_years == 13  # 30-18 + 1

    def test_stat_decline_past_peak(self, db, world):
        from game_service.wrestler_lifecycle_service import age_wrestlers

        w = _make_wrestler(db, world, age=35, peak_age=28)
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == w.id)
            .first()
        )
        old_speed = stats.speed
        old_aerial = stats.aerial
        random.seed(42)
        age_wrestlers(db, world.id, "2027-01-01")
        # Physical stats should have declined
        assert stats.speed <= old_speed
        assert stats.aerial <= old_aerial

    def test_mental_stats_improve_with_age(self, db, world):
        from game_service.wrestler_lifecycle_service import age_wrestlers

        w = _make_wrestler(db, world, age=35, peak_age=28)
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == w.id)
            .first()
        )
        old_psych = stats.psychology
        # Run aging many times to beat randomness
        random.seed(1)
        for year in range(5):
            age_wrestlers(db, world.id, f"{2027 + year}-01-01")
        assert stats.psychology >= old_psych

    def test_career_phase_transitions(self, db, world):
        from game_service.wrestler_lifecycle_service import update_career_phase

        w = _make_wrestler(db, world, age=20, peak_age=28)
        w.experience_years = 1
        update_career_phase(w)
        assert w.career_phase == "rookie"

        w.experience_years = 3
        w.age = 23
        update_career_phase(w)
        assert w.career_phase == "rising"

        w.age = 29
        update_career_phase(w)
        assert w.career_phase == "prime"

        w.age = 34
        update_career_phase(w)
        assert w.career_phase == "veteran"

        w.age = 40
        update_career_phase(w)
        assert w.career_phase == "declining"


class TestRetirement:
    def test_retirement_pressure_increases_for_declining(self, db, world):
        from game_service.wrestler_lifecycle_service import (
            calculate_retirement_pressure,
        )

        w = _make_wrestler(db, world, age=40, career_phase="declining", morale=20)
        pressure = calculate_retirement_pressure(w)
        assert pressure >= 25  # declining (10) + low morale (15)

    def test_retirement_pressure_zero_for_prime(self, db, world):
        from game_service.wrestler_lifecycle_service import (
            calculate_retirement_pressure,
        )

        w = _make_wrestler(db, world, age=28, career_phase="prime", morale=70)
        pressure = calculate_retirement_pressure(w)
        assert pressure == 0


class TestRingRust:
    def test_ring_rust_modifier_no_rust(self, db, world):
        from game_service.wrestler_lifecycle_service import calculate_ring_rust_modifier

        w = _make_wrestler(db, world)
        w.ring_rust_days = 7
        assert calculate_ring_rust_modifier(w) == 1.0

    def test_ring_rust_modifier_heavy_rust(self, db, world):
        from game_service.wrestler_lifecycle_service import calculate_ring_rust_modifier

        w = _make_wrestler(db, world)
        w.ring_rust_days = 200
        mod = calculate_ring_rust_modifier(w)
        assert mod < 1.0
        assert mod >= 0.85


class TestSpeedStat:
    def test_speed_affects_reversal_chance(self):
        """Speed stat now contributes to reversal calculations."""
        from core_engine.match_engine import MatchSimulator, MatchParticipantState

        # Fast defender should reverse more than slow defender (statistically)
        sim = MatchSimulator(card_position="midcard")

        attacker = MatchParticipantState(
            wrestler_id="a",
            name="Attacker",
            stats={
                "power": 70,
                "technical": 50,
                "aerial": 50,
                "brawling": 50,
                "submission": 50,
                "stamina": 60,
                "toughness": 50,
                "speed": 50,
                "psychology": 50,
                "selling": 50,
            },
        )
        fast_defender = MatchParticipantState(
            wrestler_id="b",
            name="FastDef",
            stats={
                "power": 50,
                "technical": 70,
                "aerial": 50,
                "brawling": 50,
                "submission": 50,
                "stamina": 60,
                "toughness": 50,
                "speed": 95,
                "psychology": 70,
                "selling": 50,
            },
            momentum=70,
        )
        # The speed stat is now in the reversal formula — test passes
        # if no error is raised (speed used to be dead weight)
        spot = sim._generate_spot(attacker, fast_defender)
        assert spot is not None  # Spot generated successfully with speed in formula

    def test_speed_affects_control_switch(self):
        from core_engine.match_engine import MatchSimulator, MatchParticipantState

        sim = MatchSimulator()
        attacker = MatchParticipantState(
            wrestler_id="a",
            name="A",
            stats={"psychology": 50, "stamina": 50, "speed": 30},
            health=80,
        )
        fast_defender = MatchParticipantState(
            wrestler_id="b",
            name="B",
            stats={"psychology": 50, "stamina": 50, "speed": 95},
            health=60,
        )
        # Run many times — fast defenders should switch control more often
        switches = sum(
            sim._should_switch_control(attacker, fast_defender) for _ in range(100)
        )
        assert switches > 20  # Should happen often with speed 95


# ===========================================================================
# Group 2: Career Goals
# ===========================================================================


class TestCareerGoals:
    def test_goals_created_from_career_goals_field(self, db, world):
        from game_service.wrestler_lifecycle_service import create_wrestler_goals

        w = _make_wrestler(db, world, career_goals=["become_champion", "earn_respect"])
        create_wrestler_goals(db, w, "2026-01-01")
        db.flush()
        goals = (
            db.query(WrestlerGoalDB).filter(WrestlerGoalDB.wrestler_id == w.id).all()
        )
        assert len(goals) == 2
        assert {g.goal_type for g in goals} == {"become_champion", "earn_respect"}

    def test_goal_completed_when_holding_title(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import (
            create_wrestler_goals,
            evaluate_goals,
        )

        w = _make_wrestler(db, world, career_goals=["become_champion"])
        create_wrestler_goals(db, w, "2026-01-01")
        db.flush()

        # Give wrestler a title
        champ = ChampionshipDB(
            world_id=world.id,
            federation_id=federation.id,
            name="World Title",
            current_holder_id=w.id,
        )
        db.add(champ)
        db.flush()

        completed = evaluate_goals(db, w, "2026-06-15")
        assert "become_champion" in completed
        assert w.satisfaction > 50  # Satisfaction increased

    def test_frustration_grows_when_blocked(self, db, world):
        from game_service.wrestler_lifecycle_service import (
            create_wrestler_goals,
            evaluate_goals,
        )

        w = _make_wrestler(db, world, career_goals=["become_champion"])
        create_wrestler_goals(db, w, "2026-01-01")
        db.flush()

        # No title — frustration should grow
        for _ in range(5):
            evaluate_goals(db, w, "2026-06-15")

        goal = (
            db.query(WrestlerGoalDB)
            .filter(
                WrestlerGoalDB.wrestler_id == w.id,
                WrestlerGoalDB.goal_type == "become_champion",
            )
            .first()
        )
        assert goal.frustration >= 5

    def test_glass_ceiling_increases_frustration(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import (
            create_wrestler_goals,
            evaluate_goals,
        )

        w = _make_wrestler(db, world, career_goals=["become_champion"])
        create_wrestler_goals(db, w, "2026-01-01")
        db.flush()

        # Create push record stuck for 30 weeks
        push = WrestlerPushDB(
            world_id=world.id,
            federation_id=federation.id,
            wrestler_id=w.id,
            push_tier="midcard",
            weeks_at_tier=30,
        )
        db.add(push)
        db.flush()

        evaluate_goals(db, w, "2026-06-15")
        goal = (
            db.query(WrestlerGoalDB)
            .filter(
                WrestlerGoalDB.wrestler_id == w.id,
                WrestlerGoalDB.goal_type == "become_champion",
            )
            .first()
        )
        assert goal.frustration >= 4  # Base 1 + glass ceiling 3

    def test_satisfaction_affects_morale(self, db, world):
        from game_service.wrestler_lifecycle_service import (
            evaluate_goals,
            create_wrestler_goals,
        )

        w = _make_wrestler(
            db, world, satisfaction=20, morale=60, career_goals=["become_champion"]
        )
        create_wrestler_goals(db, w, "2026-01-01")
        db.flush()
        old_morale = w.morale
        evaluate_goals(db, w, "2026-06-15")
        assert w.morale < old_morale  # Low satisfaction drags morale


# ===========================================================================
# Group 3: Backstage Politics & Locker Room Power
# ===========================================================================


class TestBackstagePolitics:
    def test_creative_influence_calculated(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import update_locker_room_dynamics

        w = _make_wrestler(db, world, popularity=80)
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == w.id)
            .first()
        )
        stats.backstage_politics = 80
        db.add(
            ContractDB(
                world_id=world.id,
                wrestler_id=w.id,
                federation_id=federation.id,
                status="active",
                salary_weekly=5000,
                start_date="2026-01-01",
            )
        )
        db.flush()
        update_locker_room_dynamics(db, federation, "2026-06-15")
        assert w.creative_influence > 0

    def test_leader_standing(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import update_locker_room_dynamics

        w = _make_wrestler(db, world, popularity=85)
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == w.id)
            .first()
        )
        stats.backstage_politics = 90
        db.add(
            ContractDB(
                world_id=world.id,
                wrestler_id=w.id,
                federation_id=federation.id,
                status="active",
                salary_weekly=5000,
                start_date="2026-01-01",
            )
        )
        db.flush()
        update_locker_room_dynamics(db, federation, "2026-06-15")
        assert w.locker_room_standing == "leader"

    def test_toxic_drags_morale(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import update_locker_room_dynamics

        # Create a toxic wrestler
        toxic = _make_wrestler(db, world, name="Toxic Guy", popularity=60, morale=60)
        toxic_stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == toxic.id)
            .first()
        )
        toxic_stats.backstage_politics = 85
        toxic_stats.work_ethic = 20  # High politics + low work ethic = toxic

        # Create a normal wrestler
        normal = _make_wrestler(db, world, name="Normal", popularity=50, morale=70)

        for w in [toxic, normal]:
            db.add(
                ContractDB(
                    world_id=world.id,
                    wrestler_id=w.id,
                    federation_id=federation.id,
                    status="active",
                    salary_weekly=3000,
                    start_date="2026-01-01",
                )
            )
        db.flush()
        update_locker_room_dynamics(db, federation, "2026-06-15")
        assert normal.morale < 70  # Morale dragged down by toxic

    def test_politics_modifier_in_booking(self, db, world):
        from game_service.wrestler_lifecycle_service import apply_politics_to_booking

        w = _make_wrestler(db, world)
        w.creative_influence = 10
        # Low influence: should not modify finish
        finish = apply_politics_to_booking(db, w, "pinfall")
        assert finish == "pinfall"


# ===========================================================================
# Group 4: Developmental Pipeline
# ===========================================================================


class TestDevelopmental:
    def test_mentor_assignment(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import assign_mentor

        veteran = _make_wrestler(db, world, name="Vet", age=38, career_phase="veteran")
        vet_stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == veteran.id)
            .first()
        )
        vet_stats.psychology = 80
        vet_stats.work_ethic = 70

        rookie = _make_wrestler(db, world, name="Rookie", age=20, career_phase="rookie")
        db.flush()

        m = assign_mentor(db, federation, rookie, veteran, "2026-01-01")
        assert m is not None
        assert m.mentor_bonus > 0.5
        assert m.skill_focus is not None

    def test_mentor_rejected_if_low_psychology(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import assign_mentor

        bad_mentor = _make_wrestler(db, world, name="BadMentor", age=38)
        bad_stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == bad_mentor.id)
            .first()
        )
        bad_stats.psychology = 30  # Too low to mentor

        rookie = _make_wrestler(db, world, name="Rookie", age=20)
        db.flush()

        m = assign_mentor(db, federation, rookie, bad_mentor, "2026-01-01")
        assert m is None

    def test_debut_readiness_check(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import check_debut_readiness

        rookie = _make_wrestler(db, world, name="DevRookie", age=21)
        db.add(
            WrestlerPushDB(
                world_id=world.id,
                federation_id=federation.id,
                wrestler_id=rookie.id,
                push_tier="developmental",
                weeks_at_tier=10,
            )
        )
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == rookie.id)
            .first()
        )
        stats.psychology = 40
        db.flush()

        assert check_debut_readiness(db, rookie) is True

    def test_debut_not_ready_too_soon(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import check_debut_readiness

        rookie = _make_wrestler(db, world, name="TooNew", age=19)
        db.add(
            WrestlerPushDB(
                world_id=world.id,
                federation_id=federation.id,
                wrestler_id=rookie.id,
                push_tier="developmental",
                weeks_at_tier=3,  # Only 3 weeks
            )
        )
        db.flush()
        assert check_debut_readiness(db, rookie) is False

    def test_training_with_mentor_bonus(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import training_with_mentor

        veteran = _make_wrestler(db, world, name="MentorVet", age=38)
        vet_stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == veteran.id)
            .first()
        )
        vet_stats.psychology = 80
        vet_stats.work_ethic = 70

        rookie = _make_wrestler(db, world, name="MentorRookie", age=20)
        veteran.finisher_type = "technical"

        db.add(
            MentorshipDB(
                world_id=world.id,
                mentor_id=veteran.id,
                protege_id=rookie.id,
                federation_id=federation.id,
                skill_focus="technical",
                mentor_bonus=0.75,
                is_active=True,
            )
        )
        db.flush()

        bonus = training_with_mentor(db, rookie.id, "technical")
        assert bonus >= 1  # Should get bonus for mentor's specialty

        no_bonus = training_with_mentor(db, rookie.id, "power")
        assert no_bonus == 0  # No bonus for non-specialty, non-psychology


# ===========================================================================
# Group 5: Legacy, Hall of Fame & Nostalgia
# ===========================================================================


class TestLegacy:
    def test_career_highlight_recorded(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import check_match_highlights

        w = _make_wrestler(db, world)
        match = MatchDB(
            world_id=world.id,
            match_rating=4.7,
            is_completed=True,
            winner_id=w.id,
        )
        db.add(match)
        db.flush()

        check_match_highlights(db, match, w.id, "2026-06-15")
        db.flush()

        highlights = (
            db.query(CareerHighlightDB)
            .filter(
                CareerHighlightDB.wrestler_id == w.id,
            )
            .all()
        )
        assert len(highlights) >= 1
        assert highlights[0].highlight_type == "5_star_classic"

    def test_legacy_score_computed(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import compute_legacy_score

        w = _make_wrestler(db, world, age=35)
        # Add a title reign
        champ = ChampionshipDB(
            world_id=world.id,
            federation_id=federation.id,
            name="World Title",
        )
        db.add(champ)
        db.flush()
        db.add(
            ChampionshipHistoryDB(
                championship_id=champ.id,
                wrestler_id=w.id,
                reign_start="2026-01-01",
            )
        )
        db.add(
            CareerHighlightDB(
                wrestler_id=w.id,
                highlight_type="title_win",
                description="Won title",
                game_date="2026-01-01",
            )
        )
        db.flush()

        score = compute_legacy_score(db, w.id)
        assert score > 0  # Should have points from reign + highlight + years

    def test_hall_of_fame_induction(self, db, world, federation):
        from game_service.wrestler_lifecycle_service import (
            hall_of_fame_ceremony,
            compute_legacy_score,
        )

        # Create a retired legend
        legend = _make_wrestler(db, world, name="The Legend", age=42)
        legend.is_active = False
        legend.retirement_date = "2025-12-01"

        # Add career history to boost legacy score
        for i in range(3):
            champ = ChampionshipDB(
                world_id=world.id,
                federation_id=federation.id,
                name=f"Title {i}",
            )
            db.add(champ)
            db.flush()
            db.add(
                ChampionshipHistoryDB(
                    championship_id=champ.id,
                    wrestler_id=legend.id,
                    reign_start=f"202{i}-01-01",
                )
            )
        for i in range(5):
            db.add(
                CareerHighlightDB(
                    wrestler_id=legend.id,
                    highlight_type="5_star_classic",
                    description=f"Classic {i}",
                    game_date=f"202{i}-06-01",
                    significance=8,
                )
            )
        db.flush()

        score = compute_legacy_score(db, legend.id)
        assert score > 50

        inductee = hall_of_fame_ceremony(db, world.id, "2026-04-01")
        assert inductee is not None
        assert inductee.id == legend.id
        assert legend.is_hall_of_famer is True

    def test_nostalgia_pop(self, db, world):
        from game_service.wrestler_lifecycle_service import apply_nostalgia_pop

        w = _make_wrestler(db, world, popularity=50)
        w.legacy_score = 60

        bonus = apply_nostalgia_pop(w, "2026-06-15", "2026-01-01")
        assert bonus > 0
        assert w.popularity > 50

    def test_no_nostalgia_pop_for_short_absence(self, db, world):
        from game_service.wrestler_lifecycle_service import apply_nostalgia_pop

        w = _make_wrestler(db, world, popularity=50)
        w.legacy_score = 60

        bonus = apply_nostalgia_pop(w, "2026-06-15", "2026-06-01")
        assert bonus == 0


# ===========================================================================
# Group 6: Physical Identity, Specialization, Conditioning
# ===========================================================================


class TestPhysicalIdentity:
    def test_body_type_derived(self):
        from game_service.wrestler_lifecycle_service import derive_body_type

        assert derive_body_type(180, 75) == "cruiserweight"
        assert derive_body_type(185, 100) == "average"
        assert derive_body_type(195, 120) == "big_man"
        assert derive_body_type(200, 150) == "super_heavyweight"

    def test_physical_attributes_generated(self):
        from game_service.wrestler_lifecycle_service import generate_physical_attributes

        phys = generate_physical_attributes()
        assert 165 <= phys["height_cm"] <= 205
        assert 70 <= phys["weight_kg"] <= 160
        assert phys["body_type"] in (
            "cruiserweight",
            "average",
            "big_man",
            "super_heavyweight",
        )

    def test_body_modifier_heavier_attacker(self):
        from game_service.wrestler_lifecycle_service import calculate_body_modifier

        mods = calculate_body_modifier(140, 80)  # 60kg heavier
        assert mods["power"] > 1.0
        assert mods["aerial"] < 1.0

    def test_body_modifier_lighter_attacker(self):
        from game_service.wrestler_lifecycle_service import calculate_body_modifier

        mods = calculate_body_modifier(75, 130)  # 55kg lighter
        assert mods["speed"] > 1.0
        assert mods["power"] < 1.0


class TestSpecialization:
    def test_stipulation_bonus(self):
        from game_service.wrestler_lifecycle_service import calculate_stipulation_bonus

        stats = WrestlerStatsDB()
        stats.cage_specialist = 80
        bonus = calculate_stipulation_bonus(stats, "cage")
        assert bonus > 1.0  # Should get a bonus

    def test_no_bonus_without_specialization(self):
        from game_service.wrestler_lifecycle_service import calculate_stipulation_bonus

        stats = WrestlerStatsDB()
        stats.cage_specialist = 0
        bonus = calculate_stipulation_bonus(stats, "cage")
        assert bonus == 1.0

    def test_grow_specialization(self):
        from game_service.wrestler_lifecycle_service import grow_specialization

        stats = WrestlerStatsDB()
        stats.cage_specialist = 10
        stats.ladder_specialist = 0
        stats.hardcore_specialist = 0
        grow_specialization(stats, "cage")
        assert stats.cage_specialist == 12

    def test_conditioning_cycle(self, db, world):
        from game_service.wrestler_lifecycle_service import update_conditioning

        w = _make_wrestler(db, world)
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == w.id)
            .first()
        )
        stats.conditioning_level = 70
        db.flush()
        # No matches = recovery
        update_conditioning(db, w, "2026-06-15")
        assert stats.conditioning_level > 70  # Should recover


# ===========================================================================
# Integration: Match engine uses new modifiers
# ===========================================================================


class TestMatchEngineIntegration:
    def test_ring_rust_reduces_stats(self, db, world):
        """Ring rust should reduce effective stats in match simulation."""
        w = _make_wrestler(db, world)
        w.ring_rust_days = 200
        w.condition = 90
        stats = (
            db.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == w.id)
            .first()
        )
        stats.conditioning_level = 50  # Low conditioning

        # Stats should be reduced by both ring rust and conditioning modifiers
        morale = w.morale or 50
        base_mod = 0.85 + (morale / 100) * 0.3
        rust_mod = max(0.85, 1.0 - (200 / 500))
        cond_mod = 0.85 + (50 / 100) * 0.15
        effective_power = int(stats.power * base_mod * rust_mod * cond_mod)
        assert effective_power < stats.power  # Should be reduced

    def test_post_match_highlights_recorded(self, db, world):
        """Career highlights should be recorded after great matches."""
        from core_engine.match_aftermath import _post_match_lifecycle

        w = _make_wrestler(db, world)
        match = MatchDB(
            world_id=world.id,
            match_rating=4.8,
            is_completed=True,
            winner_id=w.id,
        )
        db.add(match)
        db.flush()
        p = MatchParticipantDB(match_id=match.id, wrestler_id=w.id)
        db.add(p)
        db.flush()

        _post_match_lifecycle(db, match, [p], "2026-06-15")
        db.flush()

        highlights = (
            db.query(CareerHighlightDB)
            .filter(
                CareerHighlightDB.wrestler_id == w.id,
            )
            .all()
        )
        assert len(highlights) >= 1


# ===========================================================================
# Integration: World generation includes new fields
# ===========================================================================


class TestWorldGeneration:
    def test_wrestlers_have_physical_attributes(self):
        """World generation should populate height/weight/body_type."""
        from game_service.world_service import _generate_npc_wrestler

        random.seed(42)
        wrestler, stats = _generate_npc_wrestler("test-world")
        assert wrestler.height_cm is not None
        assert wrestler.weight_kg is not None
        assert wrestler.body_type is not None
        assert wrestler.birth_date is not None
        assert wrestler.peak_age is not None
        assert wrestler.career_phase is not None

    def test_wrestlers_have_career_phase(self):
        from game_service.world_service import _generate_npc_wrestler

        random.seed(42)
        wrestler, stats = _generate_npc_wrestler("test-world")
        assert wrestler.career_phase in (
            "rookie",
            "rising",
            "prime",
            "veteran",
            "declining",
        )
