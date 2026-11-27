"""Summarise results_*.jsonl: defect = positive class (reviewer fails it)."""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = [json.loads(l) for p in sorted(HERE.glob("results_*.jsonl")) for l in p.open()]
groups = defaultdict(list)
for r in rows:
    groups[(r["backend"], r["prompt"])].append(r)

print("| backend | prompt | n | TP | FN | FP (false fail) | TN | unparsed | precision | recall | median latency s |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for (b, p), rs in sorted(groups.items()):
    tp = sum(r["expected"] == "fail" and r["passed"] is False for r in rs)
    fn = sum(r["expected"] == "fail" and r["passed"] is True for r in rs)
    fp = sum(r["expected"] == "pass" and r["passed"] is False for r in rs)
    tn = sum(r["expected"] == "pass" and r["passed"] is True for r in rs)
    un = sum(r["passed"] is None for r in rs)
    prec = f"{tp/(tp+fp):.2f}" if tp + fp else "-"
    missed_unparsed = sum(r["expected"] == "fail" and r["passed"] is None for r in rs)
    rec = f"{tp/(tp+fn+missed_unparsed):.2f}" if tp + fn + missed_unparsed else "-"
    print(f"| {b} | {p} | {len(rs)} | {tp} | {fn} | {fp} | {tn} | {un} | {prec} | {rec} | "
          f"{statistics.median(r['latency_s'] for r in rs):.1f} |")

print("\nMisses / false fails / unparsed (case, backend, prompt, rep, defect, reason):")
for r in rows:
    wrong = r["passed"] is None or (r["passed"] != (r["expected"] == "pass"))
    if wrong:
        reason = (r["parsed"] or {}).get("reason") if r["parsed"] else (r["raw"] or "")[:120]
        print(f"- {r['case']} {r['backend']} {r['prompt']} r{r['rep']} [{r['defect']}] passed={r['passed']}: {reason}")

print("\nPer-defect recall (fails caught / total):")
by = defaultdict(lambda: [0, 0])
for r in rows:
    if r["expected"] == "fail":
        k = (r["backend"], r["prompt"], r["defect"])
        by[k][1] += 1
        by[k][0] += r["passed"] is False
for k, (c, t) in sorted(by.items()):
    print(f"- {k[0]} {k[1]} {k[2]}: {c}/{t}")
