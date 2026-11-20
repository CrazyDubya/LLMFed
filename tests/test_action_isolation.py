"""Queued actions must not escape their world or their player's control."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from game_service.player_action_handler import PlayerActionHandler
from game_service.world_ticker import WorldTicker
from models.game_models import (
    Base, WorldDB, PlayerDB, PlayerActionDB, GameFederationDB, GameWrestlerDB,
    WrestlerStatsDB, ContractDB, StableDB, ManagerDB, ManagerClientDB, StorylineDB,
    StorylineParticipantDB,
)


@pytest.fixture
def action_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        for world in ("a", "b"):
            db.add_all([
                WorldDB(id=world, name=world),
                GameFederationDB(id=f"fed-{world}", world_id=world, name=world),
                GameWrestlerDB(id=f"w-{world}", world_id=world, name=world),
                WrestlerStatsDB(wrestler_id=f"w-{world}", power=57),
                StableDB(id=f"stable-{world}", world_id=world, federation_id=f"fed-{world}", name=world),
                ManagerDB(id=f"manager-{world}", world_id=world, name=world),
                ManagerClientDB(id=f"bond-{world}", world_id=world,
                                manager_id=f"manager-{world}", client_wrestler_id=f"w-{world}"),
                StorylineDB(id=f"story-{world}", world_id=world, federation_id=f"fed-{world}", name=world),
            ])
        db.add(PlayerDB(id="player", user_id="user", world_id="b", player_type="promoter", federation_id="fed-b"))
        db.commit()
        yield db
    engine.dispose()


CASES = [
    ("train", {"wrestler_id": "w-a", "stat": "power"}),
    ("sign_wrestler", {"wrestler_id": "w-a", "federation_id": "fed-b"}),
    ("sign_wrestler", {"wrestler_id": "w-b", "federation_id": "fed-a"}),
    ("book_show", {"federation_id": "fed-a"}),
    ("cut_promo", {"wrestler_id": "w-a"}),
    ("cut_promo", {"wrestler_id": "w-b", "target_wrestler_id": "w-a"}),
    ("request_match", {"wrestler_id": "w-a"}),
    ("open_challenge", {"wrestler_id": "w-a"}),
    ("form_stable", {"leader_id": "w-a", "founding_member_ids": ["w-b"]}),
    ("form_stable", {"leader_id": "w-b", "founding_member_ids": ["w-a"]}),
    ("form_stable", {"leader_id": "w-b", "manager_id": "manager-a"}),
    ("join_stable", {"stable_id": "stable-a", "wrestler_id": "w-b"}),
    ("join_stable", {"stable_id": "stable-b", "wrestler_id": "w-a"}),
    ("leave_stable", {"stable_id": "stable-a", "wrestler_id": "w-b"}),
    ("dissolve_stable", {"stable_id": "stable-a"}),
    ("assign_manager", {"manager_id": "manager-a", "client_wrestler_id": "w-b"}),
    ("assign_manager", {"manager_id": "manager-b", "client_wrestler_id": "w-a"}),
    ("create_manager", {"name": "New", "federation_id": "fed-a"}),
    ("remove_manager", {"bond_id": "bond-a"}),
    ("create_storyline", {"wrestler_ids": ["w-b", "w-a"]}),
    ("create_storyline", {"wrestler_ids": ["w-b", "w-b"], "federation_id": "fed-a"}),
    ("advance_storyline", {"storyline_id": "story-a", "heat_boost": 10}),
]


@pytest.mark.parametrize("kind,data", CASES)
def test_handler_rejects_foreign_targets(action_db, kind, data):
    if kind in ("train", "cut_promo", "request_match", "open_challenge"):
        action_db.get(PlayerDB, "player").player_type = "wrestler"
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a, **kw: None)
    with pytest.raises(ValueError, match="not found in this world"):
        handler.execute(PlayerActionDB(world_id="b", player_id="player", action_type=kind, action_data=data))
    assert action_db.query(WrestlerStatsDB).filter_by(wrestler_id="w-a").one().power == 57
    assert action_db.query(ContractDB).count() == 0


@pytest.mark.parametrize("target", ["w-a", "missing"])
def test_http_rejects_foreign_or_missing_train(action_db, monkeypatch, target):
    action_db.get(PlayerDB, "player").player_type = "wrestler"
    monkeypatch.setitem(app.dependency_overrides, get_db_sync, lambda: action_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="user"))
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/game/worlds/b/actions", json={
            "action_type": "train", "action_data": {"wrestler_id": target, "stat": "power"},
        })
    assert response.status_code == 400, response.text
    assert "not found in this world" in response.json()["message"]
    assert action_db.query(PlayerActionDB).count() == 0


def test_train_only_owned_wrestler(action_db):
    player = action_db.get(PlayerDB, "player")
    player.player_type = "wrestler"
    player.wrestler_id = "other"
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    with pytest.raises(ValueError, match="control"):
        handler.execute(PlayerActionDB(world_id="b", player_id=player.id, action_type="train",
                                       action_data={"wrestler_id": "w-b", "stat": "power"}))


def test_train_owned_wrestler(action_db):
    player = action_db.get(PlayerDB, "player")
    player.player_type = "wrestler"
    player.wrestler_id = "w-b"
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    result = handler.execute(PlayerActionDB(world_id="b", player_id=player.id, action_type="train",
                                           action_data={"wrestler_id": "w-b", "stat": "power"}))
    assert result["new"] > 57


def test_empty_train_rejected(action_db):
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    with pytest.raises(ValueError):
        handler.execute(PlayerActionDB(world_id="b", player_id="player", action_type="train", action_data={}))


@pytest.mark.parametrize("kind,data", CASES[:2])
def test_legacy_queued_actions_fail_without_mutation(action_db, kind, data):
    if kind == "train":
        action_db.get(PlayerDB, "player").player_type = "wrestler"
    action = PlayerActionDB(world_id="b", player_id="player", action_type=kind, action_data=data)
    action_db.add(action)
    action_db.commit()
    WorldTicker(action_db, "b")._process_player_actions()
    action_db.commit()
    assert action.status == "failed"
    assert "not found in this world" in action.result["error"]
    assert action_db.query(WrestlerStatsDB).filter_by(wrestler_id="w-a").one().power == 57
    assert action_db.query(ContractDB).count() == 0


@pytest.mark.parametrize("kind,data", [
    ("book_show", {"federation_id": "fed-b"}),
    ("dissolve_stable", {"stable_id": "stable-b"}),
    ("advance_storyline", {"storyline_id": "story-b", "heat_boost": 20}),
    ("remove_manager", {"bond_id": "bond-b"}),
])
def test_promoter_cannot_manage_another_federation(action_db, kind, data):
    action_db.get(ManagerDB, "manager-b").federation_id = "fed-b"
    action_db.get(PlayerDB, "player").federation_id = "other-fed"
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    with pytest.raises(ValueError, match="control this federation"):
        handler.execute(PlayerActionDB(world_id="b", player_id="player", action_type=kind, action_data=data))


def test_http_allows_valid_signing(action_db, monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_db_sync, lambda: action_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: TokenData(user_id="user"))
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/game/worlds/b/actions", json={
            "action_type": "sign_wrestler", "action_data": {"wrestler_id": "w-b", "federation_id": "fed-b"},
        })
    assert response.status_code == 202, response.text
    WorldTicker(action_db, "b")._process_player_actions()
    assert action_db.query(PlayerActionDB).one().status == "completed"
    assert action_db.query(ContractDB).one().world_id == "b"


def test_action_world_must_match_handler(action_db):
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    with pytest.raises(ValueError, match="Action not found in this world"):
        handler.execute(PlayerActionDB(world_id="a", player_id="player", action_type="train", action_data={}))


@pytest.mark.parametrize("local_storyline", [False, True])
def test_promo_only_heats_storyline_in_action_world(action_db, local_storyline):
    player = action_db.get(PlayerDB, "player")
    player.player_type = "wrestler"
    player.wrestler_id = "w-b"
    action_db.add(GameWrestlerDB(id="rival", world_id="b", name="Rival"))
    foreign = action_db.get(StorylineDB, "story-a")
    local = action_db.get(StorylineDB, "story-b")
    foreign.heat = local.heat = 30
    for story in ([foreign, local] if local_storyline else [foreign]):
        for wrestler_id in ("w-b", "rival"):
            action_db.add(StorylineParticipantDB(storyline_id=story.id, wrestler_id=wrestler_id))
    action_db.commit()
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a, **kw: None)
    result = handler.execute(PlayerActionDB(
        world_id="b", player_id="player", action_type="cut_promo",
        action_data={"wrestler_id": "w-b", "target_wrestler_id": "rival"},
    ))
    assert foreign.heat == 30
    if local_storyline:
        assert local.heat == 30 + result["storyline_heat_boost"]
    else:
        assert "storyline_heat_boost" not in result


@pytest.mark.parametrize("field,kind", [("wrestler_ids", "create_storyline"), ("founding_member_ids", "form_stable")])
@pytest.mark.parametrize("ids", [[], ["w-b"] * 100, ["w-b", "missing"], ["w-b", "w-a"]])
def test_list_validation_uses_single_scoped_query(action_db, field, kind, ids):
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "FROM game_wrestlers" in statement:
            statements.append((statement, parameters))

    event.listen(action_db.bind, "before_cursor_execute", record)
    try:
        action = PlayerActionDB(world_id="b", player_id="player", action_type=kind, action_data={field: ids})
        if "missing" in ids or "w-a" in ids:
            with pytest.raises(ValueError, match="Wrestler not found in this world"):
                handler.validate(action)
        else:
            handler.validate(action)
    finally:
        event.remove(action_db.bind, "before_cursor_execute", record)
    assert len(statements) == (1 if ids else 0)
    if ids:
        assert "world_id =" in statements[0][0]
        assert statements[0][1].count("w-b") == 1


def test_invalid_role_rejected_before_loading_targets(action_db):
    handler = PlayerActionHandler(action_db, action_db.get(WorldDB, "b"), lambda *a: None)
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(action_db.bind, "before_cursor_execute", record)
    try:
        with pytest.raises(ValueError, match="control this wrestler"):
            handler.validate(PlayerActionDB(world_id="b", player_id="player", action_type="train",
                                            action_data={"wrestler_id": "w-b"}))
    finally:
        event.remove(action_db.bind, "before_cursor_execute", record)
    assert not any("FROM game_wrestlers" in statement for statement in statements)
