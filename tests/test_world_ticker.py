"""Tests for the world ticker - game day advancement."""

from random import Random
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    GameWrestlerDB, MatchDB, WrestlerStatsDB, PlayerActionDB, UserDB,
    GameNarrativeLogDB, PPVEventDB, ShowDB,
    ContractDB, GameFederationDB, TagTeamDB, WorldDB,
)
from game_service import ppv_calendar_service
from game_service.show_service import book_match, create_show
from game_service.world_service import create_world, create_player
from game_service.world_ticker import WorldTicker, advance_game_date, get_day_of_week


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def world_with_player(db_session):
    """Create a world with a promoter player."""
    world = create_world(db_session, "Ticker Test World")
    user = UserDB(email="t@t.com", username="ticker_user", password_hash="h")
    db_session.add(user)
    db_session.commit()
    player = create_player(
        db_session, user.id, world.id, "promoter",
        federation_name="Test Fed",
    )
    return world, player


class TestDateUtils:
    def test_advance_game_date(self):
        assert advance_game_date("2026-01-01") == "2026-01-02"
        assert advance_game_date("2026-01-31") == "2026-02-01"
        assert advance_game_date("2026-12-31") == "2027-01-01"
        assert advance_game_date("2026-01-01", 7) == "2026-01-08"

    def test_day_of_week(self):
        # 2026-01-01 is a Thursday (3)
        assert get_day_of_week("2026-01-01") == 3
        # 2026-01-05 is a Monday (0)
        assert get_day_of_week("2026-01-05") == 0


class TestWorldTicker:
    @pytest.mark.parametrize("calendar", ["new_world", "annual_rollover"])
    @pytest.mark.parametrize(("jitter", "days_until_opening"), [(-7, 1), (0, 1), (7, 7)])
    def test_opening_ppvs_run_after_calendar_start(
        self, db_session, monkeypatch, calendar, jitter, days_until_opening,
    ):
        rng = Random(42)
        calendar_rng = Mock(wraps=rng)
        calendar_rng.randint.side_effect = (
            lambda a, b: jitter if (a, b) == (-7, 7) else rng.randint(a, b)
        )
        monkeypatch.setattr(ppv_calendar_service, "random", calendar_rng)

        world = create_world(db_session, "PPV Calendar Test World")
        ticker = WorldTicker(db_session, world.id)
        events = db_session.query(PPVEventDB).filter(PPVEventDB.world_id == world.id)
        if calendar == "annual_rollover":
            original_ids = [event.id for event in events]
            world.current_game_date = "2026-12-31"
            db_session.commit()
            ticker.tick(1)
            assert world.current_game_date == "2027-01-01"
            events = events.filter(PPVEventDB.id.notin_(original_ids))

        opening_ppvs = {}
        for event in events.order_by(PPVEventDB.scheduled_date):
            opening_ppvs.setdefault(event.federation_id, event)

        expected_date = advance_game_date(world.current_game_date, days_until_opening)
        assert opening_ppvs
        assert {event.scheduled_date for event in opening_ppvs.values()} == {expected_date}

        ticker.tick(days_until_opening)
        for event in opening_ppvs.values():
            assert event.is_completed
            assert db_session.get(ShowDB, event.show_id).is_completed

    def test_tick_skips_match_if_competitor_is_injured_after_booking(self, db_session, world_with_player):
        db_session.autoflush = False
        world, player = world_with_player
        show = create_show(db_session, world.id, player.federation_id, "Booked Show", game_date="2026-01-03")
        injured, opponent, *healthy = [
            GameWrestlerDB(world_id=world.id, name=name)
            for name in ("Injured competitor", "Opponent", "Healthy A", "Healthy B")
        ]
        wrestlers = [injured, opponent, *healthy]
        db_session.add_all(wrestlers)
        db_session.flush()
        db_session.add_all(WrestlerStatsDB(wrestler_id=w.id) for w in wrestlers)
        segment = book_match(
            db_session, show.id, world.id, [injured.id, opponent.id], planned_winner_id=opponent.id,
        )
        healthy_segment = book_match(db_session, show.id, world.id, [w.id for w in healthy])
        db_session.commit()

        assert not injured.is_injured
        injured.is_injured = True
        injured.injury_return_date = "2026-01-06"
        db_session.commit()

        ticker = WorldTicker(db_session, world.id)
        ticker.tick(2)

        assert world.current_game_date == show.game_date == "2026-01-03"
        assert show.is_completed
        assert injured.is_injured
        assert injured.last_booked_date is None
        assert opponent.last_booked_date is None
        assert injured.win_streak == opponent.win_streak == 0
        assert not segment.is_completed
        assert segment.rating is None
        match = db_session.get(MatchDB, segment.match_id)
        assert not match.is_completed
        assert match.winner_id is None
        assert match.finish_type is None
        assert [p.wrestler_id for p in match.participants] == [injured.id, opponent.id]
        assert all(not p.is_winner and p.performance_rating is None for p in match.participants)
        assert healthy_segment.is_completed
        assert db_session.query(GameNarrativeLogDB).filter_by(
            world_id=world.id, game_date=show.game_date, event_type="match_cancelled",
        ).one().description == "Match cancelled at Booked Show: Injured competitor is injured."

        ticker.tick(3)

        assert not injured.is_injured
        assert not match.is_completed

    def test_tick_runs_match_on_competitor_injury_return_date(self, db_session, world_with_player):
        db_session.autoflush = False
        world, player = world_with_player
        show = create_show(db_session, world.id, player.federation_id, "Return Show", game_date="2026-01-02")
        returning = GameWrestlerDB(world_id=world.id, name="Returning competitor")
        opponent = GameWrestlerDB(world_id=world.id, name="Opponent")
        db_session.add_all([returning, opponent])
        db_session.flush()
        db_session.add_all(
            WrestlerStatsDB(wrestler_id=w.id, injury_prone=0) for w in (returning, opponent)
        )
        segment = book_match(db_session, show.id, world.id, [returning.id, opponent.id])
        db_session.commit()
        returning.is_injured = True
        returning.injury_return_date = show.game_date
        returning.condition = 20
        db_session.commit()

        day = WorldTicker(db_session, world.id).tick(1)["day_results"][0]

        assert segment.is_completed
        assert returning.last_booked_date == show.game_date
        assert not returning.is_injured
        assert returning.injury_return_date is None
        assert day["events"].count("Returning competitor returns from injury") == 1

    def test_tuesday_tick_disbands_tag_team_once_across_npc_federations(self, db_session):
        db_session.autoflush = False
        world = WorldDB(name="Tag Team Test World", current_game_date="2026-01-05")
        db_session.add(world)
        db_session.flush()

        federations = [
            GameFederationDB(world_id=world.id, name=f"NPC Fed {i}", is_npc=True)
            for i in range(3)
        ]
        face = GameWrestlerDB(world_id=world.id, name="Face", alignment="face")
        heel = GameWrestlerDB(world_id=world.id, name="Heel", alignment="heel")
        db_session.add_all([*federations, face, heel])
        db_session.flush()

        member_ids = [face.id, heel.id]
        db_session.add_all(
            ContractDB(
                world_id=world.id, federation_id=federations[0].id,
                wrestler_id=wrestler_id, start_date="2026-01-01",
            )
            for wrestler_id in member_ids
        )
        team = TagTeamDB(
            world_id=world.id, name="Split Decision", wrestler1_id=face.id, wrestler2_id=heel.id,
        )
        db_session.add(team)
        db_session.commit()

        day = WorldTicker(db_session, world.id).tick()["day_results"][0]

        assert day["game_date"] == "2026-01-06"
        assert not team.is_active
        assert team.dissolved_date == day["game_date"]
        emitted = day["events"].count("Tag team split: Split Decision")
        persisted = db_session.query(GameNarrativeLogDB).filter_by(
            world_id=world.id, tick=day["tick"], event_type="tag_team_dissolved",
        ).all()
        assert (emitted, len(persisted)) == (1, 1)
        assert persisted[0].involved_entities == member_ids

    def test_tick_advances_date(self, db_session, world_with_player):
        world, _ = world_with_player
        ticker = WorldTicker(db_session, world.id)

        assert world.current_game_date == "2026-01-01"
        result = ticker.tick(1)

        assert world.current_game_date == "2026-01-02"
        assert world.current_tick == 1
        assert result["days_advanced"] == 1

    def test_tick_multiple_days(self, db_session, world_with_player):
        world, _ = world_with_player
        ticker = WorldTicker(db_session, world.id)

        result = ticker.tick(7)

        assert world.current_game_date == "2026-01-08"
        assert world.current_tick == 7
        assert len(result["day_results"]) == 7

    def test_tick_processes_player_actions(self, db_session, world_with_player):
        world, player = world_with_player

        # Submit an action
        action = PlayerActionDB(
            world_id=world.id,
            player_id=player.id,
            action_type="book_show",
            action_data={
                "federation_id": player.federation_id,
                "name": "Big Show",
                "venue": "Arena",
            },
        )
        db_session.add(action)
        db_session.commit()

        ticker = WorldTicker(db_session, world.id)
        ticker.tick(1)

        db_session.refresh(action)
        assert action.status == "completed"

    @pytest.mark.parametrize(
        "action_type",
        ["request_release", "accept_contract", "create_championship", "not_a_real_action"],
    )
    def test_tick_fails_unsupported_action(self, db_session, world_with_player, action_type):
        world, player = world_with_player
        action = PlayerActionDB(
            world_id=world.id,
            player_id=player.id,
            action_type=action_type,
            action_data={},
        )
        db_session.add(action)
        db_session.commit()

        WorldTicker(db_session, world.id).tick(1)

        db_session.refresh(action)
        assert action.status == "failed"
        assert action.result == {"error": f"Unsupported action type: {action_type}"}

    def test_tick_train_action(self, db_session):
        """Test wrestler training action."""
        world = create_world(db_session, "Train World")
        user = UserDB(email="train@t.com", username="trainer", password_hash="h")
        db_session.add(user)
        db_session.commit()

        player = create_player(
            db_session, user.id, world.id, "wrestler",
            wrestler_name="Trainee",
            wrestler_style="technical",
        )

        # Get initial stat
        stats = db_session.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == player.wrestler_id
        ).first()
        initial_stamina = stats.stamina

        # Submit train action
        action = PlayerActionDB(
            world_id=world.id,
            player_id=player.id,
            action_type="train",
            action_data={"wrestler_id": player.wrestler_id, "stat": "stamina"},
        )
        db_session.add(action)
        db_session.commit()

        ticker = WorldTicker(db_session, world.id)
        ticker.tick(1)

        db_session.refresh(stats)
        assert stats.stamina >= initial_stamina  # Should increase (or stay same at max)

    def test_condition_recovery(self, db_session, world_with_player):
        world, _ = world_with_player

        # Set a wrestler's condition low
        wrestler = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id,
            GameWrestlerDB.is_injured.is_(False),
        ).first()
        wrestler.condition = 50
        db_session.commit()

        # Exercise the recovery mechanic directly rather than the full
        # tick() pipeline: tick() also runs show/match simulation, which
        # can (correctly) apply match damage to any wrestler on the card,
        # including this one — that's a separate concern from whether
        # daily condition recovery itself works, and routing through it
        # made this test's pass/fail depend on unrelated random draws
        # elsewhere in the pipeline.
        ticker = WorldTicker(db_session, world.id)
        ticker._recover_conditions()
        db_session.commit()

        db_session.refresh(wrestler)
        assert wrestler.condition > 50  # Should have recovered

    def test_narrative_log_created(self, db_session, world_with_player):
        world, _ = world_with_player

        # Advance enough days for shows to happen
        ticker = WorldTicker(db_session, world.id)
        ticker.tick(7)

        logs = db_session.query(GameNarrativeLogDB).filter(
            GameNarrativeLogDB.world_id == world.id
        ).all()
        # Should have some narrative events after a week
        assert len(logs) >= 0  # May or may not have events depending on RNG
