"""Troubleshooting-protocol experiment (DISCUSSION-2026-11-26 section 3, "latching onto the first idea").

Five small projects with failing unittest suites (projects/*). Each is run for real to capture the
verbatim failure output; Haiku then gets that output plus the project source. Two conditions:
  A = plain: "find the root cause and fix it"
  B = protocol: troubleshooting record (error verbatim, >=3 ranked candidates, each with a cost-to-
      eliminate class, cheapest first, the check that would confirm or rule out each, no fix yet)

Grading is keyword-based against the root-cause keys below (crude; raw outputs are kept for manual reading).
Usage: python3 run.py [concurrency]   -> raw/<cond>_<project>_<rep>.json, scores.json
"""
import concurrent.futures as cf
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROJECTS = HERE / "projects"
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)

# Root causes established by reading the code (not shown to the model).
KEYS = {
    "config_merge": r"shallow|deep merge|recursive|nested|overwrit|replac\w* the (whole )?database|dict\.update|update\(",
    "vendored_api": r"header\s*=\s*false|first (data )?row|skip\w* (the )?first|drop\w* (the )?first|header=True|header default",
    "shared_state": r"class[- ](level )?attribute|class variable|shared (across|between|by all)|mutable|items = \[\]",
    "timezone_day": r"timezone|\bUTC\b|local time|fromtimestamp|\bTZ\b",
    "shadow_secrets": r"shadow|stdlib|standard library|name collision|secrets\.py|same name",
}

PROTOCOL = (
    "Use this troubleshooting record. Do not propose or make a code change yet.\n"
    "1. ERROR: the failing output verbatim (copy the key lines).\n"
    "2. CANDIDATES: at least three possible causes. For each give: likelihood (high/medium/low), "
    "cost to eliminate (by logic / trivial check / costly), and the single check that would confirm or rule it out.\n"
    "3. ORDER: list the eliminations cheapest first (by logic, then trivial checks, then costly ones).\n"
    "4. FIRST CHECK: the exact command or reasoning step you would run first, and what result would confirm the cause.\n"
)

PLAIN = "Find the root cause of the failing tests and fix it. Show the changed code.\n"


def project_text(name):
    d = PROJECTS / name
    parts = []
    for p in sorted(d.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".json", ".csv", ".sh"):
            parts.append(f"--- {p.relative_to(d)} ---\n{p.read_text()}")
    return "\n".join(parts)


def test_output(name):
    r = subprocess.run(["python3", "-m", "unittest", "-v"], cwd=PROJECTS / name,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()


def prompt(cond, name, failing):
    body = (f"A Python project has failing tests. Project: {name}.\n\n"
            f"Failing test output:\n{failing}\n\nProject files:\n{project_text(name)}\n\n")
    return body + (PLAIN if cond == "A" else PROTOCOL)


def call(p):
    r = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "json", p],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=400)
    try:
        return json.loads(r.stdout).get("result", "")
    except Exception:
        return "ERROR " + r.stdout[-300:] + r.stderr[-300:]


def run_one(cond, name, rep, failing):
    out = RAW / f"{cond}_{name}_{rep}.json"
    if out.exists():
        return json.loads(out.read_text())
    answer = call(prompt(cond, name, failing))
    rec = {"cond": cond, "project": name, "rep": rep, "answer": answer,
           "keyword_hit": bool(re.search(KEYS[name], answer, re.I)),
           "n_candidates_guess": len(re.findall(r"(?im)^\s*[-*\d.)]+\s*(candidate|cause|hypothes)", answer))}
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    return rec


def score(recs):
    res = {}
    for cond in "AB":
        rs = [r for r in recs if r["cond"] == cond]
        res[cond] = {"n": len(rs), "root_cause_keyword_hits": sum(r["keyword_hit"] for r in rs),
                     "misses": [f"{r['project']}#{r['rep']}" for r in rs if not r["keyword_hit"]]}
    return res


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    failing = {name: test_output(name) for name in KEYS}
    jobs = [(c, n, r, failing[n]) for c in "AB" for n in KEYS for r in (1, 2)]
    with cf.ThreadPoolExecutor(workers) as ex:
        recs = [f.result() for f in cf.as_completed([ex.submit(run_one, *j) for j in jobs])]
    result = score(recs)
    (HERE / "scores.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
