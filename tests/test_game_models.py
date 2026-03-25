"""Tests for game world models and services."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    UserDB, PlayerDB, WorldDB, WorldStateDB,
    GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
    ContractDB, ShowDB, MatchDB, MatchParticipantDB,
    ChampionshipDB, StorylineDB, StorylineParticipantDB,
    PlayerActionDB, GameNarrativeLogDB, WorldNewsDB,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestUserModel:
    def test_create_user(self, db_session):
        user = UserDB(email="test@example.com", username="testuser", password_hash="hashed")
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.is_active is True

    def test_user_unique_email(self, db_session):
        db_session.add(UserDB(email="dup@test.com", username="user1", password_hash="h"))
        db_session.commit()
        db_session.add(UserDB(email="dup@test.com", username="user2", password_hash="h"))
        with pytest.raises(Exception):
            db_session.commit()


class TestWorldModel:
    def test_create_world(self, db_session):
        world = WorldDB(name="Test World")
        db_session.add(world)
        db_session.commit()

        assert world.id is not None
        assert world.current_game_date == "2026-01-01"
        assert world.current_tick == 0
        assert world.is_multiplayer is False

    def test_world_with_state(self, db_session):
        world = WorldDB(name="Stateful World")
        db_session.add(world)
        db_session.flush()

        state = WorldStateDB(world_id=world.id, key="economy", value={"health": 75})
        db_session.add(state)
        db_session.commit()

        assert len(world.world_state) == 1
        assert world.world_state[0].key == "economy"


class TestFederationModel:
    def test_create_federation(self, db_session):
        world = WorldDB(name="Fed World")
        db_session.add(world)
        db_session.flush()

        fed = GameFederationDB(
            world_id=world.id,
            name="Test Federation",
            short_name="TF",
        )
        db_session.add(fed)
        db_session.commit()

        assert fed.id is not None
        assert fed.prestige == 50
        assert fed.budget == 100000.0
        assert fed.is_npc is True


class TestWrestlerModel:
    def test_create_wrestler_with_stats(self, db_session):
        world = WorldDB(name="Wrestler World")
        db_session.add(world)
        db_session.flush()

        wrestler = GameWrestlerDB(
            world_id=world.id,
            name="Stone Dragon",
            gimmick="A fierce competitor",
            alignment="heel",
        )
        db_session.add(wrestler)
        db_session.flush()

        stats = WrestlerStatsDB(
            wrestler_id=wrestler.id,
            power=80, speed=60, technical=70,
            charisma=85, mic_skill=90,
        )
        db_session.add(stats)
        db_session.commit()

        assert wrestler.stats is not None
        assert wrestler.stats.power == 80
        assert wrestler.stats.charisma == 85

    def test_wrestler_contract(self, db_session):
        world = WorldDB(name="Contract World")
        db_session.add(world)
        db_session.flush()

        fed = GameFederationDB(world_id=world.id, name="Big Fed")
        wrestler = GameWrestlerDB(world_id=world.id, name="The Rookie")
        db_session.add_all([fed, wrestler])
        db_session.flush()

        contract = ContractDB(
            world_id=world.id,
            wrestler_id=wrestler.id,
            federation_id=fed.id,
            salary_weekly=5000,
            start_date="2026-01-01",
        )
        db_session.add(contract)
        db_session.commit()

        assert len(wrestler.contracts) == 1
        assert wrestler.contracts[0].salary_weekly == 5000


class TestShowModel:
    def test_create_show(self, db_session):
        world = WorldDB(name="Show World")
        db_session.add(world)
        db_session.flush()

        fed = GameFederationDB(world_id=world.id, name="Show Fed")
        db_session.add(fed)
        db_session.flush()

        show = ShowDB(
            world_id=world.id,
            federation_id=fed.id,
            name="Monday Night Raw",
            show_type="weekly",
            game_date="2026-01-05",
        )
        db_session.add(show)
        db_session.commit()

        assert show.id is not None
        assert show.is_completed is False


class TestMatchModel:
    def test_create_match_with_participants(self, db_session):
        world = WorldDB(name="Match World")
        db_session.add(world)
        db_session.flush()

        w1 = GameWrestlerDB(world_id=world.id, name="Fighter A")
        w2 = GameWrestlerDB(world_id=world.id, name="Fighter B")
        db_session.add_all([w1, w2])
        db_session.flush()

        match = MatchDB(world_id=world.id, match_type="singles")
        db_session.add(match)
        db_session.flush()

        db_session.add(MatchParticipantDB(match_id=match.id, wrestler_id=w1.id, role="competitor"))
        db_session.add(MatchParticipantDB(match_id=match.id, wrestler_id=w2.id, role="competitor"))
        db_session.commit()

        assert len(match.participants) == 2


class TestStorylineModel:
    def test_create_storyline(self, db_session):
        world = WorldDB(name="Story World")
        db_session.add(world)
        db_session.flush()

        w1 = GameWrestlerDB(world_id=world.id, name="Hero")
        w2 = GameWrestlerDB(world_id=world.id, name="Villain")
        db_session.add_all([w1, w2])
        db_session.flush()

        storyline = StorylineDB(
            world_id=world.id,
            name="The Great Rivalry",
            storyline_type="feud",
        )
        db_session.add(storyline)
        db_session.flush()

        db_session.add(StorylineParticipantDB(storyline_id=storyline.id, wrestler_id=w1.id, role="protagonist"))
        db_session.add(StorylineParticipantDB(storyline_id=storyline.id, wrestler_id=w2.id, role="antagonist"))
        db_session.commit()

        assert len(storyline.participants) == 2
        assert storyline.heat == 50


class TestPlayerActionModel:
    def test_create_action(self, db_session):
        world = WorldDB(name="Action World")
        user = UserDB(email="p@t.com", username="player1", password_hash="h")
        db_session.add_all([world, user])
        db_session.flush()

        player = PlayerDB(
            user_id=user.id,
            world_id=world.id,
            player_type="promoter",
        )
        db_session.add(player)
        db_session.flush()

        action = PlayerActionDB(
            world_id=world.id,
            player_id=player.id,
            action_type="book_show",
            action_data={"name": "Big Event", "venue": "Arena"},
        )
        db_session.add(action)
        db_session.commit()

        assert action.status == "pending"
        assert action.action_data["name"] == "Big Event"
