"""Benchmark 28 no-LLM ticks for a seeded 120-wrestler world."""

import hashlib
import json
import os
import random
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import DateTime, create_engine, event, select
from sqlalchemy.orm import Session


def run(path: Path):
    from game_service.world_service import create_world
    from game_service.world_ticker import FRIDAY, WorldTicker, get_day_of_week
    from models.db_models import Base

    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    random.seed(42)
    ids = random.Random(42)
    randint = random.randint
    with Session(engine, autoflush=False) as db, patch.object(
        uuid, "uuid4", side_effect=lambda: uuid.UUID(int=ids.getrandbits(128), version=4)
    ):
        with patch.object(random, "randint", side_effect=lambda a, b: 120 if (a, b) == (30, 50) else randint(a, b)):
            world = create_world(db, "Persona benchmark")

        sql = 0
        fridays = []

        @event.listens_for(engine, "before_cursor_execute")
        def count_sql(*_):
            nonlocal sql
            sql += 1

        class MeasuredTicker(WorldTicker):
            def _persona_tick(self, game_date):
                start, before = time.perf_counter(), sql
                super()._persona_tick(game_date)
                if get_day_of_week(game_date) == FRIDAY:
                    fridays.append((time.perf_counter() - start, sql - before))

        ticker = MeasuredTicker(db, world.id)
        sql = 0
        start = time.perf_counter()
        result = ticker.tick(days=28)
        print(f"28 days: {time.perf_counter() - start:.3f} s / {sql:,} SQL")
        print(f"Friday persona ({len(fridays)} Fridays): "
              f"{sum(t for t, _ in fridays):.3f} s / {sum(n for _, n in fridays):,} SQL")
        print("Tick output SHA256:", digest(result))
        tables = {}
        for name, table in sorted(Base.metadata.tables.items()):
            columns = [column for column in table.c if not isinstance(column.type, DateTime)]
            rows = db.execute(select(*columns).order_by(*table.primary_key)).all()
            if rows:
                tables[name] = digest([tuple(row) for row in rows])
        print("Persisted state SHA256 (excluding timestamp columns):", digest(tables))

    engine.dispose()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


if __name__ == "__main__":
    os.environ.pop("LLMFED_USE_LLM", None)
    with TemporaryDirectory() as directory:
        run(Path(directory) / "world.sqlite")
