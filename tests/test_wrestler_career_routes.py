"""HTTP regression coverage for wrestler career data."""

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
        db.add(WorldDB(id="career-world", name="Career World"))
        db.add(GameWrestlerDB(id="veteran", world_id="career-world", name="Veteran", experience_years=7))
        db.add(GameWrestlerDB(id="rookie", world_id="career-world", name="Rookie"))

    def get_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, get_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="career-user"))
    try:
        with TestClient(app, base_url="http://localhost") as client:
            yield client
    finally:
        engine.dispose()


@pytest.mark.parametrize("wrestler_id,years", [("veteran", 7), ("rookie", 0)])
def test_wrestler_detail_includes_experience_years(wrestler_api, wrestler_id, years):
    response = wrestler_api.get(f"/game/wrestlers/{wrestler_id}")
    assert response.status_code == 200, response.text
    assert response.json()["wrestler"]["experience_years"] == years


def test_missing_wrestler(wrestler_api):
    assert wrestler_api.get("/game/wrestlers/missing").status_code == 404
