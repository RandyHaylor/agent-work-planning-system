"""Haiku through the REAL claude_code reviewer backend (persistent headless `claude -p --model haiku` session, no
tools), both granularities, on two agent-written case sets:
  claims       planning/experiments/claim_classifier/cases.json (31 claim cases: 11 good, 20 defective)
  nothing_lost planning/experiments/nothing_lost/cases.json (8 dropped-condition, 5 faithful restatements)
Paid run approved by the user 2026-11-28 ("Yes do the paid calls").
Usage (repo root): uv run python -I planning/experiments/haiku_backend/run.py [workers]
Writes results.jsonl; one reviewer session per worker thread."""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "planning" / "experiments" / "nothing_lost"))
sys.path.insert(0, str(REPO / "planning" / "experiments" / "claim_classifier"))

import run as nothing_lost  # noqa: E402  (its packet())
from planning_system.local_client.review_mode.reviewer_backends import ReviewerBackendFactory  # noqa: E402
from run_sentence_review import packet as claim_packet  # noqa: E402

CLAIMS = [c for c in json.loads((REPO / "planning/experiments/claim_classifier/cases.json").read_text())
          if c["type"] != "summary"]
LOST = json.loads((REPO / "planning/experiments/nothing_lost/cases.json").read_text())

_local = threading.local()


def backend(granularity):
    """One persistent Haiku reviewer session per thread and granularity (as one review-mode client would hold)."""
    key = f"b_{granularity}"
    if not hasattr(_local, key):
        setattr(_local, key, ReviewerBackendFactory().create("claude_code", "haiku", granularity))
    return getattr(_local, key)


def jobs():
    for granularity in ("bulk", "per_sentence"):
        for case in CLAIMS:
            yield "claims", granularity, case["id"], case["defect"] != "none", claim_packet(case)
        for case in LOST:
            yield "nothing_lost", granularity, case["id"], bool(case["lost"]), nothing_lost.packet(case)


def run_one(job):
    case_set, granularity, case_id, should_fail, packet = job
    start = time.time()
    row = {"set": case_set, "granularity": granularity, "case": case_id, "should_fail": should_fail, "error": None}
    try:
        verdict = backend(granularity).review(packet)
        row.update(passed=verdict.passed, reason=verdict.reason)
    except Exception as exc:
        row["error"] = repr(exc)[:300]
    row["seconds"] = round(time.time() - start, 1)
    return row


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    with (HERE / "results.jsonl").open("w") as out, ThreadPoolExecutor(workers) as pool:
        for row in pool.map(run_one, list(jobs())):
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(json.dumps({k: row[k] for k in ("set", "granularity", "case", "should_fail", "error")}
                             | {"passed": row.get("passed"), "s": row["seconds"]}), flush=True)


if __name__ == "__main__":
    main()
