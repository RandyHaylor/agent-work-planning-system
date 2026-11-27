"""Claim-classifier experiment (DISCUSSION-2026-11-26 section 1, option B).

Compares two reviewer prompts on cases.json with Haiku via the claude CLI:
  A = baseline reviewer: one verdict per content item (what review does today)
  B = classifier first: split the text into sentences, label each as user claim /
      technical claim / none, then fail on any uncited or mismatched claim sentence.

Usage: python3 run.py [concurrency]    -> raw/<cond>_<id>.json, scores.json
"""
import concurrent.futures as cf
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)
CASES = json.loads((HERE / "cases.json").read_text())

DEFECTS = ("none, adds_detail, contradicts, multi_sentence_uncited, mislabelled_note, "
           "wrong_origin, summary_uncited")

RULES = (
    "Rules: a 'requirement' or 'decision' needs a user quote: origin user_exchange, or proposal_response "
    "(an approval such as 'yes' or 'A' is fine only if the pre_text shows the question or proposal it answers). "
    "A 'technical' or "
    "'documentation' claim needs a document citation that says it. A 'plan' needs a user or document citation. "
    "A 'note' must make no requirement or technical claim and needs no citation. A claim is unsupported if the "
    "claim adds detail the quote does not say, or contradicts it. Every claim sentence needs its own support."
)

BASE_TAIL = f'Reply with JSON only: {{"verdict": "pass" or "fail", "defect": one of [{DEFECTS}], "reason": "<short>"}}'

CLASSIFY_TAIL = (
    "Work in two steps. Step 1: split the claim text into sentences and label each sentence "
    "'user_claim' (states what the user wants or decided), 'technical_claim' (states a fact about a "
    "technology or document) or 'none' (process, status or question talk). Step 2: judge each labelled "
    "sentence against the citations and the node's claim tag. Fail if any user_claim or technical_claim "
    "sentence is unsupported, uncited, or tagged wrong.\n"
    f'Reply with JSON only: {{"sentences": [{{"text": "...", "label": "..."}}], "verdict": "pass" or "fail", '
    f'"defect": one of [{DEFECTS}], "reason": "<short>"}}'
)


def describe(case):
    if case["type"] == "summary":
        cited = "\n".join(f"  - {c}" for c in case["cited_content"]) or "  (none)"
        ancestors = "; ".join(case["ancestor_summaries"]) or "(none)"
        return (
            "CONTENT TYPE: node context summary (passes down to all child nodes).\n"
            f"Node title: {case['node_title']}\n"
            f"Summary to review: {case['node_context_summary']}\n"
            f"Content cited under this node:\n{cited}\n"
            f"Ancestor summaries: {ancestors}\n"
            "Check every claim in the summary is supported by the cited content or ancestor summaries. "
            "A summary claim with no support is summary_uncited."
        )
    cites = json.dumps(case["citations"], ensure_ascii=False, indent=1)
    return (
        "CONTENT TYPE: content item.\n"
        f"Node title: {case['node_title']}\nNode context: {case['node_context_summary']}\n"
        f"Claim tag: {case['claim_tag']}\nClaim text: {case['claim_text']}\n"
        f"Citations: {cites}"
    )


def prompt(cond, case):
    head = "You are the citation reviewer for a requirements ledger.\n" + RULES + "\n\n" + describe(case) + "\n\n"
    return head + (BASE_TAIL if cond == "A" else CLASSIFY_TAIL)


def call(p):
    r = subprocess.run(
        ["claude", "-p", "--model", "haiku", "--output-format", "json", p],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300,
    )
    try:
        return json.loads(r.stdout).get("result", "")
    except Exception:
        return "ERROR " + r.stdout[-300:] + r.stderr[-300:]


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"verdict": "unparsed", "defect": "unparsed", "reason": text[:200]}


def run_one(cond, case):
    out = RAW / f"{cond}_{case['id']}.json"
    if out.exists():
        return json.loads(out.read_text())
    raw = call(prompt(cond, case))
    rec = {"cond": cond, "id": case["id"], "expected": case["expected"], "defect_expected": case["defect"],
           "result": parse(raw), "raw": raw}
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    return rec


def score(recs):
    summary = {}
    for cond in "AB":
        rs = [r for r in recs if r["cond"] == cond]
        ok = sum(r["result"].get("verdict") == r["expected"] for r in rs)
        fp = [r["id"] for r in rs if r["expected"] == "fail" and r["result"].get("verdict") == "pass"]
        fn = [r["id"] for r in rs if r["expected"] == "pass" and r["result"].get("verdict") == "fail"]
        unparsed = [r["id"] for r in rs if r["result"].get("verdict") == "unparsed"]
        summary[cond] = {"n": len(rs), "verdict_correct": ok, "missed_defects(false pass)": fp,
                         "false_fails": fn, "unparsed": unparsed}
    return summary


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    jobs = [(c, case) for c in "AB" for case in CASES]
    with cf.ThreadPoolExecutor(workers) as ex:
        recs = [f.result() for f in cf.as_completed([ex.submit(run_one, c, k) for c, k in jobs])]
    result = score(recs)
    (HERE / "scores.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
