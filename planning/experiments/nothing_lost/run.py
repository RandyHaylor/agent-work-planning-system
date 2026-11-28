"""Nothing-lost experiment (build log #60 (2)): does the shipped reviewer fail a requirement/decision whose
restatement drops or weakens a condition, limit, exception or hedge in the cited user quote (or the approved
proposal), and still pass faithful restatements? Runs the REAL review methods (per_sentence and bulk) through the
real local_llm backend on the shared llama.cpp gemma4 server, one call at a time.
Usage (repo root): uv run python -I planning/experiments/nothing_lost/run.py LABEL [per_sentence,bulk]
Appends rows to results_gemma.jsonl tagged with LABEL (e.g. "baseline" before the check, "with_check" after)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from planning_system.local_client.review_mode import ReviewPacket  # noqa: E402
from planning_system.local_client.review_mode.bulk_review import BulkReview  # noqa: E402
from planning_system.local_client.review_mode.reviewer_backends.one_shot_backend import \
    OneShotReviewerBackend  # noqa: E402
from planning_system.local_client.review_mode.sentence_review import SentenceBySentenceReview  # noqa: E402
from planning_system.model_calls import load_model_endpoints  # noqa: E402

CASES = json.loads((HERE / "cases.json").read_text())
METHODS = {"per_sentence": SentenceBySentenceReview, "bulk": BulkReview}


def packet(case: dict) -> ReviewPacket:
    """The packet the server builds for a stored user exchange "<pre_text>\\n<user message>" cited at line 2."""
    claim = f"{case['claim'][:-1]} [ref-u:2-2]."
    return ReviewPacket.from_json({
        "review_id": f"rev-{case['id']}", "node_title": "requirement", "node_context_summary": "",
        "claim_tag": case["tag"], "claim_text": claim,
        "citations": [{"citation": "[ref-u:2-2]", "origin": "user_exchange", "quoted_text": case["user"],
                       "pre_text": case["pre_text"], "full_text": f"{case['pre_text']}\n{case['user']}"}]})


def main() -> None:
    label = sys.argv[1]
    granularities = sys.argv[2].split(",") if len(sys.argv) > 2 else list(METHODS)
    model_call = load_model_endpoints(REPO / "config" / "model_endpoints.json").create("local_gemma4")
    with (HERE / "results_gemma.jsonl").open("a") as out:
        for granularity in granularities:
            backend = OneShotReviewerBackend(model_call).use_review_method(METHODS[granularity]())
            for case in CASES:
                start, row = time.time(), {"label": label, "granularity": granularity, "case": case["id"],
                                           "lost": case["lost"], "error": None}
                try:
                    verdict = backend.review(packet(case))
                    row.update(passed=verdict.passed, reason=verdict.reason)
                except Exception as exc:             # unparseable/unavailable: recorded, scored as an error
                    row["error"] = repr(exc)[:300]
                row["seconds"] = round(time.time() - start, 1)
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
