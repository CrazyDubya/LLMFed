"""HTTP regression tests for match booking."""

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
from models.game_models import GameFederationDB, GameWrestlerDB, PlayerDB, ShowDB, UserDB, WorldDB


@pytest_asyncio.fixture
async def booking_client(tmp_path, monkeypatch):
    db_path = tmp_path / "booking.db"
    engine = create_engine(f"sqlite:///{db_path}")
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    sessions = sessionmaker(bind=engine)
    async_sessions = async_sessionmaker(bind=async_engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as db:
        world = WorldDB(name="Booking World")
        user = UserDB(username="promoter", email="promoter@example.test", password_hash="unused")
        db.add_all([world, user])
        db.flush()
        federation = GameFederationDB(world_id=world.id, name="Booking Federation")
        wrestlers = [GameWrestlerDB(world_id=world.id, name=f"Wrestler {i}") for i in range(2)]
        db.add_all([federation, *wrestlers])
        db.flush()
        show = ShowDB(world_id=world.id, federation_id=federation.id, name="Booking Show", game_date="2026-01-05")
        db.add_all([show, PlayerDB(user_id=user.id, world_id=world.id, player_type="promoter",
                                   federation_id=federation.id)])
        db.flush()
        show_id = show.id
        wrestler_ids = [wrestler.id for wrestler in wrestlers]
        token = create_access_token({"sub": user.id})

    def override_db_sync():
        with sessions() as db:
            yield db

    async def override_db():
        async with async_sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, override_db_sync)
    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    client = TestClient(app, base_url="http://localhost", headers={"Authorization": f"Bearer {token}"})
    try:
        yield client, show_id, wrestler_ids
    finally:
        client.close()
        await async_engine.dispose()
        engine.dispose()


@pytest.mark.parametrize(
    "match_type, duration, expected",
    [("singles", 30, 30), ("cage", 15, 15), ("singles", None, 15), ("cage", None, 20)],
    ids=["requested-30", "requested-15-for-cage", "singles-default", "cage-default"],
)
def test_book_match_duration(booking_client, match_type, duration, expected):
    client, show_id, wrestler_ids = booking_client
    payload = {"participant_ids": wrestler_ids, "match_type": match_type}
    if duration is not None:
        payload["planned_duration_minutes"] = duration

    response = client.post(f"/game/shows/{show_id}/matches", json=payload)
    assert response.status_code == 201, response.text
    segment = response.json()
    assert segment["planned_duration_minutes"] == expected

    card = client.get(f"/game/shows/{show_id}/card")
    assert card.status_code == 200, card.text
    assert card.json()["segments"] == [segment]
