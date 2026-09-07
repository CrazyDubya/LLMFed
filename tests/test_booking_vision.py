"""
Tests for the Promoter Vision system.

Covers: vision generation, push tiers, PPV calendar, title pipelines,
plan adaptation (injuries, departures, hot/cold acts), and career goals.
"""

import pytest
import random
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
    WrestlerPushDB,
    PPVEventDB,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_world(db, date="2026-01-15") -> WorldDB:
    w = WorldDB(id="world1", name="Test World", current_game_date=date, current_tick=10)
    db.add(w)
    db.flush()
    return w


def _create_fed(db, world_id="world1", name="TestFed", **kw) -> GameFederationDB:
    import uuid

    defaults = dict(
        id=str(uuid.uuid4())[:8],
        world_id=world_id,
        name=name,
        short_name=name[:4],
        is_npc=True,
        prestige=50,
        budget=100000,
        tv_deal_value=10000,
        home_region="East",
        style="sports",
        is_active=True,
        weekly_revenue=0,
        weekly_expenses=0,
        momentum=50,
        ai_personality={
            "booking_style": "entertainment",
            "risk_tolerance": 50,
            "talent_priority": "mixed",
        },
    )
    defaults.update(kw)
    f = GameFederationDB(**defaults)
    db.add(f)
    db.flush()
    return f


def _create_wrestler(db, world_id="world1", name="Wrestler", **kw) -> GameWrestlerDB:
    import uuid

    defaults = dict(
        id=str(uuid.uuid4())[:8],
        world_id=world_id,
        name=name,
        is_npc=True,
        alignment="face",
        popularity=50,
        condition=100,
        morale=50,
        age=28,
        weight_class="heavyweight",
        is_active=True,
        is_injured=False,
        win_streak=0,
    )
    defaults.update(kw)
    w = GameWrestlerDB(**defaults)
    db.add(w)
    db.flush()
    db.add(
        WrestlerStatsDB(
            wrestler_id=w.id,
            power=50,
            speed=50,
            technical=50,
            aerial=50,
            brawling=50,
            submission=50,
            stamina=50,
            toughness=50,
            charisma=50,
            mic_skill=50,
            psychology=50,
            selling=50,
            injury_prone=30,
        )
    )
    db.flush()
    return w


def _create_roster(db, fed, count=10):
    """Create a roster of wrestlers signed to a federation."""
    wrestlers = []
    for i in range(count):
        w = _create_wrestler(
            db, name=f"Wrestler_{i}", popularity=random.randint(20, 90)
        )
        db.add(
            ContractDB(
                world_id="world1",
                wrestler_id=w.id,
                federation_id=fed.id,
                status="active",
                salary_weekly=1000,
                start_date="2026-01-01",
            )
        )
        wrestlers.append(w)
    db.flush()
    return wrestlers


# =========================================================================
# Vision Generation
# =========================================================================


class TestVisionGeneration:
    def test_vision_created_with_push_tiers(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(db_session)
        roster = _create_roster(db_session, fed, count=10)

        champ = ChampionshipDB(
            world_id="world1",
            federation_id=fed.id,
            name="Title",
            current_holder_id=roster[0].id,
            is_active=True,
        )
        db_session.add(champ)
        db_session.flush()

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db_session, fed, roster)

        assert vision is not None
        assert vision.identity is not None
        assert vision.long_term_goal is not None
        assert vision.push_tiers is not None

        # Should have wrestlers in multiple tiers
        tiers = vision.push_tiers
        total_assigned = sum(len(v) for v in tiers.values())
        assert total_assigned == 10  # All wrestlers placed

        # Should have at least 2 main eventers
        assert len(tiers.get("main_event", [])) >= 2

    def test_vision_creates_push_records(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(db_session)
        roster = _create_roster(db_session, fed, count=8)

        from game_service.booking_vision_service import generate_federation_vision

        generate_federation_vision(db_session, fed, roster)

        push_records = (
            db_session.query(WrestlerPushDB)
            .filter(
                WrestlerPushDB.federation_id == fed.id,
            )
            .all()
        )
        assert len(push_records) == 8

    def test_vision_has_title_pipeline(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(db_session)
        roster = _create_roster(db_session, fed, count=10)

        champ = ChampionshipDB(
            world_id="world1",
            federation_id=fed.id,
            name="World Title",
            current_holder_id=roster[0].id,
            is_active=True,
        )
        db_session.add(champ)
        db_session.flush()

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db_session, fed, roster)

        assert champ.id in vision.title_pipelines
        pipeline = vision.title_pipelines[champ.id]
        assert pipeline["current_holder"] == roster[0].id
        assert len(pipeline["next_challengers"]) > 0
        assert pipeline["planned_reign_weeks"] > 0

    def test_vision_has_planned_storylines(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(db_session)
        roster = _create_roster(db_session, fed, count=10)

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db_session, fed, roster)

        assert len(vision.planned_storylines) > 0
        for sl in vision.planned_storylines:
            assert len(sl["wrestler_ids"]) >= 2
            assert sl["status"] == "penciled"

    def test_workrate_style_prioritizes_in_ring(self, db_session):
        """Workrate feds should put wrestlers with high technical/psychology on top."""
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(
            db_session,
            ai_personality={
                "booking_style": "workrate",
                "risk_tolerance": 50,
                "talent_priority": "mixed",
            },
        )

        # Create a charisma monster and a ring technician
        charisma_guy = _create_wrestler(db_session, name="Charisma", popularity=80)
        # Override stats for charisma guy
        stats = (
            db_session.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == charisma_guy.id)
            .first()
        )
        stats.charisma = 90
        stats.mic_skill = 90
        stats.technical = 30
        stats.psychology = 30
        stats.selling = 30

        tech_guy = _create_wrestler(db_session, name="Technician", popularity=40)
        stats2 = (
            db_session.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == tech_guy.id)
            .first()
        )
        stats2.technical = 90
        stats2.psychology = 90
        stats2.selling = 90
        stats2.charisma = 30

        roster = [charisma_guy, tech_guy]
        for w in roster:
            db_session.add(
                ContractDB(
                    world_id="world1",
                    wrestler_id=w.id,
                    federation_id=fed.id,
                    status="active",
                    salary_weekly=1000,
                    start_date="2026-01-01",
                )
            )
        db_session.flush()

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db_session, fed, roster)

        # Technician should be in main event for workrate fed
        main_eventers = vision.push_tiers.get("main_event", [])
        assert tech_guy.id in main_eventers


# =========================================================================
# PPV Calendar
# =========================================================================


class TestPPVCalendar:
    def test_high_prestige_gets_more_ppvs(self, db_session):
        random.seed(42)
        _create_world(db_session)
        big_fed = _create_fed(db_session, name="BigFed", prestige=80)
        small_fed = _create_fed(db_session, name="SmallFed", prestige=25)

        from game_service.ppv_calendar_service import generate_ppv_calendar

        big_ppvs = generate_ppv_calendar(db_session, big_fed, "2026-01-01")
        small_ppvs = generate_ppv_calendar(db_session, small_fed, "2026-01-01")

        assert len(big_ppvs) >= 8
        assert len(small_ppvs) <= 3
        assert len(big_ppvs) > len(small_ppvs)

    def test_crown_jewel_exists(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=60)

        from game_service.ppv_calendar_service import generate_ppv_calendar

        ppvs = generate_ppv_calendar(db_session, fed, "2026-01-01")

        crown_jewels = [p for p in ppvs if p.is_crown_jewel]
        assert len(crown_jewels) == 1
        # Crown jewel should be the last PPV
        assert crown_jewels[0] == ppvs[-1]

    def test_ppv_dates_are_spread_across_year(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=70)

        from game_service.ppv_calendar_service import generate_ppv_calendar

        ppvs = generate_ppv_calendar(db_session, fed, "2026-01-01")

        dates = [p.scheduled_date for p in ppvs]
        # Should span multiple months
        months = set(d[:7] for d in dates)
        assert len(months) >= 4  # At least 4 different months

    def test_get_next_ppv(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)

        ppv = PPVEventDB(
            world_id="world1",
            federation_id=fed.id,
            name="Test PPV",
            theme="showcase",
            scheduled_date="2026-03-15",
        )
        db_session.add(ppv)
        db_session.flush()

        from game_service.ppv_calendar_service import get_next_ppv

        result = get_next_ppv(db_session, fed.id, "2026-02-01")
        assert result is not None
        assert result.id == ppv.id

        # No PPV after the date
        result2 = get_next_ppv(db_session, fed.id, "2026-04-01")
        assert result2 is None

    def test_build_window_detection(self, db_session):
        from game_service.ppv_calendar_service import is_build_window, is_go_home_week

        assert is_build_window("2026-03-01", "2026-03-15") is True  # 2 weeks out
        assert is_build_window("2026-01-01", "2026-03-15") is False  # 10+ weeks out
        assert is_go_home_week("2026-03-14", "2026-03-15") is True  # 1 day out
        assert is_go_home_week("2026-03-01", "2026-03-15") is False  # 2 weeks out


# =========================================================================
# Vision Adaptation
# =========================================================================


class TestVisionAdaptation:
    def _setup_vision(self, db):
        _create_world(db)
        fed = _create_fed(db)
        roster = _create_roster(db, fed, count=8)

        champ = ChampionshipDB(
            world_id="world1",
            federation_id=fed.id,
            name="Title",
            current_holder_id=roster[0].id,
            is_active=True,
        )
        db.add(champ)
        db.flush()

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db, fed, roster)
        return fed, roster, vision, champ

    def test_injury_removes_from_pipeline(self, db_session):
        random.seed(42)
        fed, roster, vision, champ = self._setup_vision(db_session)

        # Injure a challenger
        challengers = vision.title_pipelines[champ.id]["next_challengers"]
        if challengers:
            injured = challengers[0]

            from game_service.booking_vision_service import adapt_vision_for_injury

            adapt_vision_for_injury(db_session, vision, injured, 8, "2026-02-01")

            db_session.refresh(vision)
            assert injured not in vision.title_pipelines[champ.id]["next_challengers"]
            assert len(vision.adaptation_log) > 0

    def test_injury_strips_champion(self, db_session):
        random.seed(42)
        fed, roster, vision, champ = self._setup_vision(db_session)

        # Set risk_tolerance low so champion gets stripped
        fed.ai_personality = {
            "booking_style": "entertainment",
            "risk_tolerance": 20,
            "talent_priority": "mixed",
        }

        champion_id = roster[0].id
        from game_service.booking_vision_service import adapt_vision_for_injury

        adapt_vision_for_injury(db_session, vision, champion_id, 10, "2026-02-01")

        db_session.refresh(vision)
        assert vision.title_pipelines[champ.id]["current_holder"] is None

    def test_departure_cleans_up_vision(self, db_session):
        random.seed(42)
        fed, roster, vision, champ = self._setup_vision(db_session)

        # Wrestler departs
        departing = roster[1].id

        from game_service.booking_vision_service import adapt_vision_for_departure

        adapt_vision_for_departure(db_session, vision, departing, "2026-02-01")

        db_session.refresh(vision)
        # Should be removed from all tiers
        all_in_tiers = []
        for tier_ids in vision.push_tiers.values():
            all_in_tiers.extend(tier_ids)
        assert departing not in all_in_tiers

        # Push record should be deleted
        push = (
            db_session.query(WrestlerPushDB)
            .filter(
                WrestlerPushDB.wrestler_id == departing,
            )
            .first()
        )
        assert push is None

    def test_hot_act_gets_promoted(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(
            db_session,
            ai_personality={
                "booking_style": "entertainment",
                "risk_tolerance": 80,  # High risk = promotes fast
                "talent_priority": "mixed",
            },
        )
        roster = _create_roster(db_session, fed, count=8)

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db_session, fed, roster)

        # Find a midcarder
        midcarders = vision.push_tiers.get("midcard", [])
        if midcarders:
            hot_wrestler_id = midcarders[0]

            from game_service.booking_vision_service import adapt_vision_for_hot_act

            adapt_vision_for_hot_act(db_session, vision, hot_wrestler_id, "2026-02-01")

            db_session.refresh(vision)
            # Should be promoted to upper_midcard
            assert hot_wrestler_id in vision.push_tiers.get("upper_midcard", [])
            assert hot_wrestler_id not in vision.push_tiers.get("midcard", [])

    def test_cold_act_gets_demoted(self, db_session):
        random.seed(42)
        _create_world(db_session)
        fed = _create_fed(
            db_session,
            ai_personality={
                "booking_style": "entertainment",
                "risk_tolerance": 80,  # High risk = demotes fast too
                "talent_priority": "mixed",
            },
        )
        roster = _create_roster(db_session, fed, count=8)

        from game_service.booking_vision_service import generate_federation_vision

        vision = generate_federation_vision(db_session, fed, roster)

        # Find an upper midcarder
        upper = vision.push_tiers.get("upper_midcard", [])
        if upper:
            cold_wrestler_id = upper[0]

            from game_service.booking_vision_service import adapt_vision_for_cold_act

            adapt_vision_for_cold_act(
                db_session, vision, cold_wrestler_id, "2026-02-01"
            )

            db_session.refresh(vision)
            assert cold_wrestler_id in vision.push_tiers.get("midcard", [])


# =========================================================================
# Push Tier Queries
# =========================================================================


class TestPushQueries:
    def test_get_push_tier(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)
        w = _create_wrestler(db_session, name="Main Eventer")

        db_session.add(
            WrestlerPushDB(
                world_id="world1",
                federation_id=fed.id,
                wrestler_id=w.id,
                push_tier="main_event",
                direction="established",
                protected=True,
            )
        )
        db_session.flush()

        from game_service.booking_vision_service import get_push_tier, is_protected

        assert get_push_tier(db_session, fed.id, w.id) == "main_event"
        assert is_protected(db_session, fed.id, w.id) is True

    def test_get_tier_roster(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)
        w1 = _create_wrestler(db_session, name="ME1")
        w2 = _create_wrestler(db_session, name="ME2")
        w3 = _create_wrestler(db_session, name="Midcarder")

        for wid, tier in [
            (w1.id, "main_event"),
            (w2.id, "main_event"),
            (w3.id, "midcard"),
        ]:
            db_session.add(
                WrestlerPushDB(
                    world_id="world1",
                    federation_id=fed.id,
                    wrestler_id=wid,
                    push_tier=tier,
                )
            )
        db_session.flush()

        from game_service.booking_vision_service import get_tier_roster

        mes = get_tier_roster(db_session, fed.id, "main_event")
        assert len(mes) == 2
        assert w1.id in mes and w2.id in mes


# =========================================================================
# Career Goals
# =========================================================================


class TestCareerGoals:
    def test_career_goals_generated(self, db_session):
        from game_service.world_service import _generate_career_goals

        young_goals = _generate_career_goals(22)
        assert len(young_goals) == 2
        assert young_goals[0] in [
            "win_first_title",
            "prove_myself",
            "make_it_to_main_event",
        ]

        prime_goals = _generate_career_goals(30)
        assert len(prime_goals) == 2

        vet_goals = _generate_career_goals(38)
        assert len(vet_goals) == 2
        assert vet_goals[0] in [
            "one_more_title_run",
            "mentor_next_generation",
            "retirement_match",
            "cement_legacy",
            "prove_doubters_wrong",
        ]
