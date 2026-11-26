"""HTTP tests for world access on snapshot routes."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_service.database import get_db, get_db_sync
from api_gateway.main import app
from api_gateway.routes import snapshot_routes
from api_gateway.security import create_access_token
from models.db_models import Base
from models.game_models import PlayerDB, UserDB, WorldDB


SNAPSHOTS = "/game/snapshots"


@pytest_asyncio.fixture
async def snapshot_client(tmp_path, monkeypatch):
    db_path = tmp_path / "snapshots.db"
    engine = create_engine(f"sqlite:///{db_path}")
    auth_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    sessions = sessionmaker(bind=engine)
    auth_sessions = async_sessionmaker(bind=auth_engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        headers = {}
        for username in ("owner", "other"):
            user = UserDB(id=username, username=username, email=f"{username}@example.test", password_hash="unused")
            world = WorldDB(id=f"{username}-world", name=f"{username}'s world")
            db.add_all([user, world])
            db.flush()
            db.add(PlayerDB(user_id=user.id, world_id=world.id, player_type="promoter"))
            headers[username] = {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}

    def override_db_sync():
        with sessions() as db:
            yield db

    async def override_db():
        async with auth_sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, override_db_sync)
    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    monkeypatch.setattr(snapshot_routes, "_snapshots", {})
    with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as client:
        yield client, headers
    await auth_engine.dispose()
    engine.dispose()


def _create_snapshot(client, headers, world_id):
    response = client.post(SNAPSHOTS, json={"world_id": world_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["snapshot_id"]


def test_create_snapshot_requires_world_access(snapshot_client):
    client, headers = snapshot_client
    _create_snapshot(client, headers["owner"], "owner-world")
    response = client.post(SNAPSHOTS, json={"world_id": "owner-world"}, headers=headers["other"])
    assert response.status_code == 404


def test_filtered_snapshot_list_requires_world_access(snapshot_client):
    client, headers = snapshot_client
    snapshot_id = _create_snapshot(client, headers["owner"], "owner-world")
    params = {"world_id": "owner-world"}
    response = client.get(SNAPSHOTS, params=params, headers=headers["owner"])
    assert response.status_code == 200
    assert [row["snapshot_id"] for row in response.json()] == [snapshot_id]
    response = client.get(SNAPSHOTS, params=params, headers=headers["other"])
    assert response.status_code == 404


def test_unfiltered_snapshot_list_returns_only_accessible_worlds(snapshot_client):
    client, headers = snapshot_client
    owner_id = _create_snapshot(client, headers["owner"], "owner-world")
    other_id = _create_snapshot(client, headers["other"], "other-world")
    for username, snapshot_id in (("owner", owner_id), ("other", other_id)):
        response = client.get(SNAPSHOTS, headers=headers[username])
        assert response.status_code == 200
        assert [row["snapshot_id"] for row in response.json()] == [snapshot_id]


@pytest.mark.parametrize("create_new_world", [True, False], ids=["branch", "overwrite"])
def test_restore_snapshot_requires_world_access(snapshot_client, create_new_world):
    client, headers = snapshot_client
    snapshot_id = _create_snapshot(client, headers["owner"], "owner-world")
    payload = {"snapshot_id": snapshot_id, "create_new_world": create_new_world}
    response = client.post(f"{SNAPSHOTS}/restore", json=payload, headers=headers["owner"])
    assert response.status_code == 200, response.text
    assert response.json()["is_branch"] is create_new_world
    response = client.post(f"{SNAPSHOTS}/restore", json=payload, headers=headers["other"])
    assert response.status_code == 404


@pytest.mark.parametrize("foreign_side", ["snapshot_a", "snapshot_b"])
def test_compare_snapshots_requires_access_to_both_worlds(snapshot_client, foreign_side):
    client, headers = snapshot_client
    owner_id = _create_snapshot(client, headers["owner"], "owner-world")
    other_id = _create_snapshot(client, headers["other"], "other-world")
    params = {"snapshot_a": other_id, "snapshot_b": other_id}
    response = client.get(f"{SNAPSHOTS}/compare", params=params, headers=headers["other"])
    assert response.status_code == 200, response.text
    params[foreign_side] = owner_id
    response = client.get(f"{SNAPSHOTS}/compare", params=params, headers=headers["other"])
    assert response.status_code == 404
