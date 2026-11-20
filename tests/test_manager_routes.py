"""HTTP regression tests for manager creation."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from models.db_models import Base
from models.game_models import ManagerDB, WorldDB


@pytest.fixture
def manager_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add(WorldDB(id="manager-world", name="Manager World"))

    def get_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, get_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="manager-user"))
    try:
        with TestClient(app, base_url="http://localhost") as client:
            yield client, sessions
    finally:
        engine.dispose()


def test_create_manager_missing_world(manager_api):
    client, sessions = manager_api
    response = client.post("/game/worlds/missing-world/managers", json={"name": "Orphan Manager"})
    with sessions() as db:
        count = db.query(ManagerDB).count()
    assert (response.status_code, count) == (404, 0), response.text
    assert response.json()["message"] == "World not found"


def test_create_manager_existing_world(manager_api):
    client, sessions = manager_api
    response = client.post("/game/worlds/manager-world/managers", json={"name": "Valid Manager"})
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Valid Manager"
    with sessions() as db:
        manager = db.query(ManagerDB).one()
        assert manager.id == response.json()["id"]
        assert manager.world_id == "manager-world"
