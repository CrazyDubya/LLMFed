"""HTTP tests for manager bond assignment."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_service.database import get_db, get_db_sync
from api_gateway.main import app
from api_gateway.security import create_access_token
from models.db_models import Base
from models.game_models import (
    GameFederationDB, GameWrestlerDB, ManagerClientDB, ManagerDB, PlayerDB, UserDB, WorldDB,
)


@pytest.fixture
def bond_sessions(tmp_path):
    db_path = tmp_path / "bonds.db"
    engine = create_engine(f"sqlite:///{db_path}")
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        user = UserDB(id="bond-player", username="bond-player", email="bond@example.test", password_hash="unused")
        db.add_all([
            user,
            WorldDB(id="bond-world", name="Bond World", current_game_date="2026-01-10"),
            WorldDB(id="other-world", name="Other World", current_game_date="2026-01-10"),
        ])
        db.flush()
        db.add_all([
            ManagerDB(id="bond-manager", world_id="bond-world", name="The Advocate"),
            GameWrestlerDB(id="bond-wrestler", world_id="bond-world", name="The Hero"),
            GameWrestlerDB(id="other-wrestler", world_id="other-world", name="The Outsider"),
        ])
    try:
        yield sessions
    finally:
        engine.dispose()


@pytest_asyncio.fixture
async def bond_client(tmp_path, monkeypatch, bond_sessions):
    auth_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bonds.db'}")
    auth_sessions = async_sessionmaker(bind=auth_engine)
    token = create_access_token({"sub": "bond-player"})

    def override_db_sync():
        with bond_sessions() as db:
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


def test_list_manager_bonds_filters_by_manager_federation(bond_client, bond_sessions):
    with bond_sessions.begin() as db:
        db.add_all([
            GameFederationDB(id="home-fed", world_id="bond-world", name="Home Federation"),
            GameFederationDB(id="rival-fed", world_id="bond-world", name="Rival Federation"),
            UserDB(id="rival-user", username="rival", email="rival@example.test", password_hash="unused"),
        ])
        db.flush()
        db.add_all([
            PlayerDB(user_id="bond-player", world_id="bond-world", player_type="promoter", federation_id="home-fed"),
            PlayerDB(user_id="rival-user", world_id="bond-world", player_type="promoter", federation_id="rival-fed"),
            ManagerDB(id="home-manager", world_id="bond-world", name="Home Manager", federation_id="home-fed"),
            ManagerDB(id="rival-manager", world_id="bond-world", name="Rival Manager", federation_id="rival-fed"),
        ])
        db.flush()
        db.add_all([
            ManagerClientDB(id="home-bond", world_id="bond-world", manager_id="home-manager",
                            client_wrestler_id="bond-wrestler"),
            ManagerClientDB(id="rival-bond", world_id="bond-world", manager_id="rival-manager",
                            client_wrestler_id="bond-wrestler"),
            ManagerClientDB(id="freelance-bond", world_id="bond-world", manager_id="bond-manager",
                            client_wrestler_id="bond-wrestler"),
        ])

    endpoint = "/game/worlds/bond-world/manager-bonds"
    scoped = bond_client.get(endpoint, params={"federation_id": "home-fed"})
    assert scoped.status_code == 200, scoped.text
    assert [bond["id"] for bond in scoped.json()] == ["home-bond"]
    assert scoped.json()[0]["manager_name"] == "Home Manager"

    unscoped = bond_client.get(endpoint)
    assert unscoped.status_code == 200, unscoped.text
    assert {bond["id"] for bond in unscoped.json()} == {"home-bond", "rival-bond", "freelance-bond"}

    empty = bond_client.get(endpoint, params={"federation_id": "missing-fed"})
    assert empty.status_code == 200, empty.text
    assert empty.json() == []

    forbidden = bond_client.delete("/game/manager-bonds/rival-bond")
    assert forbidden.status_code == 403, forbidden.text


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


def test_assign_manager_rejects_client_with_active_rival_bond(bond_client, bond_sessions):
    with bond_sessions.begin() as db:
        db.add_all([
            GameFederationDB(id="home-fed", world_id="bond-world", name="Home Federation"),
            GameFederationDB(id="rival-fed", world_id="bond-world", name="Rival Federation"),
        ])
        db.flush()
        db.get(ManagerDB, "bond-manager").federation_id = "home-fed"
        db.add_all([
            PlayerDB(user_id="bond-player", world_id="bond-world", player_type="promoter", federation_id="home-fed"),
            ManagerDB(id="rival-manager", world_id="bond-world", name="Rival Manager", federation_id="rival-fed"),
        ])
        db.flush()
        db.add(ManagerClientDB(id="rival-bond", world_id="bond-world", manager_id="rival-manager",
                               client_wrestler_id="bond-wrestler"))

    endpoint = "/game/worlds/bond-world/manager-bonds"
    scoped = bond_client.get(endpoint, params={"federation_id": "home-fed"})
    assert scoped.status_code == 200, scoped.text
    assert scoped.json() == []

    response = bond_client.post(endpoint, json={
        "manager_id": "bond-manager", "client_wrestler_id": "bond-wrestler", "role": "valet",
    })
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Wrestler already has an active manager"
    assert response.json()["error_code"] == "HTTP_400"

    bonds = bond_client.get(endpoint)
    assert bonds.status_code == 200, bonds.text
    assert [bond["id"] for bond in bonds.json()] == ["rival-bond"]


def test_assign_manager_missing_manager(bond_client):
    response = bond_client.post("/game/worlds/bond-world/manager-bonds", json={
        "manager_id": "missing-manager", "client_wrestler_id": "bond-wrestler",
    })
    assert response.status_code == 404, response.text
    assert response.json()["message"] == "Manager not found"


@pytest.mark.parametrize("wrestler_id", ["other-wrestler", "missing-wrestler"])
def test_assign_manager_requires_wrestler_in_world(bond_client, wrestler_id):
    endpoint = "/game/worlds/bond-world/manager-bonds"
    response = bond_client.post(endpoint, json={
        "manager_id": "bond-manager", "client_wrestler_id": wrestler_id,
    })
    assert response.status_code == 404, response.text
    assert response.json()["message"] == "Wrestler not found in this world"

    bonds = bond_client.get(endpoint)
    assert bonds.status_code == 200, bonds.text
    assert bonds.json() == []


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
