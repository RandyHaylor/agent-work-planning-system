"""Supersede experiment (spec 05-spec-reference-supersede.md, DRAFT). Two model-dependent parts, several variations:
A. does a new user statement change an earlier cited quote?  Q1 one session, one turn per quote | Q2 one call, all
   quotes | Q3 one isolated call per quote
B. trial review: does a claim still hold in the new copy of a document?  P1 mapped range only | P2 whole new doc |
   P3 mapped range + whole doc
Usage (repo root): uv run python -I planning/experiments/supersede/run.py {gemma|haiku} Q1,Q2,Q3,P1,P2,P3"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
sys.path.insert(0, str(HERE.parent / "node_validation"))

import run as shared  # noqa: E402  (node_validation sessions: GemmaSession, HaikuSession, json_answer)
from planning_system.server.domain.references.line_range_mapping import map_line_range  # noqa: E402

CASES = json.loads((HERE / "cases.json").read_text())
QUOTES = CASES["cited_quotes"]


def session(backend):
    return shared.GemmaSession() if backend == "gemma" else shared.HaikuSession()


def quote_block(qid):
    q = QUOTES[qid]
    return f'[{qid}] agent asked: "{q["pre_text"]}" / user answered: "{q["text"]}"'


def statement_block(s):
    return f'Agent asked: "{s["pre_text"]}"\nUser answered: "{s["text"]}"'


CHANGE_RULE = ("A statement CHANGES an earlier quote if it replaces, contradicts, narrows, widens, adds to, removes "
               "from, or makes more specific what that quote required. Repeating or agreeing with it, or talking "
               "about something else, is not a change.")

Q1_OPEN = ("You check whether a user's NEW STATEMENT changes any requirement they gave earlier. " + CHANGE_RULE +
           "\nI will show you the earlier quotes one at a time.\n\nNEW STATEMENT:\n{new}\n\n"
           'Reply now with exactly {{"ready": true}}.')
Q_TURN = ('Earlier quote {qid}: {quote}\nDoes the NEW STATEMENT change this earlier quote? '
          'Reply with exactly one JSON object: {{"changes": true|false, "reason": "<=15 words"}}')
Q3_ONE = ("You check whether a user's NEW STATEMENT changes a requirement they gave earlier. " + CHANGE_RULE +
          '\n\nNEW STATEMENT:\n{new}\n\nEARLIER QUOTE: {quote}\nDoes the NEW STATEMENT change the earlier quote? '
          'Reply with exactly one JSON object: {{"changes": true|false, "reason": "<=15 words"}}')
Q2_ALL = ("You check whether a user's NEW STATEMENT changes any requirement they gave earlier. " + CHANGE_RULE +
          '\n\nNEW STATEMENT:\n{new}\n\nEARLIER QUOTES:\n{quotes}\n\nList every earlier quote the new statement '
          'changes. Reply with exactly one JSON object: {{"changed": [{{"quote": "U1", "reason": "<=15 words"}}]}} '
          '(empty list if none).')


def q1(s, sess):
    sess.say(Q1_OPEN.format(new=statement_block(s)))
    return [qid for qid in QUOTES
            if shared.json_answer(sess.say(Q_TURN.format(qid=qid, quote=quote_block(qid))), "changes") is True]


def q2(s, sess):
    answer = sess.say(Q2_ALL.format(new=statement_block(s), quotes="\n".join(quote_block(q) for q in QUOTES)),
                      max_tokens=600)
    return sorted({str(item.get("quote")) for item in shared.json_answer(answer, "changed")})


def q3(s, backend):
    calls, changed = 0, []
    for qid in QUOTES:
        one = session(backend)
        if shared.json_answer(one.say(Q3_ONE.format(new=statement_block(s), quote=quote_block(qid))),
                              "changes") is True:
            changed.append(qid)
        calls += one.calls
    return changed, calls


TRIAL = ("A planning claim cited lines of an OLD copy of a document. A NEW copy of the same source was loaded. "
         "Decide whether the NEW copy still supports every detail of the claim, and whether the NEW copy looks "
         "like an error, login, loading or placeholder page instead of real content.\n\n"
         "CLAIM: {claim}\n\nCITED OLD LINES:\n{old_lines}\n\n{new_part}\n\n"
         'Reply with exactly one JSON object: {{"still_supported": true|false, "broken_page": true|false, '
         '"reason": "<=15 words"}}')


def new_part(case, variation):
    start, end = case["cited"]
    mapped = map_line_range(case["old"], case["new"], start, end)
    new_lines = case["new"].splitlines()
    mapped_text = ("(every cited line was deleted)" if mapped.start is None
                   else "\n".join(new_lines[mapped.start - 1:mapped.end]))
    parts = []
    if variation in ("P1", "P3"):
        parts.append(f"THE SAME LINES IN THE NEW COPY (matched by diff):\n{mapped_text}")
    if variation in ("P2", "P3"):
        parts.append(f"WHOLE NEW COPY:\n{case['new']}")
    return "\n\n".join(parts)


def trial(case, variation, sess):
    start, end = case["cited"]
    old_lines = "\n".join(case["old"].splitlines()[start - 1:end])
    data = shared.find_json_object(sess.say(TRIAL.format(claim=case["claim"], old_lines=old_lines,
                                                          new_part=new_part(case, variation))),
                                   lambda d: "still_supported" in d)
    if data is None:
        raise ValueError("no trial answer")
    return bool(data["still_supported"]), bool(data.get("broken_page")), data.get("reason")


def run_job(backend, variation, case):
    start = time.time()
    row = {"backend": backend, "variation": variation, "case": case["id"], "error": None}
    try:
        if variation in ("Q1", "Q2"):
            sess = session(backend)
            got = (q1 if variation == "Q1" else q2)(case, sess)
            row.update(expected=sorted(case["changes"]), got=sorted(got), calls=sess.calls)
        elif variation == "Q3":
            got, calls = q3(case, backend)
            row.update(expected=sorted(case["changes"]), got=sorted(got), calls=calls)
        else:
            sess = session(backend)
            holds, broken, reason = trial(case, variation, sess)
            row.update(expected_holds=case["holds"], got_holds=holds, expected_broken=case["broken_page"],
                       got_broken=broken, reason=reason, calls=sess.calls)
    except Exception as exc:
        row["error"] = repr(exc)[:300]
    row["seconds"] = round(time.time() - start, 1)
    return row


def main():
    backend, variations = sys.argv[1], sys.argv[2].split(",")
    jobs = [(backend, v, c) for v in variations
            for c in (CASES["new_statements"] if v.startswith("Q") else CASES["doc_cases"])]
    with (HERE / f"results_{backend}.jsonl").open("a") as out, ThreadPoolExecutor(1 if backend == "gemma" else 8) as pool:
        for row in pool.map(lambda job: run_job(*job), jobs):
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(json.dumps({k: v for k, v in row.items() if k != "reason"}), flush=True)


if __name__ == "__main__":
    main()
