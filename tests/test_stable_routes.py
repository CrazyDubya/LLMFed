"""HTTP regression tests for stables and their members."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from models.core_models import PlayerDB
from models.db_models import Base
from models.game_models import (
    ContractDB, GameFederationDB, GameWrestlerDB, ManagerDB, StableDB, StableMemberDB, WorldDB,
)

USER_ID = "stable-user"


@pytest.fixture
def stable_api(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions.begin() as db:
        for world in ("a", "b"):
            db.add(WorldDB(id=f"world-{world}", name=f"World {world.upper()}"))
            db.add(GameFederationDB(id=f"fed-{world}", world_id=f"world-{world}", name=f"Fed {world}"))
            db.add(PlayerDB(
                user_id=USER_ID, world_id=f"world-{world}",
                player_type="promoter", federation_id=f"fed-{world}",
            ))
        for wid, world in (("a1", "a"), ("a2", "a"), ("a3", "a"), ("b1", "b")):
            db.add(GameWrestlerDB(id=wid, world_id=f"world-{world}", name=f"Wrestler {wid}"))
            db.add(ContractDB(
                world_id=f"world-{world}", federation_id=f"fed-{world}",
                wrestler_id=wid, status="active", start_date="2026-01-01",
            ))

    def get_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, get_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id=USER_ID))
    try:
        with TestClient(app, base_url="http://localhost") as client:
            yield client, sessions
    finally:
        engine.dispose()


def _create_stable(client, leader_id="a1", member_ids=("a1", "a2")):
    return client.post("/game/worlds/world-a/stables", json={
        "name": "The Pack", "leader_id": leader_id, "founding_member_ids": list(member_ids),
    })


def test_list_stables_batches_active_members_and_names(stable_api):
    client, sessions = stable_api
    with sessions.begin() as db:
        db.add(GameFederationDB(id="fed-a2", world_id="world-a", name="Other fed"))
        db.add(ManagerDB(id="manager", world_id="world-a", name="The Mouth", is_active=False))
        for i in range(31):
            stable_id = f"stable-{30 - i:02d}"
            db.add(StableDB(id=stable_id, world_id="world-a", federation_id="fed-a",
                            name=stable_id, manager_id="manager" if i else "missing-manager"))
            for wrestler_id in ("a2", "missing-wrestler", "a1"):
                db.add(StableMemberDB(stable_id=stable_id, wrestler_id=wrestler_id,
                                      is_active=wrestler_id != "a1"))
        for stable_id, world_id, federation_id, is_active in (
            ("empty-stable", "world-a", "fed-a2", True),
            ("inactive-stable", "world-a", "fed-a", False),
            ("out-of-world", "world-b", "fed-b", True),
        ):
            db.add(StableDB(id=stable_id, world_id=world_id, federation_id=federation_id,
                            name=stable_id, is_active=is_active))

    selects = []

    def count_selects(_conn, _cursor, statement, _params, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    engine = sessions.kw["bind"]
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        url = "/game/worlds/world-a/stables"
        response = client.get(url, params={"federation_id": "fed-a"})
        assert response.status_code == 200, response.text
        rows = response.json()
        assert [row["id"] for row in rows] == [f"stable-{i:02d}" for i in range(30, -1, -1)]
        assert rows[0]["manager_name"] is None
        assert all(row["manager_name"] == "The Mouth" for row in rows[1:])
        assert all(
            [(m["wrestler_id"], m["wrestler_name"]) for m in row["members"]]
            == [("a2", "Wrestler a2"), ("missing-wrestler", "Unknown")] for row in rows
        )
        assert len(selects) == 4

        selects.clear()
        response = client.get(url, params={"federation_id": "fed-a2"})
        assert response.status_code == 200, response.text
        [row] = response.json()
        assert (row["id"], row["manager_name"], row["members"]) == ("empty-stable", None, [])
        assert len(selects) == 2

        selects.clear()
        response = client.get(url, params={"federation_id": "absent"})
        assert response.status_code == 200, response.text
        assert response.json() == []
        assert len(selects) == 1
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)


@pytest.mark.parametrize("bad_member", ["ghost", "b1"])
def test_create_stable_rejects_member_outside_world(stable_api, bad_member):
    client, sessions = stable_api
    response = _create_stable(client, member_ids=["a2", bad_member])
    with sessions() as db:
        counts = (db.query(StableDB).count(), db.query(StableMemberDB).count())
    assert (response.status_code, counts) == (400, (0, 0)), response.text
    assert response.json()["message"] == f"Wrestler not found in this world: {bad_member}"


def test_create_stable_rejects_leader_from_other_world(stable_api):
    client, sessions = stable_api
    response = _create_stable(client, leader_id="b1", member_ids=["b1", "a2"])
    with sessions() as db:
        count = db.query(StableDB).count()
    assert (response.status_code, count) == (404, 0), response.text
    assert response.json()["message"] == "Leader wrestler not found"


@pytest.mark.parametrize("bad_member", ["ghost", "b1"])
def test_add_member_rejects_wrestler_outside_world(stable_api, bad_member):
    client, sessions = stable_api
    stable_id = _create_stable(client).json()["id"]
    response = client.post(f"/game/stables/{stable_id}/members", json={"wrestler_id": bad_member})
    with sessions() as db:
        member_ids = {m.wrestler_id for m in db.query(StableMemberDB).filter_by(stable_id=stable_id)}
    assert (response.status_code, member_ids) == (400, {"a1", "a2"}), response.text
    assert response.json()["message"] == f"Wrestler not found in this world: {bad_member}"


def test_valid_stable_members_are_accepted(stable_api):
    client, sessions = stable_api
    created = _create_stable(client)
    assert created.status_code == 201, created.text
    added = client.post(f"/game/stables/{created.json()['id']}/members", json={"wrestler_id": "a3"})
    assert added.status_code == 201, added.text
    with sessions() as db:
        member_ids = {m.wrestler_id for m in db.query(StableMemberDB)}
    assert member_ids == {"a1", "a2", "a3"}


def test_member_can_rejoin_stable(stable_api):
    client, sessions = stable_api
    url = f"/game/stables/{_create_stable(client).json()['id']}/members"
    added = client.post(url, json={"wrestler_id": "a3", "role": "recruit"})
    assert added.status_code == 201, added.text
    assert client.delete(f"{url}/a3").status_code == 204
    with sessions.begin() as db:
        member = db.query(StableMemberDB).filter_by(wrestler_id="a3").one()
        assert member.is_active is False
        assert member.left_date is not None
        db.get(WorldDB, "world-a").current_game_date = "2026-01-05"
    rejoined = client.post(url, json={"wrestler_id": "a3", "role": "enforcer"})
    assert rejoined.status_code == 201, rejoined.text
    assert rejoined.json() == {"id": added.json()["id"], "wrestler_id": "a3", "role": "enforcer"}
    with sessions() as db:
        member = db.query(StableMemberDB).filter_by(wrestler_id="a3").one()
        assert member.is_active is True
        assert member.left_date is None
        assert member.joined_date == "2026-01-05"
        assert (member.loyalty, member.influence) == (65, 30)


def test_active_member_still_conflicts(stable_api):
    client, sessions = stable_api
    stable_id = _create_stable(client).json()["id"]
    response = client.post(f"/game/stables/{stable_id}/members", json={"wrestler_id": "a2"})
    assert response.status_code == 409, response.text
    assert response.json()["message"] == "Database constraint violation"
    with sessions() as db:
        assert db.query(StableMemberDB).filter_by(wrestler_id="a2").count() == 1


@pytest.mark.parametrize("new_role", ["member", "lieutenant", "enforcer", "recruit"])
@pytest.mark.parametrize("inactive_leader", [False, True])
def test_cannot_demote_last_active_leader(stable_api, new_role, inactive_leader):
    client, sessions = stable_api
    stable_id = _create_stable(client).json()["id"]
    if inactive_leader:
        with sessions.begin() as db:
            db.add(StableMemberDB(
                stable_id=stable_id, wrestler_id="a3", role="leader", is_active=False,
            ))
    response = client.patch(
        f"/game/stables/{stable_id}/members/a1/role", json={"new_role": new_role},
    )
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Cannot demote the stable's only active leader"
    with sessions() as db:
        leader = db.query(StableMemberDB).filter_by(stable_id=stable_id, wrestler_id="a1").one()
        assert leader.role == "leader"
        assert db.get(StableDB, stable_id).is_active is True


def test_leadership_transfer_and_role_changes(stable_api):
    client, sessions = stable_api
    stable_id = _create_stable(client).json()["id"]
    url = f"/game/stables/{stable_id}/members"
    for wrestler_id, role in (("a1", "leader"), ("a2", "leader"), ("a1", "member")):
        response = client.patch(f"{url}/{wrestler_id}/role", json={"new_role": role})
        assert response.status_code == 200, response.text
    with sessions() as db:
        roles = {m.wrestler_id: m.role for m in db.query(StableMemberDB).filter_by(stable_id=stable_id)}
        assert roles == {"a1": "member", "a2": "leader"}
    response = client.patch(f"{url}/ghost/role", json={"new_role": "member"})
    assert response.status_code == 404, response.text


def test_can_demote_leader_when_another_active_leader_remains(stable_api):
    client, sessions = stable_api
    stable_id = _create_stable(client).json()["id"]
    with sessions.begin() as db:
        db.query(StableMemberDB).filter_by(stable_id=stable_id, wrestler_id="a2").one().role = "leader"
    response = client.patch(
        f"/game/stables/{stable_id}/members/a1/role", json={"new_role": "member"},
    )
    assert response.status_code == 200, response.text
    with sessions() as db:
        leaders = db.query(StableMemberDB).filter_by(stable_id=stable_id, role="leader", is_active=True).all()
        assert [m.wrestler_id for m in leaders] == ["a2"]
