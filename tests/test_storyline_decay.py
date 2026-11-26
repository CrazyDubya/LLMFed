"""Regression coverage for cold storylines in the daily ticker."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from game_service.storyline_service import progress_storyline
from game_service.world_ticker import WorldTicker
from models.db_models import Base
from models.game_models import ContractDB, GameFederationDB, GameWrestlerDB, StorylineDB, WorldDB


@pytest.fixture
def ticker():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        db.add(WorldDB(id="world", name="Storyline World"))
        db.commit()
        yield WorldTicker(db, "world")
    engine.dispose()


def advance_storylines(ticker, day):
    ticker.world.current_game_date = day
    ticker._advance_storylines()
    ticker.db.commit()


def test_cold_arcs_get_a_week_then_free_npc_slots(ticker, monkeypatch):
    monkeypatch.setattr("game_service.world_ticker.random.random", lambda: 0.0)
    ticker.db.add(GameFederationDB(id="npc", world_id="world", name="NPC Federation"))
    for i in range(2):
        wid = f"wrestler-{i}"
        ticker.db.add(GameWrestlerDB(id=wid, world_id="world", name=wid))
        ticker.db.add(ContractDB(
            world_id="world", wrestler_id=wid, federation_id="npc", start_date="2026-01-01",
        ))
    arcs = [
        StorylineDB(world_id="world", federation_id="npc", name=f"Arc {i}", status=status, heat=1)
        for i, status in enumerate(("brewing", "active", "active"))
    ]
    ticker.db.add_all(arcs)
    ticker.db.commit()

    for days in range(7):
        advance_storylines(ticker, (date(2026, 1, 7) + timedelta(days=days)).isoformat())
        assert [arc.heat for arc in arcs] == [0, 0, 0]
        assert [arc.status for arc in arcs] == ["brewing", "active", "active"]
        assert ticker.events == []

    advance_storylines(ticker, "2026-01-14")

    assert [arc.status for arc in arcs] == ["resolved"] * 3
    assert all(arc.end_date == "2026-01-14" and arc.planned_blowoff for arc in arcs)
    assert len(ticker.events) == 1
    assert ticker.events[0].startswith("New storyline: ")


def test_storylines_with_heat_keep_normal_decay_and_escalation(ticker, monkeypatch):
    monkeypatch.setattr("game_service.world_ticker.random.random", lambda: 0.0)
    brewing = StorylineDB(world_id="world", name="Hot arc", status="brewing", heat=70)
    active = StorylineDB(world_id="world", name="Warm arc", status="active", heat=40)
    ticker.db.add_all([brewing, active])
    ticker.db.commit()

    for days in range(10):
        advance_storylines(ticker, (date(2026, 1, 1) + timedelta(days=days)).isoformat())

    assert (brewing.status, brewing.heat) == ("active", 60)
    assert (active.status, active.heat) == ("active", 30)


def test_reheating_restarts_grace_even_if_next_decay_returns_to_zero(ticker, monkeypatch):
    monkeypatch.setattr("game_service.world_ticker.random.random", lambda: 0.0)
    arc = StorylineDB(world_id="world", name="Revived arc", status="active", heat=0)
    ticker.db.add(arc)
    ticker.db.commit()
    advance_storylines(ticker, "2026-01-01")
    for day in range(2, 8):
        advance_storylines(ticker, f"2026-01-{day:02}")

    progress_storyline(ticker.db, arc, "promo", heat_delta=1)
    ticker.db.commit()
    advance_storylines(ticker, "2026-01-08")
    assert (arc.status, arc.heat) == ("active", 0)

    for day in range(9, 15):
        advance_storylines(ticker, f"2026-01-{day:02}")
    assert arc.status == "active"
    advance_storylines(ticker, "2026-01-15")
    assert arc.status == "resolved"
