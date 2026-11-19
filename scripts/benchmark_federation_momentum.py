"""Run ten alternating before/after pairs using the same bench_world harness."""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    harness = args.output.resolve() / 'bench_world.py'
    shutil.copyfile(Path(__file__).with_name('bench_world.py'), harness)
    env = dict(os.environ, PYTHONHASHSEED='0')
    env.pop('LLMFED_USE_LLM', None)
    runs = {'before': [], 'after': []}
    hashes = {'before': set(), 'after': set()}
    for pair in range(10):
        for label in ('before', 'after'):
            repo = getattr(args, label).resolve()
            output = args.output.resolve() / f'{pair:02d}-{label}'
            with (args.output / f'{pair:02d}-{label}.log').open('w') as log:
                subprocess.run([sys.executable, str(harness), str(output)],
                               cwd=repo, env=dict(env, PYTHONPATH=str(repo)),
                               stdout=log, stderr=subprocess.STDOUT, check=True)
            runs[label].append(json.loads((output / 'results.json').read_text()))
            hashes[label].add((output / 'sha256.txt').read_text().strip())
            print(f'{pair + 1}/10 {label}: {runs[label][-1]}', flush=True)
    print('| Metric | Version | Median | Min | Max | SD |')
    print('|---|---|---:|---:|---:|---:|')
    for metric in ('momentum_seconds', 'momentum_selects', 'seconds', 'sql', 'selects'):
        for label, results in runs.items():
            values = [r[metric] for r in results]
            print(f'| {metric} | {label} | {statistics.median(values):.6f} | '
                  f'{min(values):.6f} | {max(values):.6f} | '
                  f'{statistics.stdev(values):.6f} |')
    for label, digests in hashes.items():
        print(f'{label} hashes: {sorted(digests)}')
    assert len(hashes['before']) == 1 and hashes['before'] == hashes['after'], 'Output parity failed'


if __name__ == '__main__':
    main()
