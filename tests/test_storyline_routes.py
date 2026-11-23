"""HTTP regression tests for storyline routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from models.db_models import Base
from models.game_models import (
    WorldDB, GameWrestlerDB, StorylineDB, StorylineParticipantDB, PlayerDB, GameNarrativeLogDB,
)


@pytest.fixture
def storyline_api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(WorldDB(id="story-world", name="Story World"))
        db.add(GameWrestlerDB(id="hero", world_id="story-world", name="The Hero"))
        db.add(GameWrestlerDB(id="villain", world_id="story-world", name="The Villain"))
        db.commit()

    def get_db():
        with sessions() as db:
            yield db

    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_sync] = get_db
    app.dependency_overrides[get_current_user] = lambda: TokenData(user_id="story-user")
    try:
        yield TestClient(app, base_url="http://localhost", raise_server_exceptions=False), sessions, engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        engine.dispose()


@pytest.mark.parametrize("count,with_participants", [(0, False), (1, False), (5, False), (1, True), (5, True)])
def test_list_storylines_batches_participants(storyline_api, count, with_participants):
    client, sessions, engine = storyline_api
    with sessions() as db:
        for index in range(count):
            storyline_id = f"story-{index}"
            db.add(StorylineDB(id=storyline_id, world_id="story-world", name=f"Story {index}", heat=60 + index))
            if with_participants:
                db.add(StorylineParticipantDB(
                    storyline_id=storyline_id, wrestler_id="hero", role="protagonist",
                ))
        db.commit()

    selects = []

    def count_selects(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = client.get("/game/worlds/story-world/storylines")
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)
    print(f"storylines={count} participants={with_participants} SELECTs={len(selects)}")
    print(f"HTTP {response.status_code} {response.text}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [story["name"] for story in body] == [f"Story {index}" for index in reversed(range(count))]
    for story in body:
        assert story["participants"] == ([{
            "wrestler_id": "hero", "wrestler_name": "The Hero", "role": "protagonist",
        }] if with_participants else [])
    assert len(selects) == (1 if not count else 3 if with_participants else 2)


def test_list_storylines_invalid_limit(storyline_api):
    client, _, _ = storyline_api
    response = client.get("/game/worlds/story-world/storylines?limit=0")
    assert response.status_code == 422


def test_create_storyline_missing_world(storyline_api):
    client, _, _ = storyline_api
    response = client.post("/game/worlds/missing-world/storylines", json={
        "name": "Missing World Story", "wrestler_ids": ["hero", "villain"],
    })
    assert response.status_code == 404, response.text
    assert response.json()["message"] == "World not found"


def test_create_storyline_rejects_wrestler_from_another_world(storyline_api):
    client, sessions, _ = storyline_api
    with sessions.begin() as db:
        db.add(WorldDB(id="other-world", name="Other World"))
        db.add(GameWrestlerDB(id="visitor", world_id="other-world", name="The Visitor"))

    response = client.post("/game/worlds/story-world/storylines", json={
        "name": "Cross-world feud", "description": "A rivalry", "wrestler_ids": ["hero", "villain", "visitor"],
    })
    detail = client.get("/game/wrestlers/visitor")
    assert detail.status_code == 200, detail.text
    print(f"POST HTTP {response.status_code} {response.text}")
    print(f"GET HTTP {detail.status_code} active_storylines={detail.json()['active_storylines']}")
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Wrestler not found in this world"
    assert detail.json()["active_storylines"] == []
    with sessions() as db:
        assert db.query(StorylineDB).count() == 0


def test_create_storyline_returns_saved_body(storyline_api):
    client, sessions, _ = storyline_api
    response = client.post("/game/worlds/story-world/storylines", json={
        "name": "Bad Blood", "description": "A rivalry", "wrestler_ids": ["hero", "villain"],
    })
    with sessions() as db:
        saved = db.query(StorylineDB).one()
        saved_id = saved.id
        assert saved.name == "Bad Blood"
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == saved_id
    assert body["name"] == "Bad Blood"
    assert body["status"] == "brewing"
    assert body["participants"] == [
        {"wrestler_id": "hero", "wrestler_name": "The Hero", "role": "protagonist"},
        {"wrestler_id": "villain", "wrestler_name": "The Villain", "role": "antagonist"},
    ]


@pytest.mark.parametrize("with_participants", [False, True])
def test_update_storyline_returns_saved_status(storyline_api, with_participants):
    client, sessions, _ = storyline_api
    with sessions() as db:
        db.add(StorylineDB(id="story", world_id="story-world", name="Bad Blood"))
        if with_participants:
            db.add(StorylineParticipantDB(storyline_id="story", wrestler_id="hero", role="protagonist"))
        db.commit()
    response = client.patch("/game/storylines/story", json={"status": "climax"})
    with sessions() as db:
        assert db.get(StorylineDB, "story").status == "climax"
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "climax"
    assert response.json()["participants"] == ([{
        "wrestler_id": "hero", "wrestler_name": "The Hero", "role": "protagonist",
    }] if with_participants else [])


def test_update_storyline_missing(storyline_api):
    client, _, _ = storyline_api
    response = client.patch("/game/storylines/missing", json={"status": "climax"})
    assert response.status_code == 404
    assert response.json()["message"] == "Storyline not found"


def test_promo_storyline_news_carries_world_date_and_tick(storyline_api):
    client, sessions, _ = storyline_api
    with sessions() as db:
        world = db.get(WorldDB, "story-world")
        world.current_game_date = "2026-03-14"
        world.current_tick = 72
        db.add(PlayerDB(id="story-player", user_id="story-user", world_id="story-world",
                        player_type="wrestler", wrestler_id="hero"))
        db.add(StorylineDB(id="rivalry", world_id="story-world", name="Rivalry", heat=40))
        db.add_all([
            StorylineParticipantDB(storyline_id="rivalry", wrestler_id="hero", role="protagonist"),
            StorylineParticipantDB(storyline_id="rivalry", wrestler_id="villain", role="antagonist"),
        ])
        db.commit()

    action = client.post("/game/worlds/story-world/actions", json={
        "action_type": "cut_promo",
        "action_data": {"wrestler_id": "hero", "target_wrestler_id": "villain"},
    })
    assert action.status_code == 202, action.text
    tick = client.post("/game/worlds/story-world/tick")
    assert tick.status_code == 200, tick.text
    assert tick.json()["current_game_date"] == "2026-03-15"

    narrative = client.get("/game/worlds/story-world/narrative?limit=500")
    assert narrative.status_code == 200, narrative.text
    storyline_rows = [row for row in narrative.json() if row["event_type"] == "storyline"]
    print(f"HTTP {narrative.status_code} storyline rows: {storyline_rows}")
    assert [row["game_date"] for row in storyline_rows] == ["2026-03-15"]
    with sessions() as db:
        log = db.query(GameNarrativeLogDB).filter_by(event_type="storyline").one()
        assert log.tick == 73
