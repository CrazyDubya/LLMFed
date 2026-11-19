"""Run with PYTHONHASHSEED=0 python -m scripts.benchmark_weekly_conditioning."""

import os
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.engine import Engine

from game_service import wrestler_lifecycle_service as lifecycle
from game_service.world_ticker import WorldTicker
from scripts import benchmark_friday_persona as benchmark


def run():
    selects = conditioning_selects = 0
    seconds = 0.0

    def count_sql(conn, cursor, statement, parameters, context, executemany):
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    def measured(fn):
        def wrapped(*args, **kwargs):
            nonlocal seconds, conditioning_selects
            start, before = perf_counter(), selects
            try:
                return fn(*args, **kwargs)
            finally:
                seconds += perf_counter() - start
                conditioning_selects += selects - before
        return wrapped

    tick = WorldTicker.tick

    def measured_tick(*args, **kwargs):
        before = selects
        start = perf_counter()
        result = tick(*args, **kwargs)
        print(f"Total tick: {perf_counter() - start:.6f} s / {selects - before} SELECTs")
        return result

    event.listen(Engine, "before_cursor_execute", count_sql)
    try:
        with ExitStack() as stack, TemporaryDirectory() as directory:
            stack.enter_context(patch.object(WorldTicker, "tick", measured_tick))
            for name in ("update_conditioning", "load_conditioning_data"):
                if hasattr(lifecycle, name):
                    stack.enter_context(patch.object(lifecycle, name, measured(getattr(lifecycle, name))))
            benchmark.run(Path(directory) / "world.sqlite")
        print(f"Weekly conditioning: {seconds:.6f} s / {conditioning_selects} SELECTs")
    finally:
        event.remove(Engine, "before_cursor_execute", count_sql)


if __name__ == "__main__":
    os.environ.pop("LLMFED_USE_LLM", None)
    run()
