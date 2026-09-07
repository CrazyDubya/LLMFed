"""Tests for world service - world creation, player management."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    GameFederationDB,
    GameWrestlerDB,
    WrestlerStatsDB,
    ContractDB,
    ChampionshipDB,
    UserDB,
)
from game_service.world_service import (
    create_world,
    create_player,
    get_roster,
    get_free_agents,
    get_world_federations,
    get_wrestler_with_stats,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCreateWorld:
    def test_creates_world_with_federations(self, db_session):
        world = create_world(db_session, "Test World", "A test")

        assert world.id is not None
        assert world.name == "Test World"
        assert world.current_game_date == "2026-01-01"

        feds = (
            db_session.query(GameFederationDB)
            .filter(GameFederationDB.world_id == world.id)
            .all()
        )
        assert len(feds) >= 3  # 3-5 NPC federations

    def test_creates_wrestlers(self, db_session):
        world = create_world(db_session, "Wrestler World")

        wrestlers = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.world_id == world.id)
            .all()
        )
        assert len(wrestlers) >= 30  # 30-50 wrestlers

    def test_wrestlers_have_stats(self, db_session):
        world = create_world(db_session, "Stats World")

        wrestlers = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.world_id == world.id)
            .all()
        )

        for w in wrestlers:
            stats = (
                db_session.query(WrestlerStatsDB)
                .filter(WrestlerStatsDB.wrestler_id == w.id)
                .first()
            )
            assert stats is not None
            assert 1 <= stats.power <= 100
            assert 1 <= stats.charisma <= 100

    def test_creates_championships(self, db_session):
        world = create_world(db_session, "Championship World")

        champs = (
            db_session.query(ChampionshipDB)
            .filter(ChampionshipDB.world_id == world.id)
            .all()
        )
        assert len(champs) >= 3  # One per federation

    def test_some_wrestlers_under_contract(self, db_session):
        world = create_world(db_session, "Contract World")

        contracts = (
            db_session.query(ContractDB).filter(ContractDB.world_id == world.id).all()
        )
        assert len(contracts) > 0


class TestCreatePlayer:
    def test_create_promoter_player(self, db_session):
        world = create_world(db_session, "Player World")
        user = UserDB(email="test@t.com", username="testuser", password_hash="h")
        db_session.add(user)
        db_session.commit()

        player = create_player(
            db_session,
            user.id,
            world.id,
            "promoter",
            federation_name="My Fed",
            federation_description="A new fed",
        )

        assert player.player_type == "promoter"
        assert player.federation_id is not None

        # Federation was created
        fed = (
            db_session.query(GameFederationDB)
            .filter(GameFederationDB.id == player.federation_id)
            .first()
        )
        assert fed.name == "My Fed"
        assert fed.is_npc is False
        assert fed.prestige == 20  # Start small

    def test_create_wrestler_player(self, db_session):
        world = create_world(db_session, "Wrestler Player World")
        user = UserDB(email="w@t.com", username="wrestler1", password_hash="h")
        db_session.add(user)
        db_session.commit()

        player = create_player(
            db_session,
            user.id,
            world.id,
            "wrestler",
            wrestler_name="Thunder Rose",
            wrestler_gimmick="A fierce competitor",
            wrestler_style="highflyer",
        )

        assert player.player_type == "wrestler"
        assert player.wrestler_id is not None

        wrestler = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.id == player.wrestler_id)
            .first()
        )
        assert wrestler.name == "Thunder Rose"
        assert wrestler.is_npc is False

        # Stats should reflect highflyer style
        stats = (
            db_session.query(WrestlerStatsDB)
            .filter(WrestlerStatsDB.wrestler_id == wrestler.id)
            .first()
        )
        assert stats.aerial > stats.power  # Highflyer bonus

    def test_cannot_create_duplicate_player(self, db_session):
        world = create_world(
            db_session, "Dup World", is_multiplayer=True, max_players=10
        )
        user = UserDB(email="dup@t.com", username="dupuser", password_hash="h")
        db_session.add(user)
        db_session.commit()

        create_player(db_session, user.id, world.id, "promoter")

        with pytest.raises(ValueError, match="already have"):
            create_player(db_session, user.id, world.id, "wrestler")


class TestWorldQueries:
    def test_get_roster(self, db_session):
        world = create_world(db_session, "Roster World")

        feds = (
            db_session.query(GameFederationDB)
            .filter(GameFederationDB.world_id == world.id)
            .all()
        )

        # At least one federation should have wrestlers
        has_roster = False
        for fed in feds:
            roster = get_roster(db_session, fed.id)
            if len(roster) > 0:
                has_roster = True
                break
        assert has_roster

    def test_get_free_agents(self, db_session):
        world = create_world(db_session, "FA World")
        # Some wrestlers should be free agents (20% chance)
        # With 30-50 wrestlers, statistically very likely to have some
        fas = get_free_agents(db_session, world.id)
        # Could be 0 in rare cases, just check it doesn't error
        assert isinstance(fas, list)

    def test_get_world_federations(self, db_session):
        world = create_world(db_session, "Fed Query World")
        feds = get_world_federations(db_session, world.id)
        assert len(feds) >= 3

    def test_get_wrestler_with_stats(self, db_session):
        world = create_world(db_session, "WS World")
        wrestlers = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.world_id == world.id)
            .first()
        )

        w, stats = get_wrestler_with_stats(db_session, wrestlers.id)
        assert w.name == wrestlers.name
        assert stats is not None
