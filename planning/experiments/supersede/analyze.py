"""Scores results_<backend>.jsonl (last row per backend/variation/case).
A: per (statement, quote) pair: changes caught, missed, false alarms. B: holds/broken-page correct."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
QUOTE_IDS = list(json.loads((HERE / "cases.json").read_text())["cited_quotes"])


def last_rows(backend):
    rows = {}
    path = HERE / f"results_{backend}.jsonl"
    for line in (path.read_text().splitlines() if path.exists() else []):
        r = json.loads(line)
        rows[(r["variation"], r["case"])] = r
    return rows


def main():
    for backend in sys.argv[1:] or ["gemma", "haiku"]:
        rows = last_rows(backend)
        print(f"\n## {backend}\n")
        print("| variation | result | errors | median calls | median s |\n|---|---|---|---|---|")
        details = []
        for variation in sorted({v for v, _ in rows}):
            rs = [r for (v, _), r in rows.items() if v == variation]
            errors = sum(1 for r in rs if r["error"])
            ok = [r for r in rs if not r["error"]]
            if variation.startswith("Q"):
                caught = sum(len(set(r["got"]) & set(r["expected"])) for r in ok)
                total = sum(len(r["expected"]) for r in ok)
                false = sum(len(set(r["got"]) - set(r["expected"])) for r in ok)
                result = f"changes caught {caught}/{total}, false alarms {false}/{len(ok) * len(QUOTE_IDS) - total}"
                for r in ok:
                    for q in sorted(set(r["expected"]) - set(r["got"])):
                        details.append(f"{variation} {r['case']} MISSED {q}")
                    for q in sorted(set(r["got"]) - set(r["expected"])):
                        details.append(f"{variation} {r['case']} FALSE {q}")
            else:
                holds_ok = sum(r["got_holds"] == r["expected_holds"] for r in ok)
                broken_ok = sum(r["got_broken"] == r["expected_broken"] for r in ok)
                result = f"holds right {holds_ok}/{len(ok)}, broken-page right {broken_ok}/{len(ok)}"
                for r in ok:
                    if r["got_holds"] != r["expected_holds"] or r["got_broken"] != r["expected_broken"]:
                        details.append(f"{variation} {r['case']} holds {r['got_holds']} (want {r['expected_holds']}) "
                                       f"broken {r['got_broken']} (want {r['expected_broken']}): {r.get('reason')}")
            for r in rs:
                if r["error"]:
                    details.append(f"{variation} {r['case']} ERROR {r['error']}")
            print(f"| {variation} | {result} | {errors} | {median(r.get('calls', 0) for r in rs)} | "
                  f"{median(r['seconds'] for r in rs)} |")
        print()
        for line in details:
            print("- " + line)


if __name__ == "__main__":
    main()
