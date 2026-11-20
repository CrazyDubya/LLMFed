"""HTTP regression tests for show booking."""

import random
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
from core_engine import match_engine, tag_match_simulator
from models.db_models import Base
from models.game_models import (
    GameFederationDB, GameWrestlerDB, MatchDB, MatchParticipantDB, PlayerDB, PromoDB, ShowDB, ShowSegmentDB,
    UserDB, WorldDB, WrestlerStatsDB,
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
        world = WorldDB(name="Booking World", current_game_date="2026-01-04")
        other_world = WorldDB(name="Other World")
        user = UserDB(username="promoter", email="promoter@example.test", password_hash="unused")
        db.add_all([world, other_world, user])
        db.flush()
        federation = GameFederationDB(world_id=world.id, name="Booking Federation")
        wrestlers = [GameWrestlerDB(world_id=world.id, name=f"Wrestler {i}", condition=70) for i in range(5)]
        outsider = GameWrestlerDB(world_id=other_world.id, name="Outsider")
        db.add_all([federation, *wrestlers, outsider])
        db.flush()
        db.add_all(WrestlerStatsDB(wrestler_id=wrestler.id) for wrestler in wrestlers)
        show = ShowDB(world_id=world.id, federation_id=federation.id, name="Booking Show", game_date="2026-01-05")
        db.add_all([show, PlayerDB(user_id=user.id, world_id=world.id, player_type="promoter",
                                   federation_id=federation.id)])
        db.flush()
        show_id = show.id
        world_id = world.id
        roster_ids = [wrestler.id for wrestler in wrestlers]
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
        yield SimpleNamespace(client=client, sessions=sessions, show_id=show_id, world_id=world_id,
                              roster_ids=roster_ids, wrestler_ids=roster_ids[:2], bench_id=roster_ids[2],
                              outsider_id=outsider_id)
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


@pytest.mark.parametrize("legacy_booking", [False, True], ids=["new-booking", "legacy-booking"])
def test_tag_match_simulates_both_pairs(booking_client, monkeypatch, legacy_booking):
    b = booking_client
    wrestlers = b.roster_ids[:4]
    response = b.client.post(f"/game/shows/{b.show_id}/matches", json={
        "match_type": "tag_team",
        "participant_ids": wrestlers,
    })
    assert response.status_code == 201, response.text
    match_id = response.json()["match_id"]
    if legacy_booking:
        with b.sessions.begin() as db:
            for participant in db.get(MatchDB, match_id).participants:
                participant.team = wrestlers.index(participant.wrestler_id)

    rng = random.Random(0)
    monkeypatch.setattr(match_engine, "random", rng)
    monkeypatch.setattr(tag_match_simulator, "random", rng)
    tick = b.client.post(f"/game/worlds/{b.world_id}/tick")
    assert tick.status_code == 200, tick.text

    replay = b.client.get(f"/game/matches/{match_id}/play-by-play")
    assert replay.status_code == 200, replay.text
    actors = {wid for spot in replay.json()["spots"] for wid in (spot["attacker"], spot["defender"]) if wid}
    assert actors == set(wrestlers), f"Expected 4 competitors in play-by-play, got {len(actors)}"

    with b.sessions() as db:
        teams = {p.wrestler_id: p.team for p in db.get(MatchDB, match_id).participants}
    assert teams == dict(zip(wrestlers, [0, 0, 1, 1]))


@pytest.mark.parametrize("count", [2, 3, 5])
def test_book_tag_match_rejects_unsupported_counts(booking_client, count):
    b = booking_client
    response = b.client.post(f"/game/shows/{b.show_id}/matches", json={
        "match_type": "tag_team",
        "participant_ids": b.roster_ids[:count],
    })
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Tag team matches require exactly four wrestlers"
    with b.sessions() as db:
        assert db.query(MatchDB).count() == 0


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


@pytest.mark.parametrize("kind", ["matches", "promos"])
def test_booking_rejects_completed_show(booking_client, kind):
    b = booking_client
    with b.sessions.begin() as db:
        db.get(ShowDB, b.show_id).is_completed = True

    kwargs = ({"json": {"participant_ids": b.wrestler_ids}} if kind == "matches"
              else {"params": {"wrestler_id": b.wrestler_ids[0]}})
    response = b.client.post(f"/game/shows/{b.show_id}/{kind}", **kwargs)
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Cannot book segments on a completed show"

    with b.sessions() as db:
        for model in (ShowSegmentDB, MatchDB, MatchParticipantDB, PromoDB):
            assert db.query(model).count() == 0


@pytest.mark.parametrize("case", ["subset", "empty", "duplicate", "extra", "unknown", "other-show"])
def test_reorder_card_rejects_incomplete_permutation(booking_client, case):
    b = booking_client
    with b.sessions.begin() as db:
        show = db.get(ShowDB, b.show_id)
        other = ShowDB(world_id=show.world_id, federation_id=show.federation_id,
                       name="Other Show", game_date=show.game_date)
        db.add(other)
        db.flush()
        segments = [ShowSegmentDB(show_id=b.show_id, position=i, segment_type="promo") for i in (1, 2)]
        outsider = ShowSegmentDB(show_id=other.id, position=1, segment_type="promo")
        db.add_all([*segments, outsider])
        db.flush()
        first, second = [s.id for s in segments]
        outsider_id = outsider.id
    order = {
        "subset": [second], "empty": [], "duplicate": [first, first],
        "extra": [second, first, "missing"], "unknown": [second, "missing"],
        "other-show": [second, outsider_id],
    }[case]

    response = b.client.patch(f"/game/shows/{b.show_id}/card/order", json={"segment_order": order})
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Segment order must contain every show segment exactly once"
    with b.sessions() as db:
        assert [(s.id, s.position) for s in db.query(ShowSegmentDB).filter_by(show_id=b.show_id)
                .order_by(ShowSegmentDB.position)] == [(first, 1), (second, 2)]
        assert db.get(ShowSegmentDB, outsider_id).position == 1


@pytest.mark.parametrize("count", [0, 2])
def test_reorder_card_full_permutation(booking_client, count):
    b = booking_client
    with b.sessions.begin() as db:
        segments = [ShowSegmentDB(show_id=b.show_id, position=i + 1, segment_type="promo")
                    for i in range(count)]
        db.add_all(segments)
        db.flush()
        order = [s.id for s in reversed(segments)]

    response = b.client.patch(f"/game/shows/{b.show_id}/card/order", json={"segment_order": order})
    assert response.status_code == 200, response.text
    expected = list(zip(order, range(1, count + 1)))
    assert [(s["id"], s["position"]) for s in response.json()["segments"]] == expected
    with b.sessions() as db:
        assert [(s.id, s.position) for s in db.query(ShowSegmentDB).filter_by(show_id=b.show_id)
                .order_by(ShowSegmentDB.position)] == expected


@pytest.mark.parametrize(
    "match_type, count, teams",
    [("singles", 2, [None, None]), ("tag_team", 4, [0, 0, 1, 1])],
    ids=["singles", "tag-team"],
)
def test_booked_match_lists_participants(booking_client, match_type, count, teams):
    b = booking_client
    booked_ids = list(reversed(b.roster_ids[:count]))
    response = b.client.post(f"/game/shows/{b.show_id}/matches",
                             json={"participant_ids": booked_ids, "match_type": match_type})
    assert response.status_code == 201, response.text
    segment = response.json()
    with b.sessions() as db:
        names = {w.id: w.name for w in db.query(GameWrestlerDB)}
    expected = [{"wrestler_id": wid, "name": names[wid], "role": "competitor", "team": team}
                for wid, team in zip(booked_ids, teams)]
    assert segment["participants"] == expected

    card = b.client.get(f"/game/shows/{b.show_id}/card")
    assert card.status_code == 200, card.text
    assert card.json()["segments"] == [segment]

    match = b.client.get(f"/game/matches/{segment['match_id']}")
    assert match.status_code == 200, match.text
    assert match.json()["participants"] == expected


def test_promo_segment_has_no_participants(booking_client):
    b = booking_client
    response = b.client.post(f"/game/shows/{b.show_id}/promos", params={"wrestler_id": b.bench_id})
    assert response.status_code == 201, response.text
    assert response.json()["participants"] == []
