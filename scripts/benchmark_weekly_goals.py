"""Run with LLMFED_USE_LLM=0 PYTHONHASHSEED=0 python -m scripts.benchmark_weekly_goals."""

import hashlib
import json
import random
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import Session

from game_service.world_service import create_world
from game_service.world_ticker import WorldTicker
from models.db_models import Base


def output_digest(db, tick_result):
    state = {}
    for table in Base.metadata.sorted_tables:
        rows = db.execute(table.select().order_by(*table.primary_key)).mappings()
        # Ignore wall-clock timestamps, not simulated game dates.
        state[table.name] = [
            {column.name: row[column.name] for column in table.columns
             if not isinstance(column.type, DateTime)}
            for row in rows
        ]
    payload = json.dumps([tick_result, state], sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def benchmark(db):
    random.seed(42)
    id_rng = random.Random(42)
    randint = random.randint
    with patch.object(uuid, "uuid4", side_effect=lambda: uuid.UUID(int=id_rng.getrandbits(128), version=4)):
        with patch.object(random, "randint", side_effect=lambda a, b: 120 if (a, b) == (30, 50) else randint(a, b)):
            world = create_world(db, "Weekly goals benchmark")
        ticker = WorldTicker(db, world.id)
        sql = goal_selects = 0

        def count_sql(conn, cursor, statement, parameters, context, executemany):
            nonlocal sql, goal_selects
            sql += 1
            if statement.startswith("SELECT") and "FROM wrestler_goals" in statement:
                goal_selects += 1

        event.listen(db.bind, "before_cursor_execute", count_sql)
        try:
            start = perf_counter()
            result = ticker.tick(days=28)
            seconds = perf_counter() - start
        finally:
            event.remove(db.bind, "before_cursor_execute", count_sql)

    print(f"28 days: {seconds:.3f} s | {sql:,} SQL statements | {goal_selects:,} goal SELECTs")
    print(f"Output SHA-256: {output_digest(db, result)}")


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{Path(tmp) / 'world.sqlite'}")
        Base.metadata.create_all(engine)
        with Session(engine, autoflush=False) as session:
            benchmark(session)
        engine.dispose()
