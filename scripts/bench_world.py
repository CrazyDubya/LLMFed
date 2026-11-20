"""Deterministic 120-wrestler, 28-day SQL benchmark (no profiler).

Run with PYTHONHASHSEED=0 and LLMFED_USE_LLM unset. Fingerprints include
every persisted table, excluding wall-clock DateTime columns.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import DateTime, create_engine, event, select
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from game_service.world_service import create_world
from game_service.world_ticker import WorldTicker
from game_service import inter_federation_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    random.seed(42)
    ids = random.Random(42)
    engine = create_engine(f"sqlite:///{args.output / 'world.sqlite'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    counts = Counter()
    phase = "outside"

    def sql(conn, cursor, statement, parameters, context, executemany):
        counts["sql"] += 1
        if statement.startswith("SELECT"):
            counts["selects"] += 1
            if phase == "momentum":
                counts["momentum_selects"] += 1
        if phase == "show":
            counts["show_sql"] += 1
        if "count(" in statement and "championships" in statement:
            counts["title_count_sql"] += 1
        if "SELECT" in statement and "wrestler_relationships" in statement:
            counts["rivalry_sql"] += 1

    original_show = WorldTicker._simulate_shows
    show_seconds = 0.0
    original_momentum = inter_federation_service.update_federation_momentum
    momentum_seconds = 0.0

    def momentum(*a, **kw):
        nonlocal phase, momentum_seconds
        previous_phase = phase
        phase = "momentum"
        start = time.perf_counter()
        try:
            return original_momentum(*a, **kw)
        finally:
            momentum_seconds += time.perf_counter() - start
            phase = previous_phase

    def shows(self, *a, **kw):
        nonlocal phase, show_seconds
        phase = "show"
        start = time.perf_counter()
        try:
            return original_show(self, *a, **kw)
        finally:
            show_seconds += time.perf_counter() - start
            phase = "outside"

    randint = random.randint
    with patch("uuid.uuid4", side_effect=lambda: uuid.UUID(int=ids.getrandbits(128))), patch.object(
        WorldTicker, "_simulate_shows", shows,
    ), patch.object(
        inter_federation_service, "update_federation_momentum", momentum,
    ):
        with patch(
            "game_service.world_service.random.randint",
            side_effect=lambda a, b: 120 if (a, b) == (30, 50) else randint(a, b),
        ):
            world = create_world(db, "Profiling world")
        ticker = WorldTicker(db, world.id)
        event.listen(engine, "before_cursor_execute", sql)
        start = time.perf_counter()
        tick_results = ticker.tick(days=28)
        seconds = time.perf_counter() - start
        event.remove(engine, "before_cursor_execute", sql)
        result = dict(seconds=seconds, show_seconds=show_seconds,
                      momentum_seconds=momentum_seconds, **counts)
        print(json.dumps(result, sort_keys=True), flush=True)
        (args.output / "results.json").write_text(json.dumps(result, indent=2))
        fingerprint = {"tick_results": tick_results}
        for table in Base.metadata.sorted_tables:
            columns = [c for c in table.c if not isinstance(c.type, DateTime)]
            rows = [dict(row) for row in db.execute(select(*columns)).mappings()]
            fingerprint[table.name] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
        (args.output / "fingerprint.json").write_text(
            json.dumps(fingerprint, sort_keys=True, indent=2, default=str) + "\n"
        )
        digest = hashlib.sha256((args.output / "fingerprint.json").read_bytes()).hexdigest()
        (args.output / "sha256.txt").write_text(digest + "\n")
        print("sha256=" + digest, flush=True)
    db.close()
    engine.dispose()


if __name__ == "__main__":
    main()
