"""Experiment: current reviewer prompt vs sentence-classifier prompt vs summary-review prompt.
Usage: python run_experiment.py {gemma|haiku} [repeats]   -> results_<backend>.jsonl
Run from the repo root (imports planning_system)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from planning_system.local_client.review_mode.review_prompt import build_review_prompt  # noqa: E402
from planning_system.local_client.review_mode.types import ResolvedCitation, ReviewPacket  # noqa: E402
from planning_system.local_client.review_mode.verdict_parser import _balanced_brace_objects_from_end  # noqa: E402

CLASSIFIER_PROMPT = """You check that every claim in a planning item is backed by its citations.
Reply with EXACTLY one JSON object, no markdown fence, nothing before or after.

STEP 1. Split the CLAIM into sentences (a sentence joined by ';' or 'and' that states two separate facts counts as two).
STEP 2. For each sentence decide its type:
  - "user_claim": a requirement, decision, preference or rule about what the system must do or be (only the user can authorise it).
  - "technical_claim": a statement of fact about how a technology, library, protocol or system behaves (needs a document or knowledge_base citation).
  - "none": a note, status, to-do, question or process remark that asserts neither.
STEP 3. For each user_claim or technical_claim, name the citation index that supports EVERY detail of it, or "unsupported".
  - A user_claim is supported only by a user_exchange or proposal_response citation. A brief confirmation ("yes", "A", "ok") supports exactly what the PRE-INPUT CONTEXT question/proposal offered, nothing more.
  - A technical_claim is supported only by a document or knowledge_base citation. A user saying something technical is NOT support for a technical_claim.
  - Any added detail (number, version, extra item, extra behaviour, stronger wording) not in the cited text makes the sentence "unsupported". A sentence that contradicts its citation is "unsupported".
STEP 4. Tag check against CLAIM TAG:
  - note: fails if ANY sentence is user_claim or technical_claim.
  - requirement / decision: must contain at least one user_claim.
  - technical / documentation: must contain at least one technical_claim.
  - plan: any mix.
passed = true only if no claim sentence is "unsupported" and the tag check holds.

Output shape:
{"sentences":[{"text":"...","type":"user_claim|technical_claim|none","support":<index>|"unsupported"|null}],"tag_ok":true|false,"passed":true|false,"reason":"<=20 words, name the failing sentence"}

CLAIM TAG: {tag}
NODE TITLE: {title}
CLAIM:
{claim}

CITATIONS:
{citations}"""

SUMMARY_PROMPT = """You review a planning node's CONTEXT SUMMARY. The summary is passed down to every child node, so it may only
restate what the node's own CITED CONTENT says or what its ANCESTOR SUMMARIES say. It may also describe the node's scope
("this node covers ...") without that being a claim.
Reply with EXACTLY one JSON object, no markdown fence, nothing before or after.

Split the summary into claims. For each, find the cited content item or ancestor summary that states it, or "unsupported".
Any added detail (number, version, product, extra requirement, reason/justification) not stated there is "unsupported".
passed = true only if no claim is unsupported.

Output shape:
{"claims":[{"text":"...","support":"content[<i>]"|"ancestor[<i>]"|"scope"|"unsupported"}],"passed":true|false,"reason":"<=20 words"}

NODE TITLE: {title}
CONTEXT SUMMARY:
{summary}

CITED CONTENT:
{content}

ANCESTOR SUMMARIES:
{ancestors}"""


def _fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def classifier_prompt(case: dict) -> str:
    blocks = []
    for i, c in enumerate(case["citations"]):
        lines = [f"--- citation[{i}] origin={c['origin']} ---"]
        if c.get("pre_text"):
            lines.append(f"PRE-INPUT CONTEXT (what the agent said before the user replied):\n{c['pre_text']}")
        lines.append(f"CITED TEXT:\n{c['quoted_text']}")
        blocks.append("\n".join(lines))
    return _fill(CLASSIFIER_PROMPT, tag=case["claim_tag"], title=case["node_title"], claim=case["claim_text"],
                 citations="\n".join(blocks) or "(no citations)")


def summary_prompt(case: dict) -> str:
    return _fill(SUMMARY_PROMPT, title=case["node_title"], summary=case["node_context_summary"],
                 content="\n".join(f"content[{i}] {t}" for i, t in enumerate(case["cited_content"])),
                 ancestors="\n".join(f"ancestor[{i}] {t}" for i, t in enumerate(case["ancestor_summaries"])))


def current_prompt(case: dict) -> str:
    cits = tuple(ResolvedCitation(f"[ref{i}:1-1]", c["origin"], c["quoted_text"], c.get("pre_text", ""), "")
                 for i, c in enumerate(case["citations"]))
    return build_review_prompt(ReviewPacket(case["id"], case["node_title"], case["node_context_summary"],
                                            case["claim_tag"], case["claim_text"], cits))


def parse_passed(answer: str):
    for cand in [answer.strip(), *_balanced_brace_objects_from_end(answer)]:
        try:
            data = json.loads(cand)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("passed"), bool):
            return data["passed"], data
    return None, None


class Gemma:
    def __init__(self):
        from planning_system.model_calls.endpoint_factory import load_model_endpoints
        from planning_system.model_calls.types import OneShotRequest
        self._call = load_model_endpoints(HERE.parents[2] / "config" / "model_endpoints.json").create("local_gemma4")
        self._req = OneShotRequest

    def ask(self, prompt: str) -> str:
        return self._call.complete(self._req(user_text=prompt, json_output=True, max_tokens=1200,
                                             temperature=0.0)).text


class Haiku:
    def ask(self, prompt: str) -> str:
        out = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "json", "--tools", ""],
                             input=prompt, capture_output=True, text=True, timeout=300)
        return json.loads(out.stdout).get("result", "") if out.stdout.strip() else "ERR " + out.stderr[:300]


def jobs(cases, repeats):
    for case in cases:
        prompts = [("summary_review", summary_prompt(case))] if case["type"] == "summary" else \
            [("current", current_prompt(case)), ("classifier", classifier_prompt(case))]
        for name, prompt in prompts:
            for rep in range(repeats):
                yield case, name, prompt, rep


def run_one(backend, case, name, prompt, rep):
    start = time.time()
    try:
        answer = backend.ask(prompt)
    except Exception as exc:  # record and move on
        answer = f"ERR {exc!r}"
    latency = round(time.time() - start, 2)
    passed, data = parse_passed(answer)
    return {"case": case["id"], "defect": case["defect"], "expected": case["expected"], "prompt": name, "rep": rep,
            "latency_s": latency, "passed": passed, "parsed": data, "raw": answer if data is None else None}


def main():
    which = sys.argv[1]
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    cases = json.loads((HERE / "cases.json").read_text())
    backend = Gemma() if which == "gemma" else Haiku()
    workers = 1 if which == "gemma" else 8
    out = HERE / f"results_{which}.jsonl"
    with out.open("w") as f, ThreadPoolExecutor(workers) as pool:
        for row in pool.map(lambda j: run_one(backend, *j), list(jobs(cases, repeats))):
            row["backend"] = which
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(row["case"], row["prompt"], row["passed"], row["latency_s"], flush=True)


if __name__ == "__main__":
    main()
