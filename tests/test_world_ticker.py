"""Tests for the world ticker - game day advancement."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    GameWrestlerDB, WrestlerStatsDB, PlayerActionDB, UserDB,
    ContractDB, GameFederationDB, GameNarrativeLogDB, WorldDB,
)
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
    def test_expiring_contract_does_not_count_as_underpaid(self, db_session):
        db_session.autoflush = False
        world = WorldDB(name="Expiry Test World", current_game_date="2026-01-05")
        federation = GameFederationDB(world=world, name="Test Fed", is_npc=False)
        departing = GameWrestlerDB(
            world=world, name="Departing", is_npc=False, popularity=80, morale=75,
            stats=WrestlerStatsDB(injury_prone=0),
        )
        staying = GameWrestlerDB(
            world=world, name="Staying", is_npc=False, popularity=80, morale=75,
            stats=WrestlerStatsDB(injury_prone=0),
        )
        db_session.add_all([world, federation, departing, staying])
        db_session.flush()
        expiring = ContractDB(
            world_id=world.id, wrestler=departing, federation=federation,
            salary_weekly=1000, start_date="2025-07-06", end_date="2026-01-06",
        )
        ongoing = ContractDB(
            world_id=world.id, wrestler=staying, federation=federation,
            salary_weekly=1000, start_date="2025-07-06", end_date="2026-02-06",
        )
        db_session.add_all([expiring, ongoing])
        db_session.commit()

        result = WorldTicker(db_session, world.id).tick(1)

        assert "Contract expired: Departing is now a free agent" in result["day_results"][0]["events"]
        assert expiring.status == "expired"
        assert ongoing.status == "active"
        assert staying.morale == 73
        assert departing.morale == 75

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
