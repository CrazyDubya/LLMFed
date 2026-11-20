"""HTTP tests for manager bond assignment."""

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_service.database import get_db, get_db_sync
from api_gateway.main import app
from api_gateway.security import create_access_token
from models.db_models import Base
from models.game_models import GameWrestlerDB, ManagerDB, UserDB, WorldDB


@pytest_asyncio.fixture
async def bond_client(tmp_path, monkeypatch):
    db_path = tmp_path / "bonds.db"
    engine = create_engine(f"sqlite:///{db_path}")
    auth_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    sessions = sessionmaker(bind=engine)
    auth_sessions = async_sessionmaker(bind=auth_engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        user = UserDB(username="bond-player", email="bond@example.test", password_hash="unused")
        db.add_all([user, WorldDB(id="bond-world", name="Bond World", current_game_date="2026-01-10")])
        db.flush()
        db.add_all([
            ManagerDB(id="bond-manager", world_id="bond-world", name="The Advocate"),
            GameWrestlerDB(id="bond-wrestler", world_id="bond-world", name="The Hero"),
        ])
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


def test_assign_manager_missing_world(bond_client):
    response = bond_client.post("/game/worlds/missing-world/manager-bonds", json={
        "manager_id": "bond-manager", "client_wrestler_id": "bond-wrestler",
    })
    print(f"RAW HTTP: {response.status_code} {response.text}")
    assert response.status_code == 404, response.text
    assert response.json()["message"] == "World not found"


def test_assign_manager_existing_world(bond_client):
    response = bond_client.post("/game/worlds/bond-world/manager-bonds", json={
        "manager_id": "bond-manager", "client_wrestler_id": "bond-wrestler",
    })
    assert response.status_code == 201, response.text
    assert response.json()["manager_id"] == "bond-manager"
    assert response.json()["client_wrestler_id"] == "bond-wrestler"


def test_assign_manager_missing_manager(bond_client):
    response = bond_client.post("/game/worlds/bond-world/manager-bonds", json={
        "manager_id": "missing-manager", "client_wrestler_id": "bond-wrestler",
    })
    assert response.status_code == 404, response.text
    assert response.json()["message"] == "Manager not found"


def test_assign_manager_empty_payload(bond_client):
    response = bond_client.post("/game/worlds/bond-world/manager-bonds", json={})
    assert response.status_code == 422, response.text


def test_readd_removed_manager(bond_client):
    url = "/game/worlds/bond-world/manager-bonds"
    payload = {"manager_id": "bond-manager", "client_wrestler_id": "bond-wrestler"}
    added = bond_client.post(url, json=payload)
    assert added.status_code == 201, added.text
    bond_id = added.json()["id"]
    active_duplicate = bond_client.post(url, json=payload)
    removed = bond_client.delete(f"/game/manager-bonds/{bond_id}")
    readded = bond_client.post(url, json={**payload, "role": "valet", "specialization": "promo_boost"})
    duplicate = bond_client.post(url, json=payload)
    for label, response in [("add", added), ("remove", removed),
                            ("re-add", readded), ("duplicate-active add", active_duplicate),
                            ("duplicate after re-add", duplicate)]:
        print(f"HTTP {label}: {response.status_code} {response.text}")
    assert active_duplicate.status_code == 409, active_duplicate.text
    assert removed.status_code == 204, removed.text
    assert readded.status_code == 201, readded.text
    assert readded.json()["id"] == bond_id
    assert readded.json()["is_active"] is True
    assert readded.json()["role"] == "valet"
    assert readded.json()["specialization"] == "promo_boost"
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["message"] == "Database constraint violation"
    bonds = bond_client.get(url).json()
    assert len(bonds) == 1
    assert bonds[0]["id"] == bond_id
