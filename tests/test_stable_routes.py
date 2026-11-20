"""HTTP regressions for stable membership changes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from models.db_models import Base
from models.game_models import (
    WorldDB, GameFederationDB, GameWrestlerDB, PlayerDB, StableDB, StableMemberDB,
)


@pytest.fixture
def stable_api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        db.add(WorldDB(id="world", name="World", current_game_date="2026-01-01"))
        db.add(GameFederationDB(id="fed", world_id="world", name="Fed"))
        db.add(PlayerDB(user_id="owner", world_id="world", player_type="promoter", federation_id="fed"))
        db.add(StableDB(id="stable", world_id="world", federation_id="fed", name="Stable"))
        for i in range(3):
            db.add(GameWrestlerDB(id=f"w{i}", world_id="world", name=f"Wrestler {i}"))
        db.flush()
        for i in range(2):
            db.add(StableMemberDB(stable_id="stable", wrestler_id=f"w{i}"))
        db.commit()

    def get_db():
        with sessions() as db:
            yield db

    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_sync] = get_db
    app.dependency_overrides[get_current_user] = lambda: TokenData(user_id="owner")
    try:
        yield TestClient(app, base_url="http://localhost", raise_server_exceptions=False), sessions
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        engine.dispose()


def test_member_can_rejoin_stable(stable_api):
    client, sessions = stable_api
    url = "/game/stables/stable/members"
    added = client.post(url, json={"wrestler_id": "w2", "role": "recruit"})
    assert added.status_code == 201, added.text
    assert client.delete(f"{url}/w2").status_code == 204
    with sessions() as db:
        member = db.query(StableMemberDB).filter_by(wrestler_id="w2").one()
        assert member.is_active is False
        assert member.left_date == "2026-01-01"
        db.get(WorldDB, "world").current_game_date = "2026-01-05"
        db.commit()
    rejoined = client.post(url, json={"wrestler_id": "w2", "role": "enforcer"})
    assert rejoined.status_code == 201, rejoined.text
    assert rejoined.json() == {"id": added.json()["id"], "wrestler_id": "w2", "role": "enforcer"}
    with sessions() as db:
        member = db.query(StableMemberDB).filter_by(wrestler_id="w2").one()
        assert member.is_active is True
        assert member.left_date is None
        assert member.joined_date == "2026-01-05"
        assert (member.loyalty, member.influence) == (65, 30)


def test_active_member_still_conflicts(stable_api):
    client, sessions = stable_api
    response = client.post("/game/stables/stable/members", json={"wrestler_id": "w0"})
    assert response.status_code == 409, response.text
    assert response.json()["message"] == "Database constraint violation"
    with sessions() as db:
        assert db.query(StableMemberDB).filter_by(wrestler_id="w0").count() == 1
