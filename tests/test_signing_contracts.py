"""Signing actions must see contracts created earlier in the same tick."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from game_service.player_action_handler import PlayerActionHandler
from game_service.world_ticker import WorldTicker
from models.game_models import (
    Base, WorldDB, GameFederationDB, GameWrestlerDB, PlayerDB,
    PlayerActionDB, ContractDB, GameNarrativeLogDB,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, autoflush=False)() as session:
        session.add_all([
            WorldDB(id="world", name="Signing", current_game_date="2026-01-04"),
            GameFederationDB(id="fed", world_id="world", name="Fed", is_npc=False),
            GameWrestlerDB(id="wrestler", world_id="world", name="Free Agent"),
            PlayerDB(id="player", user_id="user", world_id="world",
                     player_type="promoter", federation_id="fed"),
        ])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def signing_api(db, monkeypatch):
    def get_db():
        with sessionmaker(bind=db.bind, autoflush=False)() as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, get_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="user"))
    return TestClient(app, base_url="http://localhost", raise_server_exceptions=False)


@pytest.mark.parametrize("salary", [-100000, "-100000", float("inf"), float("nan"), "NaN"])
def test_submit_signing_rejects_invalid_salary(db, signing_api, salary):
    response = signing_api.post(
        "/game/worlds/world/actions",
        content=json.dumps({
            "action_type": "sign_wrestler",
            "action_data": {"wrestler_id": "wrestler", "federation_id": "fed", "salary_weekly": salary},
        }),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400, response.text
    assert "salary_weekly" in response.json()["message"]
    assert db.query(PlayerActionDB).count() == 0


def test_submit_and_process_signing_allows_zero_salary(db, signing_api):
    response = signing_api.post("/game/worlds/world/actions", json={
        "action_type": "sign_wrestler",
        "action_data": {"wrestler_id": "wrestler", "federation_id": "fed", "salary_weekly": 0},
    })

    assert response.status_code == 202, response.text
    WorldTicker(db, "world")._process_player_actions()
    assert db.query(ContractDB).one().salary_weekly == 0


@pytest.mark.parametrize("salary", [-100000, float("inf"), float("nan")])
def test_pending_signing_with_invalid_salary_creates_no_contract(db, salary):
    action = PlayerActionDB(
        world_id="world", player_id="player", action_type="sign_wrestler",
        action_data={"wrestler_id": "wrestler", "federation_id": "fed", "salary_weekly": salary},
    )
    db.add(action)
    db.commit()

    WorldTicker(db, "world")._process_player_actions()
    db.commit()

    assert action.status == "failed"
    assert "salary_weekly" in action.result["error"]
    assert db.query(ContractDB).count() == 0


@pytest.mark.parametrize("federation_id", ["fed", "other-fed"])
def test_duplicate_queued_signings_only_create_one_contract(db, federation_id):
    db.add(GameFederationDB(id="other-fed", world_id="world", name="Other Fed", is_npc=False))
    actions = [PlayerActionDB(
        world_id="world", player_id="player", action_type="sign_wrestler",
        action_data={"wrestler_id": "wrestler", "federation_id": fed, "salary_weekly": 1000},
    ) for fed in ["fed", federation_id]]
    db.add_all(actions)
    db.commit()

    ticker = WorldTicker(db, "world")
    ticker._process_player_actions()
    db.commit()

    assert sorted(a.status for a in actions) == ["completed", "failed"]
    completed = next(a for a in actions if a.status == "completed")
    failed = next(a for a in actions if a.status == "failed")
    assert failed.result == {"error": "Wrestler already under contract"}
    contracts = db.query(ContractDB).filter_by(status="active").all()
    assert len(contracts) == 1
    assert completed.result["contract_id"] == contracts[0].id
    assert db.query(GameNarrativeLogDB).filter_by(event_type="signing").count() == 1
    assert sum(c.salary_weekly for c in contracts) == 1000
    with patch("game_service.world_ticker.random.uniform", return_value=5000):
        ticker._economy_tick()
    assert sum(f.weekly_expenses for f in db.query(GameFederationDB).all()) == 11000


def test_signing_returns_persisted_contract_without_committing(db):
    world = db.get(WorldDB, "world")
    handler = PlayerActionHandler(db, world, lambda *args: None)
    result = handler.execute(PlayerActionDB(
        action_type="sign_wrestler",
        action_data={"wrestler_id": "wrestler", "federation_id": "fed"},
    ))
    assert result["contract_id"] is not None
    contract = db.query(ContractDB).one()
    assert result == {"contract_id": contract.id, "wrestler": "Free Agent"}
    assert contract.salary_weekly == 1000
    db.rollback()
    assert db.query(ContractDB).count() == 0


def test_signing_missing_wrestler_does_not_create_contract(db):
    handler = PlayerActionHandler(db, db.get(WorldDB, "world"), lambda *args: None)
    with pytest.raises(ValueError, match="Wrestler not found"):
        handler.execute(PlayerActionDB(action_type="sign_wrestler", action_data={}))
    db.commit()
    assert db.query(ContractDB).count() == 0
