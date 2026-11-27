"""Join checks + trace metrics + judge output per trial; print tables. python3 aggregate.py [--judge]"""
import json, subprocess, sys
from collections import defaultdict
from pathlib import Path
E = Path(__file__).parent
sys.path.insert(0, str(E))
import trace

rows = []
for chk in sorted((E / "logs").glob("*.check.json")):
    tag = chk.name[:-len(".check.json")]
    log = E / "logs" / f"{tag}.jsonl"
    r = json.loads(chk.read_text())
    r.update(trace.metrics(str(log)))
    jf = E / "logs" / f"{tag}.judge.json"
    if "--judge" in sys.argv and not jf.exists():
        j = subprocess.run([sys.executable, str(E / "judge.py"), str(log)], capture_output=True, text=True)
        jf.write_text(j.stdout or json.dumps({"error": j.stderr[-300:]}))
    if jf.exists():
        try:
            r["judge"] = json.loads(jf.read_text())
        except Exception:
            r["judge"] = {}
    r["stops"] = sum(1 for e in r.get("guard_log", []) if e["event"] == "stop_injected")
    r["refused"] = sum(1 for e in r.get("guard_log", []) if e["event"] == "refused")
    r.pop("guard_log", None)
    rows.append(r)
(E / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

def agg(group):
    n = len(group)
    j = [g.get("judge") or {} for g in group]
    f = lambda k: sum(1 for g in group if g.get(k))
    avg = lambda k: round(sum((g.get(k) or 0) for g in group) / n, 2)
    return {"n": n, "root_fixed": f"{f('root_fixed')}/{n}", "symptom_patch": f"{f('symptom_patch')}/{n}",
            "cycles": avg("edit_run_cycles"), "code_edits": avg("code_edits"),
            "hyp_before_edit": round(sum(x.get("hypotheses_before_first_code_edit", 0) for x in j) / n, 2),
            "first_hyp_root": f"{sum(1 for x in j if x.get('first_hypothesis_was_root_cause'))}/{n}",
            "first_edit_wrong": f"{sum(1 for x in j if x.get('first_code_edit_targets_wrong_first_guess'))}/{n}",
            "stops": sum(g["stops"] for g in group), "cost_usd": avg("cost_usd"), "dur_s": avg("duration_s"),
            "out_tok": int(avg("out_tokens")), "in_tok": int(avg("in_tokens"))}

by_c, by_pc = defaultdict(list), defaultdict(list)
for r in rows:
    by_c[r["cond"]].append(r)
    by_pc[(r["project"], r["cond"])].append(r)
cols = ["n", "root_fixed", "symptom_patch", "cycles", "code_edits", "hyp_before_edit", "first_hyp_root", "first_edit_wrong", "stops", "cost_usd", "dur_s", "out_tok", "in_tok"]
print("| cond | " + " | ".join(cols) + " |\n|" + "---|" * (len(cols) + 1))
for c in sorted(by_c):
    a = agg(by_c[c]); print(f"| {c} | " + " | ".join(str(a[k]) for k in cols) + " |")
print("\n| project | cond | root_fixed | symptom_patch | cycles | hyp_before_edit | first_edit_wrong |\n|---|---|---|---|---|---|---|")
for (p, c) in sorted(by_pc):
    a = agg(by_pc[(p, c)]); print(f"| {p} | {c} | {a['root_fixed']} | {a['symptom_patch']} | {a['cycles']} | {a['hyp_before_edit']} | {a['first_edit_wrong']} |")
