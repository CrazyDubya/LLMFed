"""HTTP regression tests for show booking."""

from types import SimpleNamespace

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
    GameFederationDB, GameWrestlerDB, MatchDB, MatchParticipantDB, PlayerDB, PromoDB, ShowDB, ShowSegmentDB,
    UserDB, WorldDB,
)


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
        other_world = WorldDB(name="Other World")
        user = UserDB(username="promoter", email="promoter@example.test", password_hash="unused")
        db.add_all([world, other_world, user])
        db.flush()
        federation = GameFederationDB(world_id=world.id, name="Booking Federation")
        wrestlers = [GameWrestlerDB(world_id=world.id, name=f"Wrestler {i}") for i in range(3)]
        outsider = GameWrestlerDB(world_id=other_world.id, name="Outsider")
        db.add_all([federation, *wrestlers, outsider])
        db.flush()
        show = ShowDB(world_id=world.id, federation_id=federation.id, name="Booking Show", game_date="2026-01-05")
        db.add_all([show, PlayerDB(user_id=user.id, world_id=world.id, player_type="promoter",
                                   federation_id=federation.id)])
        db.flush()
        show_id = show.id
        wrestler_ids = [wrestler.id for wrestler in wrestlers[:2]]
        bench_id = wrestlers[2].id
        outsider_id = outsider.id
        token = create_access_token({"sub": user.id})

    def override_db_sync():
        with sessions() as db:
            yield db

    async def override_db():
        async with async_sessions() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db_sync, override_db_sync)
    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    client = TestClient(app, base_url="http://localhost", headers={"Authorization": f"Bearer {token}"},
                        raise_server_exceptions=False)
    try:
        yield SimpleNamespace(client=client, sessions=sessions, show_id=show_id, wrestler_ids=wrestler_ids,
                              bench_id=bench_id, outsider_id=outsider_id)
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
    client, show_id, wrestler_ids = booking_client.client, booking_client.show_id, booking_client.wrestler_ids
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


@pytest.mark.parametrize(
    "case, message",
    [
        ("nonexistent", "Wrestlers not found in this world: missing-a, missing-b"),
        ("other-world", "Wrestlers not found in this world"),
        ("duplicate", "Match participants must be distinct"),
        ("outside-winner", "Planned winner must be a match participant"),
    ],
    ids=["nonexistent", "other-world", "duplicate", "outside-winner"],
)
def test_book_match_rejects_invalid_participants(booking_client, case, message):
    b = booking_client
    first, second = b.wrestler_ids
    payload = {
        "nonexistent": {"participant_ids": ["missing-a", "missing-b"]},
        "other-world": {"participant_ids": [first, b.outsider_id]},
        "duplicate": {"participant_ids": [first, first]},
        "outside-winner": {"participant_ids": [first, second], "planned_winner_id": b.bench_id},
    }[case]

    response = b.client.post(f"/game/shows/{b.show_id}/matches", json=payload)
    assert response.status_code == 400, response.text
    assert response.json()["message"].startswith(message)

    card = b.client.get(f"/game/shows/{b.show_id}/card")
    assert card.status_code == 200, card.text
    assert card.json()["segments"] == []
    with b.sessions() as db:
        assert db.query(MatchDB).count() == 0
        assert db.query(MatchParticipantDB).count() == 0


@pytest.mark.parametrize("promo_type", ["worked_shoot", None], ids=["requested-type", "default-type"])
def test_book_promo(booking_client, promo_type):
    b = booking_client
    params = {"wrestler_id": b.wrestler_ids[0]}
    if promo_type is not None:
        params["promo_type"] = promo_type

    response = b.client.post(f"/game/shows/{b.show_id}/promos", params=params)
    assert response.status_code == 201, response.json()["message"]
    segment = response.json()

    with b.sessions() as db:
        show = db.get(ShowDB, b.show_id)
        stored_segment = db.get(ShowSegmentDB, segment["id"])
        promo = db.get(PromoDB, stored_segment.promo_id)
        assert segment["description"] == "Promo segment"
        assert segment["description"] != show.world_id
        assert promo.promo_type == (promo_type or "in_ring")
        assert promo.world_id == show.world_id
