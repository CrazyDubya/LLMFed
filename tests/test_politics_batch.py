"""Locker room stats reads should not scale with roster size."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from game_service.politics_service import update_locker_room_dynamics
from models.db_models import Base
from models.game_models import (
    ContractDB, GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
)


@pytest.mark.parametrize("count,is_active,expected_selects", [
    (0, True, 1), (1, True, 3), (12, True, 3), (12, False, 2),
])
@pytest.mark.parametrize("autoflush", [False, True])
def test_locker_room_select_budget(count, is_active, expected_selects, autoflush):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=autoflush) as db:
        federation = GameFederationDB(id="fed", world_id="world", name="Fed")
        db.add(federation)
        for i in range(count):
            db.add(GameWrestlerDB(
                id=f"w{i}", world_id="world", name=f"Wrestler {i}",
                popularity=85, experience_years=10, morale=80,
                is_active=is_active, creative_influence=17, locker_room_standing="neutral",
            ))
            db.add(ContractDB(
                world_id="world", wrestler_id=f"w{i}", federation_id="fed",
                status="active", start_date="2026-01-01",
            ))
            db.add(WrestlerStatsDB(wrestler_id=f"w{i}", backstage_politics=90, work_ethic=80))
        db.flush()
        selects = []

        def record(conn, cursor, statement, *args):
            if statement.startswith("SELECT"):
                selects.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            update_locker_room_dynamics(db, federation, "2026-01-01")
        finally:
            event.remove(engine, "before_cursor_execute", record)
        assert len(selects) == expected_selects
        assert sum("FROM wrestler_stats" in sql for sql in selects) == bool(count and is_active)
        for wrestler in db.query(GameWrestlerDB).all():
            assert wrestler.locker_room_standing == ("leader" if is_active else "neutral")
            assert wrestler.creative_influence == (100 if is_active else 17)
            assert wrestler.morale == 80
    engine.dispose()


def test_missing_stats_and_excluded_wrestlers():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        federation = GameFederationDB(id="fed", world_id="world", name="Fed")
        db.add(federation)
        for wid, active, status in [
            ("missing", True, "active"), ("inactive", False, "active"),
            ("expired", True, "expired"),
        ]:
            db.add(GameWrestlerDB(
                id=wid, world_id="world", name=wid, is_active=active,
                creative_influence=17, locker_room_standing="neutral", morale=70,
            ))
            db.add(ContractDB(
                world_id="world", wrestler_id=wid, federation_id="fed",
                status=status, start_date="2026-01-01",
            ))
            if wid != "missing":
                db.add(WrestlerStatsDB(wrestler_id=wid, backstage_politics=90))
        db.flush()
        update_locker_room_dynamics(db, federation, "2026-01-01")
        for wrestler in db.query(GameWrestlerDB).all():
            assert (wrestler.creative_influence, wrestler.locker_room_standing, wrestler.morale) == (
                17, "neutral", 70,
            )
    engine.dispose()
