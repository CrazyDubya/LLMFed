"""HTTP regression tests for atomic New Game setup."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from game_service import world_service
from models.core_models import UserDB
from models.db_models import Base
from models.game_models import GameFederationDB, GameWrestlerDB, PlayerDB, WorldDB


@pytest.fixture
def game_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions.begin() as db:
        db.add(UserDB(id="booker", username="booker", email="booker@example.com", password_hash="unused"))

    def get_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, get_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="booker"))
    try:
        with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as client:
            yield client, sessions
    finally:
        engine.dispose()


def _new_game(client, **player):
    return client.post("/game/new-game", json={
        "world": {"name": "Test World"},
        "player": player,
    })


def test_invalid_new_game_leaves_no_world_and_retry_creates_one(game_api):
    client, sessions = game_api
    response = _new_game(client, player_type="promoter", federation_name="F" * 101)
    assert response.status_code == 422, response.text
    with sessions() as db:
        assert db.query(WorldDB).count() == 0
        assert db.query(PlayerDB).count() == 0

    response = _new_game(client, player_type="promoter", federation_name="Apex Pro Wrestling")
    assert response.status_code == 201, response.text
    player = response.json()
    assert player["user_id"] == "booker"
    with sessions() as db:
        world = db.query(WorldDB).one()
        assert world.id == player["world_id"]
        assert world.name == "Test World"
        assert not world.is_multiplayer
        assert db.query(PlayerDB).one().id == player["id"]
        assert db.get(GameFederationDB, player["federation_id"]).name == "Apex Pro Wrestling"
    assert client.get(f"/game/worlds/{world.id}/my-player").json() == player


def test_new_game_rolls_back_seeded_world_on_player_failure(game_api, monkeypatch):
    client, sessions = game_api
    create_federation = world_service._create_player_federation
    attempted = []

    def fail_after_insert(db, world_id, options):
        create_federation(db, world_id, options)
        attempted.append(world_id)
        raise RuntimeError("Could not complete player creation")

    with monkeypatch.context() as patch:
        patch.setattr(world_service, "_create_player_federation", fail_after_insert)
        response = _new_game(client, player_type="promoter", federation_name="Apex Pro Wrestling")
    assert response.status_code == 500, response.text
    assert len(attempted) == 1
    with sessions() as db:
        for model in (WorldDB, GameFederationDB, GameWrestlerDB, PlayerDB):
            assert db.query(model).count() == 0

    response = _new_game(client, player_type="wrestler", wrestler_name="Thunder Rose")
    assert response.status_code == 201, response.text
    player = response.json()
    with sessions() as db:
        assert db.query(WorldDB).one().id == player["world_id"]
        assert db.query(PlayerDB).one().id == player["id"]
        assert db.get(GameWrestlerDB, player["wrestler_id"]).name == "Thunder Rose"


def test_separate_create_world_and_join_remain_available(game_api):
    client, sessions = game_api
    response = client.post("/game/worlds", json={
        "name": "Multiplayer World", "is_multiplayer": True, "max_players": 2,
    })
    assert response.status_code == 201, response.text
    world = response.json()
    assert world["is_multiplayer"]
    assert world["max_players"] == 2
    with sessions() as db:
        assert db.query(PlayerDB).count() == 0

    join = {"world_id": world["id"], "player_type": "wrestler", "wrestler_name": "The Rookie"}
    response = client.post("/game/players", json=join)
    assert response.status_code == 201, response.text
    assert response.json()["world_id"] == world["id"]
    response = client.post("/game/players", json=join)
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "You already have a character in this world"
