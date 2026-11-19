"""HTTP tests for promo submission."""

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_service.database import get_db, get_db_sync
from api_gateway.main import app
from api_gateway.security import create_access_token
from models.db_models import Base
from models.game_models import GameWrestlerDB, UserDB, WorldDB


@pytest_asyncio.fixture
async def promo_client(tmp_path, monkeypatch):
    db_path = tmp_path / "promos.db"
    engine = create_engine(f"sqlite:///{db_path}")
    auth_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    sessions = sessionmaker(bind=engine)
    auth_sessions = async_sessionmaker(bind=auth_engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        user = UserDB(username="promo-player", email="promo@example.test", password_hash="unused")
        db.add_all([user, WorldDB(id="promo-world", name="Promo World", current_game_date="2026-01-10")])
        db.flush()
        db.add(GameWrestlerDB(id="promo-wrestler", world_id="promo-world", name="The Hero"))
        token = create_access_token({"sub": user.id})

    def override_db_sync():
        with sessions() as db:
            yield db

    async def override_db():
        async with auth_sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, override_db_sync)
    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    client = TestClient(app, base_url="http://localhost", headers={"Authorization": f"Bearer {token}"},
                        raise_server_exceptions=False)
    try:
        yield client
    finally:
        client.close()
        await auth_engine.dispose()
        engine.dispose()


def test_submit_promo_missing_world(promo_client):
    response = promo_client.post("/game/worlds/missing-world/promos", json={
        "wrestler_id": "promo-wrestler", "player_content": "I'll see you in the ring.",
    })
    assert response.status_code == 404, response.text
    assert response.json()["message"] == "World not found"


def test_submit_promo_existing_world(promo_client):
    response = promo_client.post("/game/worlds/promo-world/promos", json={
        "wrestler_id": "promo-wrestler", "player_content": "I'll see you in the ring.",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content"] == "I'll see you in the ring."
    assert body["game_date"] == "2026-01-10"
    assert body["is_player_written"] is True


def test_submit_promo_missing_wrestler(promo_client):
    response = promo_client.post("/game/worlds/promo-world/promos", json={"wrestler_id": "missing-wrestler"})
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Wrestler not found"
