"""Scores results.jsonl: per case set and granularity, defects caught, good items failed, errors, seconds."""
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent


def main():
    rows = [json.loads(line) for line in (HERE / "results.jsonl").read_text().splitlines()]
    groups = defaultdict(list)
    for row in rows:
        groups[(row["set"], row["granularity"])].append(row)
    print("| set | granularity | defects caught | good items failed | errors | median s |")
    print("|---|---|---|---|---|---|")
    for (case_set, granularity), rs in sorted(groups.items()):
        ok = [r for r in rs if not r["error"]]
        bad = [r for r in ok if r["should_fail"]]
        good = [r for r in ok if not r["should_fail"]]
        caught = sum(1 for r in bad if not r["passed"])
        false_fail = sum(1 for r in good if not r["passed"])
        print(f"| {case_set} | {granularity} | {caught}/{len(bad)} | {false_fail}/{len(good)} | "
              f"{len(rs) - len(ok)} | {median(r['seconds'] for r in rs)} |")
    print()
    for r in rows:
        if r["error"] or r["should_fail"] == r.get("passed"):
            what = "ERROR" if r["error"] else ("MISSED" if r["should_fail"] else "FALSE FAIL")
            print(f"- {r['set']} {r['granularity']} {r['case']} {what}: {(r.get('reason') or r['error'] or '')[:160]}")


if __name__ == "__main__":
    main()
