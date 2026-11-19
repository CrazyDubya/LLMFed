"""Seeded full-world social-post benchmark; run with PYTHONHASHSEED=0."""
import hashlib
import json
import os
import random
import statistics
import sys
import uuid
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.pop('LLMFED_USE_LLM', None)
from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import Session
from models.db_models import Base
from game_service.world_service import create_world
from game_service.world_ticker import WorldTicker
from game_service import social_media_service as social


def run():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    random.seed(42)
    ids = random.Random(42)
    randint = random.randint
    with Session(engine, autoflush=False) as db, patch.object(
        uuid, 'uuid4', side_effect=lambda: uuid.UUID(int=ids.getrandbits(128), version=4)
    ):
        with patch.object(random, 'randint', side_effect=lambda a, b: 120 if (a, b) == (30, 50) else randint(a, b)):
            world = create_world(db, 'Social benchmark')
        ticker = WorldTicker(db, world.id)
        sql = social_sql = 0
        social_seconds = 0.0
        original = social.tick_social_media

        def count(*args):
            nonlocal sql
            sql += 1

        def measured(*args, **kwargs):
            nonlocal social_sql, social_seconds
            before, start = sql, perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                social_seconds += perf_counter() - start
                social_sql += sql - before

        event.listen(engine, 'before_cursor_execute', count)
        with patch.object(social, 'tick_social_media', measured):
            start = perf_counter()
            result = ticker.tick(days=28)
            seconds = perf_counter() - start
        event.remove(engine, 'before_cursor_execute', count)
        state = {}
        for table in Base.metadata.sorted_tables:
            state[table.name] = [
                {c.name: row[c.name] for c in table.columns if not isinstance(c.type, DateTime)}
                for row in db.execute(table.select().order_by(*table.primary_key)).mappings()
            ]
        digest = hashlib.sha256(json.dumps([result, state], sort_keys=True, default=str).encode()).hexdigest()
    engine.dispose()
    return seconds, sql, social_seconds, social_sql, digest


if __name__ == '__main__':
    runs = [run() for _ in range(5)]
    for row in runs:
        print('run:', *row)
    assert len({row[4] for row in runs}) == 1
    print('median tick_s tick_sql social_s social_sql:', *(statistics.median(row[i] for row in runs) for i in range(4)))
    print('SHA256:', runs[0][4])
