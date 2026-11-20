"""Persist match requests across HTTP action submission and world ticks."""

import json
import zlib
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_service.database import get_db, get_db_sync
from api_gateway.main import app
from api_gateway.security import create_access_token
from game_service import show_service
from models.db_models import Base
from models.game_models import (
    ContractDB, GameFederationDB, GameWrestlerDB, MatchParticipantDB, PlayerDB, ShowDB, UserDB, WorldDB,
)


@pytest_asyncio.fixture
async def match_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'requests.db'}")
    auth_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'requests.db'}")
    auth_sessions = async_sessionmaker(bind=auth_engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        db.add_all([
            WorldDB(id="world", name="Request World", current_game_date="2026-01-04"),
            UserDB(id="user", username="requester", email="requester@example.test", password_hash="unused"),
        ])
        db.flush()
        db.add_all([
            GameFederationDB(id="fed", world_id="world", name="Request Federation", is_npc=False),
            GameWrestlerDB(id="wrestler", world_id="world", name="Challenger", popularity=30),
            GameWrestlerDB(id="opponent", world_id="world", name="Opponent", popularity=30),
        ])
        db.flush()
        db.add(PlayerDB(user_id="user", world_id="world", player_type="wrestler", wrestler_id="wrestler"))
        db.add_all(ContractDB(world_id="world", federation_id="fed", wrestler_id=wid,
                              start_date="2026-01-01") for wid in ["wrestler", "opponent"])

    def override_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, override_db)

    async def override_auth_db():
        async with auth_sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, override_auth_db)
    token = create_access_token({"sub": "user"})
    with TestClient(app, base_url="http://localhost", headers={"Authorization": f"Bearer {token}"},
                    raise_server_exceptions=False) as client:
        yield client, sessions
    engine.dispose()
    await auth_engine.dispose()


@pytest.mark.parametrize("action_type", ["request_match", "open_challenge"])
@pytest.mark.parametrize("config", [{}, {"difficulty": "normal"}, {
    "difficulty": "normal", "pending_match_requests": [
        {"wrestler_id": "someone-else", "date": "2026-01-01", "type": "request_match"},
        {"wrestler_id": "wrestler", "date": "2025-12-01", "type": "request_match"},
    ],
}], ids=["empty", "nonempty", "existing-requests"])
def test_match_request_persists(match_client, action_type, config):
    client, sessions = match_client
    with sessions.begin() as db:
        db.get(WorldDB, "world").world_config = config
    path = "/game/worlds/world"
    payload = {"action_type": action_type, "action_data": {"wrestler_id": "wrestler"}}
    submitted = client.post(f"{path}/actions", json=payload)
    print(f"POST {path}/actions {json.dumps(payload)} -> {submitted.status_code} {submitted.text}")
    assert submitted.status_code == 202, submitted.text
    tick = client.post(f"{path}/tick")
    assert tick.status_code == 200, tick.text
    actions = client.get(f"{path}/actions")
    print(f"GET {path}/actions -> {actions.status_code} {actions.text}")
    assert actions.json()[0]["status"] == "completed", actions.text
    with sessions() as db:
        persisted = db.get(WorldDB, "world").world_config
    print(f"Fresh database session world_config: {json.dumps(persisted, sort_keys=True)}")
    expected = {"wrestler_id": "wrestler", "federation_id": "fed", "date": "2026-01-05", "type": action_type}
    if action_type == "open_challenge":
        expected["opponent_id"] = "opponent"
    retained = [r for r in config.get("pending_match_requests", []) if r["wrestler_id"] != "wrestler"]
    assert persisted == {**config, "pending_match_requests": [*retained, expected]}


@pytest.mark.parametrize("action_type", ["request_match", "open_challenge"])
@pytest.mark.parametrize("case", ["missing-wrestler", "no-contract", "unavailable"])
def test_match_request_without_booking_preserves_config(match_client, action_type, case):
    client, sessions = match_client
    config = {"difficulty": "normal"}
    if case == "unavailable" and action_type == "request_match":
        config["pending_match_requests"] = [{"wrestler_id": "wrestler", "date": "2026-01-04"}]
    with sessions.begin() as db:
        db.get(WorldDB, "world").world_config = config
        if case == "no-contract":
            db.query(ContractDB).filter_by(wrestler_id="wrestler").delete()
        if case == "unavailable" and action_type == "open_challenge":
            db.get(GameWrestlerDB, "opponent").is_injured = True
    response = client.post("/game/worlds/world/actions", json={
        "action_type": action_type,
        "action_data": {"wrestler_id": "missing" if case == "missing-wrestler" else "wrestler"},
    })
    assert response.status_code == 202, response.text
    tick = client.post("/game/worlds/world/tick")
    assert tick.status_code == 200, tick.text
    action = client.get("/game/worlds/world/actions").json()[0]
    if case == "unavailable":
        assert action["status"] == "completed"
        expected = "cooldown" if action_type == "request_match" else "No suitable opponents"
        assert expected in action["result"]["message"]
    else:
        assert action["status"] == "failed"
        expected = "Wrestler not found" if case == "missing-wrestler" else "Wrestler has no active contract"
        assert action["result"]["error"] == expected
    with sessions() as db:
        assert db.get(WorldDB, "world").world_config == config


def test_booked_request_is_consumed_before_later_show(match_client, monkeypatch):
    client, sessions = match_client
    monkeypatch.setattr(show_service.random, "random", lambda: 0.99)
    show_day = zlib.crc32(b"fed") % 7
    show_date = datetime(2026, 1, 5) + timedelta(days=show_day)
    pending = {"wrestler_id": "wrestler", "federation_id": "fed", "opponent_id": "opponent",
               "type": "open_challenge", "date": "2026-01-01"}
    unrelated = {"wrestler_id": "elsewhere", "federation_id": "other-fed", "type": "request_match"}
    with sessions.begin() as db:
        world = db.get(WorldDB, "world")
        world.current_game_date = (show_date - timedelta(days=1)).strftime("%Y-%m-%d")
        world.world_config = {"difficulty": "normal", "pending_match_requests": [pending, unrelated]}
        db.get(GameFederationDB, "fed").is_npc = True
        db.get(GameWrestlerDB, "wrestler").popularity = 10
        db.get(GameWrestlerDB, "opponent").popularity = 90
        db.add_all(GameWrestlerDB(id=wid, world_id="world", name=wid, popularity=pop)
                   for wid, pop in [("middle-low", 35), ("middle-high", 65)])
        db.flush()
        db.add_all(ContractDB(world_id="world", federation_id="fed", wrestler_id=wid,
                              start_date="2026-01-01") for wid in ["middle-low", "middle-high"])

    def has_requested_pair(db, show):
        for segment in show.segments:
            if not segment.match_id:
                continue
            match = segment.match
            ids = {p.wrestler_id for p in db.query(MatchParticipantDB).filter_by(match_id=match.id)}
            if ids == {"wrestler", "opponent"}:
                return True
        return False

    tick = client.post("/game/worlds/world/tick")
    assert tick.status_code == 200, tick.text
    with sessions() as db:
        show = db.query(ShowDB).filter_by(world_id="world").one()
        assert show.is_completed
        assert has_requested_pair(db, show)
        persisted = db.get(WorldDB, "world").world_config
        assert persisted == {"difficulty": "normal", "pending_match_requests": [unrelated]}

    tick = client.post("/game/worlds/world/tick?days=7")
    assert tick.status_code == 200, tick.text
    with sessions() as db:
        shows = db.query(ShowDB).filter_by(world_id="world").order_by(ShowDB.game_date).all()
        assert len(shows) == 2
        assert shows[1].is_completed
        assert not has_requested_pair(db, shows[1])
        assert db.get(WorldDB, "world").world_config == persisted


def test_open_challenge_waits_for_injured_opponent(match_client, monkeypatch):
    client, sessions = match_client
    monkeypatch.setattr(show_service.random, "random", lambda: 0.99)
    path = "/game/worlds/world"
    accepted = client.post(f"{path}/actions", json={
        "action_type": "open_challenge",
        "action_data": {"wrestler_id": "wrestler"},
    })
    assert accepted.status_code == 202, accepted.text
    tick = client.post(f"{path}/tick")
    assert tick.status_code == 200, tick.text
    actions = client.get(f"{path}/actions")
    assert actions.status_code == 200, actions.text
    action = actions.json()[0]
    assert action["status"] == "completed"
    assert action["result"]["opponent_id"] == "opponent"
    print(f"POST {path}/actions -> {accepted.status_code}; GET {path}/actions -> {actions.status_code} "
          f"{action['result']['message']}")

    show_date = datetime(2026, 1, 5) + timedelta(days=zlib.crc32(b"fed") % 7)
    with sessions.begin() as db:
        world = db.get(WorldDB, "world")
        pending = world.world_config["pending_match_requests"]
        world.current_game_date = (show_date - timedelta(days=1)).strftime("%Y-%m-%d")
        db.get(GameFederationDB, "fed").is_npc = True
        opponent = db.get(GameWrestlerDB, "opponent")
        opponent.is_injured = True
        opponent.injury_return_date = (show_date + timedelta(days=1)).strftime("%Y-%m-%d")
        opponent.popularity = 90
        db.add_all(GameWrestlerDB(id=wid, world_id="world", name=wid, popularity=pop)
                   for wid, pop in [("middle-low", 50), ("middle-high", 65)])
        db.flush()
        db.add_all(ContractDB(world_id="world", federation_id="fed", wrestler_id=wid,
                              start_date="2026-01-01") for wid in ["middle-low", "middle-high"])

    def show_matches(db, date):
        show = db.query(ShowDB).filter_by(world_id="world", game_date=date).one()
        assert show.is_completed
        return [{p.wrestler_id for p in db.query(MatchParticipantDB).filter_by(match_id=segment.match_id)}
                for segment in show.segments if segment.match_id]

    tick = client.post(f"{path}/tick")
    assert tick.status_code == 200, tick.text
    with sessions() as db:
        matches = show_matches(db, tick.json()["current_game_date"])
        assert matches and all("opponent" not in pair for pair in matches)
        retained = db.get(WorldDB, "world").world_config["pending_match_requests"]
    print(f"POST {path}/tick -> {tick.status_code} {tick.json()['current_game_date']}; "
          f"matches={list(map(sorted, matches))}; pending={retained}")

    tick = client.post(f"{path}/tick?days=7")
    assert tick.status_code == 200, tick.text
    with sessions() as db:
        assert not db.get(GameWrestlerDB, "opponent").is_injured
        matches = show_matches(db, tick.json()["current_game_date"])
        remaining = db.get(WorldDB, "world").world_config["pending_match_requests"]
    print(f"POST {path}/tick?days=7 -> {tick.status_code} {tick.json()['current_game_date']}; "
          f"matches={list(map(sorted, matches))}; pending={remaining}")
    assert retained == pending
    assert {"wrestler", "opponent"} in matches
    assert remaining == []
