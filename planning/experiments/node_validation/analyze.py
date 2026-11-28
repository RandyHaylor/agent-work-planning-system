"""Summarises results_<backend>.jsonl: per backend x variation, guesses caught, backed sentences wrongly flagged,
neutral sentences flagged, errors, model calls and seconds per node. Uses the last row per (backend, variation,
node). Usage: python -I analyze.py [backend ...]"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent


def main():
    backends = sys.argv[1:] or ["gemma", "haiku"]
    print("| backend | variation | guesses caught | backed wrongly flagged | neutral flagged | errors | "
          "median calls/node | median s/node |")
    print("|---|---|---|---|---|---|---|---|")
    for backend in backends:
        path = HERE / f"results_{backend}.jsonl"
        if not path.exists():
            continue
        rows = {}
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rows[(row["variation"], row["node"])] = row
        for variation in sorted({v for v, _ in rows}):
            rs = [r for (v, _), r in rows.items() if v == variation]
            guesses = sum(len(r["guesses"]) for r in rs)
            caught = sum(len(r["caught"]) for r in rs)
            false = sum(len(r["false_flags"]) for r in rs)
            neutral = sum(len(r["neutral_flags"]) for r in rs)
            errors = sum(1 for r in rs if r["error"])
            print(f"| {backend} | {variation} | {caught}/{guesses} | {false} | {neutral} | {errors} | "
                  f"{median(r['calls'] for r in rs)} | {median(r['seconds'] for r in rs)} |")
    print()
    for backend in backends:
        path = HERE / f"results_{backend}.jsonl"
        if not path.exists():
            continue
        print(f"Misses and false flags ({backend}):")
        nodes = {n["id"]: n for n in json.loads((HERE / "nodes.json").read_text())}
        last = {}
        for line in path.read_text().splitlines():
            row = json.loads(line)
            last[(row["variation"], row["node"])] = row
        for (variation, node_id), r in sorted(last.items()):
            missed = sorted(set(r["guesses"]) - set(r["caught"]))
            for number in missed:
                print(f"  {variation} {node_id} MISSED {number}: {nodes[node_id]['sentences'][number - 1]['text']}")
            for number in r["false_flags"] + r["neutral_flags"]:
                print(f"  {variation} {node_id} FLAGGED {number}: {nodes[node_id]['sentences'][number - 1]['text']}"
                      f"  -- {r['notes'].get(str(number))}")
            if r["error"]:
                print(f"  {variation} {node_id} ERROR {r['error']}")


if __name__ == "__main__":
    main()
