"""HTTP regression tests for batched storyline serialization."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from models.db_models import Base
from models.game_models import WorldDB, GameWrestlerDB, StorylineDB, StorylineParticipantDB


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
