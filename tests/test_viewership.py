"""
Tests for the viewership/fan model service.

Covers: wrestler draw, card draw, TV ratings, attendance, PPV buys,
and federation fanbase updates.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    WorldDB,
    GameFederationDB,
    GameWrestlerDB,
    WrestlerStatsDB,
    MatchDB,
    MatchParticipantDB,
    ShowDB,
    ShowSegmentDB,
    ChampionshipDB,
    WrestlerRelationshipDB,
    PromoDB,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_world(db) -> WorldDB:
    w = WorldDB(
        id="world1", name="Test World", current_game_date="2026-01-15", current_tick=10
    )
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


def _create_show_with_card(db, fed, w1, w2, show_type="weekly", **kw):
    """Create a show with one match segment featuring w1 vs w2."""
    show = ShowDB(
        world_id="world1",
        federation_id=fed.id,
        name="Test Show",
        show_type=show_type,
        capacity=kw.get("capacity", 5000),
        game_date="2026-01-15",
        is_completed=False,
    )
    db.add(show)
    db.flush()

    match = MatchDB(
        world_id="world1",
        match_type="singles",
        is_title_match=kw.get("is_title_match", False),
        championship_id=kw.get("championship_id"),
        winner_id=w1.id,
        finish_type="pinfall",
        match_rating=3.5,
        crowd_heat=60,
        is_completed=True,
    )
    db.add(match)
    db.flush()
    db.add(
        MatchParticipantDB(
            match_id=match.id, wrestler_id=w1.id, role="competitor", is_winner=True
        )
    )
    db.add(
        MatchParticipantDB(
            match_id=match.id, wrestler_id=w2.id, role="competitor", is_winner=False
        )
    )
    db.flush()

    seg = ShowSegmentDB(
        show_id=show.id,
        position=1,
        segment_type="match",
        match_id=match.id,
    )
    db.add(seg)
    db.flush()

    return show, match


# =========================================================================
# Wrestler Draw Rating
# =========================================================================


class TestWrestlerDraw:
    def test_base_draw_equals_popularity(self, db_session):
        _create_world(db_session)
        w = _create_wrestler(db_session, name="Star", popularity=75)

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w.id)
        assert draw == 75.0

    def test_title_bonus(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)
        w = _create_wrestler(db_session, name="Champ", popularity=50)

        # Give them a title
        champ = ChampionshipDB(
            world_id="world1",
            federation_id=fed.id,
            name="World Title",
            current_holder_id=w.id,
            is_active=True,
        )
        db_session.add(champ)
        db_session.flush()

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w.id)
        assert draw == 60.0  # 50 + 10 for title

    def test_win_streak_bonus(self, db_session):
        _create_world(db_session)
        w = _create_wrestler(db_session, name="Streak", popularity=50, win_streak=4)

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w.id)
        assert draw == 58.0  # 50 + min(4*2, 10) = 58

    def test_win_streak_capped(self, db_session):
        _create_world(db_session)
        w = _create_wrestler(
            db_session, name="Undefeated", popularity=50, win_streak=20
        )

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w.id)
        assert draw == 60.0  # 50 + 10 (cap)

    def test_loss_streak_penalty(self, db_session):
        _create_world(db_session)
        w = _create_wrestler(db_session, name="Jobber", popularity=50, win_streak=-3)

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w.id)
        assert draw == 41.0  # 50 + (-3 * 3) = 41

    def test_rivalry_heat_bonus(self, db_session):
        _create_world(db_session)
        w1 = _create_wrestler(db_session, name="Face", popularity=50)
        w2 = _create_wrestler(db_session, name="Heel", popularity=50)

        w1_id, w2_id = sorted([w1.id, w2.id])
        db_session.add(
            WrestlerRelationshipDB(
                world_id="world1",
                wrestler1_id=w1_id,
                wrestler2_id=w2_id,
                matches_together=5,
                total_rating=20.0,
                chemistry_score=4.0,
                rivalry_heat=60,
            )
        )
        db_session.flush()

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w1.id)
        assert draw == 55.0  # 50 + 5 for high rivalry heat

    def test_draw_clamped_to_100(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)
        w = _create_wrestler(db_session, name="Megastar", popularity=95, win_streak=5)
        # Add title
        db_session.add(
            ChampionshipDB(
                world_id="world1",
                federation_id=fed.id,
                name="Title",
                current_holder_id=w.id,
                is_active=True,
            )
        )
        db_session.flush()

        from game_service.viewership_service import calculate_wrestler_draw

        draw = calculate_wrestler_draw(db_session, w.id)
        assert draw == 100.0  # 95 + 10 + 10 = 115, clamped to 100


# =========================================================================
# Card Draw
# =========================================================================


class TestCardDraw:
    def test_card_draw_from_match(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)
        w1 = _create_wrestler(db_session, name="W1", popularity=60)
        w2 = _create_wrestler(db_session, name="W2", popularity=40)
        show, _ = _create_show_with_card(db_session, fed, w1, w2)

        from game_service.viewership_service import calculate_card_draw

        draw = calculate_card_draw(db_session, show)
        assert draw > 0
        # Single match = main event, so both wrestlers weighted 2x
        # Expected: avg of (60*2, 40*2) = avg(120, 80) = 100, clamped to 100
        assert draw == 100.0

    def test_empty_show_returns_zero(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session)
        show = ShowDB(
            world_id="world1",
            federation_id=fed.id,
            name="Empty",
            show_type="weekly",
            capacity=5000,
            game_date="2026-01-15",
        )
        db_session.add(show)
        db_session.flush()

        from game_service.viewership_service import calculate_card_draw

        draw = calculate_card_draw(db_session, show)
        assert draw == 0.0


# =========================================================================
# TV Rating
# =========================================================================


class TestTVRating:
    def test_tv_rating_is_deterministic_range(self, db_session):
        """TV rating should be in a reasonable range for average fed."""
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=50, momentum=50)
        w1 = _create_wrestler(db_session, name="W1", popularity=50)
        w2 = _create_wrestler(db_session, name="W2", popularity=50)
        show, _ = _create_show_with_card(db_session, fed, w1, w2)

        from game_service.viewership_service import calculate_tv_rating

        rating = calculate_tv_rating(db_session, show, fed)

        # 50 prestige → base ~1.43, card + momentum + trend should land ~1.5-2.5
        assert 0.5 < rating < 4.0

    def test_high_prestige_gets_higher_rating(self, db_session):
        _create_world(db_session)
        low_fed = _create_fed(db_session, name="LowFed", prestige=20, momentum=50)
        high_fed = _create_fed(db_session, name="HighFed", prestige=90, momentum=50)

        w1 = _create_wrestler(db_session, name="W1", popularity=50)
        w2 = _create_wrestler(db_session, name="W2", popularity=50)

        show_low, _ = _create_show_with_card(db_session, low_fed, w1, w2)
        show_high, _ = _create_show_with_card(db_session, high_fed, w1, w2)

        from game_service.viewership_service import calculate_tv_rating

        # Run multiple times and average to reduce variance impact
        import random

        random.seed(42)
        rating_low = calculate_tv_rating(db_session, show_low, low_fed)
        random.seed(42)
        rating_high = calculate_tv_rating(db_session, show_high, high_fed)

        assert rating_high > rating_low


# =========================================================================
# Attendance
# =========================================================================


class TestAttendance:
    def test_attendance_within_capacity(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=50, momentum=50)
        w1 = _create_wrestler(db_session, name="W1", popularity=50)
        w2 = _create_wrestler(db_session, name="W2", popularity=50)
        show, _ = _create_show_with_card(db_session, fed, w1, w2, capacity=10000)

        from game_service.viewership_service import calculate_attendance

        attendance, ticket_price, gate = calculate_attendance(
            db_session, show, fed, 50.0
        )

        assert 0 < attendance <= 10000
        assert ticket_price > 0
        assert gate == round(attendance * ticket_price, 2)

    def test_ppv_draws_more(self, db_session):
        """PPV shows should have higher fill rate than weekly shows."""
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=50, momentum=50)
        w1 = _create_wrestler(db_session, name="W1", popularity=50)
        w2 = _create_wrestler(db_session, name="W2", popularity=50)

        show_weekly, _ = _create_show_with_card(
            db_session, fed, w1, w2, show_type="weekly", capacity=5000
        )
        show_ppv, _ = _create_show_with_card(
            db_session, fed, w1, w2, show_type="ppv", capacity=5000
        )

        import random
        from game_service.viewership_service import calculate_attendance

        random.seed(42)
        att_weekly, _, _ = calculate_attendance(db_session, show_weekly, fed, 50.0)
        random.seed(42)
        att_ppv, _, _ = calculate_attendance(db_session, show_ppv, fed, 50.0)

        assert att_ppv > att_weekly


# =========================================================================
# PPV Buys
# =========================================================================


class TestPPVBuys:
    def test_ppv_buys_positive(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=50, momentum=50)
        w1 = _create_wrestler(db_session, name="W1", popularity=60)
        w2 = _create_wrestler(db_session, name="W2", popularity=60)
        show, _ = _create_show_with_card(db_session, fed, w1, w2, show_type="ppv")

        from game_service.viewership_service import calculate_ppv_buys

        buys = calculate_ppv_buys(db_session, show, fed, 60.0)

        assert buys >= 1000

    def test_high_prestige_more_buys(self, db_session):
        _create_world(db_session)
        low_fed = _create_fed(db_session, name="Low", prestige=20, momentum=50)
        high_fed = _create_fed(db_session, name="High", prestige=80, momentum=50)

        w1 = _create_wrestler(db_session, name="W1", popularity=50)
        w2 = _create_wrestler(db_session, name="W2", popularity=50)

        show_low, _ = _create_show_with_card(
            db_session, low_fed, w1, w2, show_type="ppv"
        )
        show_high, _ = _create_show_with_card(
            db_session, high_fed, w1, w2, show_type="ppv"
        )

        import random
        from game_service.viewership_service import calculate_ppv_buys

        random.seed(42)
        buys_low = calculate_ppv_buys(db_session, show_low, low_fed, 50.0)
        random.seed(42)
        buys_high = calculate_ppv_buys(db_session, show_high, high_fed, 50.0)

        assert buys_high > buys_low


# =========================================================================
# Federation Fanbase Update
# =========================================================================


class TestFanbaseUpdate:
    def test_great_show_increases_prestige(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=50)
        show = ShowDB(
            world_id="world1",
            federation_id=fed.id,
            name="Great Show",
            show_type="weekly",
            capacity=5000,
            game_date="2026-01-15",
            is_completed=True,
            overall_rating=4.5,
            attendance=4500,  # 90% capacity
        )
        db_session.add(show)
        db_session.flush()

        from game_service.viewership_service import update_federation_fanbase

        update_federation_fanbase(db_session, fed, show)

        assert fed.prestige > 50

    def test_poor_show_decreases_prestige(self, db_session):
        _create_world(db_session)
        fed = _create_fed(db_session, prestige=50)
        show = ShowDB(
            world_id="world1",
            federation_id=fed.id,
            name="Bad Show",
            show_type="weekly",
            capacity=5000,
            game_date="2026-01-15",
            is_completed=True,
            overall_rating=1.5,
            attendance=1000,
        )
        db_session.add(show)
        db_session.flush()

        from game_service.viewership_service import update_federation_fanbase

        update_federation_fanbase(db_session, fed, show)

        assert fed.prestige < 50


# =========================================================================
# Promo Segment Fix
# =========================================================================


class TestPromoBooking:
    def test_promo_segment_creates_promo_record(self, db_session):
        """book_promo_segment with wrestler_id should create a PromoDB."""
        _create_world(db_session)
        fed = _create_fed(db_session)
        w = _create_wrestler(db_session, name="Talker", popularity=70)
        show = ShowDB(
            world_id="world1",
            federation_id=fed.id,
            name="Show",
            show_type="weekly",
            capacity=5000,
            game_date="2026-01-15",
        )
        db_session.add(show)
        db_session.flush()

        from game_service.show_service import book_promo_segment

        seg = book_promo_segment(
            db_session,
            show.id,
            description="Talker addresses the crowd",
            wrestler_id=w.id,
            world_id="world1",
            game_date="2026-01-15",
        )

        assert seg.promo_id is not None
        promo = db_session.query(PromoDB).filter(PromoDB.id == seg.promo_id).first()
        assert promo is not None
        assert promo.wrestler_id == w.id

    def test_promo_segment_without_wrestler_has_no_promo(self, db_session):
        """book_promo_segment without wrestler_id should not create PromoDB."""
        _create_world(db_session)
        fed = _create_fed(db_session)
        show = ShowDB(
            world_id="world1",
            federation_id=fed.id,
            name="Show",
            show_type="weekly",
            capacity=5000,
            game_date="2026-01-15",
        )
        db_session.add(show)
        db_session.flush()

        from game_service.show_service import book_promo_segment

        seg = book_promo_segment(db_session, show.id, description="Generic segment")

        assert seg.promo_id is None
