"""Run alternating seeded benchmarks: python scripts/bench_npc_booking.py BEFORE OUTPUT."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import statistics
import subprocess
import sys
import time
from unittest.mock import patch


def run_one(repo, output):
    sys.path.insert(0, str(repo))
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    from game_service import show_service

    original = show_service.npc_book_card
    calls = []
    active = False
    selects = 0

    def sql(conn, cursor, statement, parameters, context, executemany):
        nonlocal selects
        if active and statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    def book(*args, **kwargs):
        nonlocal active, selects
        active, selects = True, 0
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            calls.append({"seconds": time.perf_counter() - start, "selects": selects})
            active = False

    event.listen(Engine, "before_cursor_execute", sql)
    sys.argv = ["bench_world.py", str(output)]
    with patch.object(show_service, "npc_book_card", book):
        runpy.run_path(str(repo / "scripts/bench_world.py"), run_name="__main__")
    event.remove(Engine, "before_cursor_execute", sql)
    result_path = output / "results.json"
    result = json.loads(result_path.read_text())
    fingerprint = json.loads((output / "fingerprint.json").read_text())

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    result.update(npc_calls=calls, npc_seconds=sum(c["seconds"] for c in calls),
                  npc_selects=sum(c["selects"] for c in calls),
                  tick_hash=digest(fingerprint.pop("tick_results")), state_hash=digest(fingerprint))
    result_path.write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pairs", type=int, default=10)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.run:
        run_one(args.before.resolve(), args.output.resolve())
        return
    args.output.mkdir(parents=True, exist_ok=False)
    after = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONHASHSEED="0", OTEL_SDK_DISABLED="true")
    env.pop("LLMFED_USE_LLM", None)
    results = {"before": [], "after": []}
    for i in range(args.pairs):
        for label, repo in [("before", args.before.resolve()), ("after", after)]:
            output = args.output.resolve() / f"{i:02d}-{label}"
            with (args.output / f"{i:02d}-{label}.log").open("w") as log:
                subprocess.run([sys.executable, str(Path(__file__).resolve()), str(repo), str(output), "--run"],
                               cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            result = json.loads((output / "results.json").read_text())
            results[label].append(result)
            print(label, i, result["seconds"], result["npc_seconds"], result["npc_selects"], flush=True)
    for label, rows in results.items():
        for metric in ["seconds", "npc_seconds"]:
            values = [row[metric] for row in rows]
            print(label, metric, dict(min=min(values), median=statistics.median(values),
                                      max=max(values), sd=statistics.stdev(values)))
        print(label, "calls", len(rows[0]["npc_calls"]), "selects", rows[0]["npc_selects"])
    for key in ["tick_hash", "state_hash"]:
        hashes = {row[key] for rows in results.values() for row in rows}
        assert len(hashes) == 1, (key, hashes)
        print(key, next(iter(hashes)))
    (args.output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
