"""Runs the claim cases of cases.json through the real SentenceBySentenceReview (build log #55) on local gemma4.
Usage (repo root): uv run python -I planning/experiments/claim_classifier/run_sentence_review.py
Writes results_sentence_gemma.jsonl and prints a summary."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from planning_system.local_client.review_mode import ReviewPacket  # noqa: E402
from planning_system.local_client.review_mode.reviewer_backends import OneShotReviewerBackend  # noqa: E402
from planning_system.model_calls import load_model_endpoints  # noqa: E402


def packet(case: dict) -> ReviewPacket:
    return ReviewPacket.from_json({
        "review_id": case["id"], "node_title": case["node_title"],
        "node_context_summary": case.get("node_context_summary", ""), "claim_tag": case["claim_tag"],
        "claim_text": case["claim_text"],
        "citations": [{"citation": f"[ref{i}:1-1]", **c} for i, c in enumerate(case["citations"])]})


def main() -> None:
    cases = [c for c in json.loads((HERE / "cases.json").read_text()) if c["type"] != "summary"]
    backend = OneShotReviewerBackend(load_model_endpoints().create("local_gemma4"))
    tp = fn = ff = tn = 0
    with (HERE / "results_sentence_gemma.jsonl").open("w") as out:
        for case in cases:
            start = time.time()
            try:
                verdict = backend.review(packet(case))
                passed, reason = verdict.passed, verdict.reason
            except Exception as error:
                passed, reason = None, f"ERR {error!r}"
            row = {"case": case["id"], "defect": case["defect"], "passed": passed, "reason": reason,
                   "latency_s": round(time.time() - start, 2)}
            out.write(json.dumps(row) + "\n")
            print(row, flush=True)
            if case["defect"] != "none":
                tp, fn = tp + (passed is False), fn + (passed is not False)
            else:
                tn, ff = tn + (passed is True), ff + (passed is not True)
    print(f"defects caught {tp}/{tp + fn}; good claims passed {tn}/{tn + ff} (false fails {ff})")


if __name__ == "__main__":
    main()
