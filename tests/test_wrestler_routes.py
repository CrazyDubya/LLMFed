"""HTTP regression tests for the wrestler dashboard detail endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from models.db_models import Base
from models.game_models import GameWrestlerDB, WorldDB


@pytest.fixture
def wrestler_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add(WorldDB(id="injury-world", name="Injury World"))

    def get_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, get_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="injury-user"))
    try:
        with TestClient(app, base_url="http://localhost") as client:
            yield client, sessions
    finally:
        engine.dispose()


@pytest.mark.parametrize("return_date", ["2026-03-12", None])
def test_wrestler_detail_injury_return_date(wrestler_api, return_date):
    client, sessions = wrestler_api
    with sessions.begin() as db:
        db.add(GameWrestlerDB(
            id="injured-wrestler", world_id="injury-world", name="Recovery Star",
            is_injured=return_date is not None, injury_return_date=return_date,
        ))

    response = client.get("/game/wrestlers/injured-wrestler")

    assert response.status_code == 200, response.text
    wrestler = response.json()["wrestler"]
    assert wrestler["injury_return_date"] == return_date
    assert wrestler["is_injured"] is (return_date is not None)


def test_wrestler_detail_missing(wrestler_api):
    client, _ = wrestler_api
    response = client.get("/game/wrestlers/missing-wrestler")
    assert response.status_code == 404, response.text
