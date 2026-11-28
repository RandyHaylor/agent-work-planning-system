"""Node-validation experiment (PLAN.md). Scores four ways of finding agent guesses in a whole node.
Usage (repo root): uv run python -I planning/experiments/node_validation/run.py {gemma|haiku} V1,V2,V3,V4
Writes results_<backend>.jsonl (one row per node x variation)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from planning_system.local_client.review_mode.review_turns import (opening_turn, read_sentence_answer,  # noqa: E402
                                                                   sentence_turn)
from planning_system.local_client.review_mode.types import ResolvedCitation, ReviewPacket  # noqa: E402
from planning_system.local_client.review_mode.verdict_parser import find_json_object  # noqa: E402

USER_ORIGINS = ("user_exchange", "proposal_response")
CHILD_CWD = Path(tempfile.mkdtemp(prefix="node-validation-"))   # headless sessions run outside the repo


# --------------------------------------------------------------------------- sessions

class GemmaSession:
    def __init__(self):
        from planning_system.model_calls import ChatMessage, ChatRequest, load_model_endpoints
        self._call = load_model_endpoints().create("local_gemma4")
        self._msg, self._req = ChatMessage, ChatRequest
        self._messages, self.calls = [], 0

    def say(self, text: str, max_tokens: int = 256) -> str:
        self._messages.append(self._msg("user", text))
        answer = self._call.chat(self._req(tuple(self._messages), json_output=True, max_tokens=max_tokens)).text
        self._messages.append(self._msg("assistant", answer))
        self.calls += 1
        return answer


class HaikuSession:
    def __init__(self):
        self._id, self.calls = str(uuid.uuid4()), 0

    def say(self, text: str, max_tokens: int = 256) -> str:
        session = ["--session-id", self._id] if self.calls == 0 else ["--resume", self._id]
        out = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "json", "--tools", "",
                              "--setting-sources", "project", *session], input=text, capture_output=True,
                             text=True, timeout=300, cwd=CHILD_CWD)
        self.calls += 1
        if not out.stdout.strip():
            raise RuntimeError("haiku: " + out.stderr[:300])
        data = json.loads(out.stdout)
        if isinstance(data, list):           # some CLI versions print the whole event list
            data = next((e for e in reversed(data) if isinstance(e, dict) and e.get("type") == "result"), {})
        if data.get("is_error"):
            raise RuntimeError("haiku: " + str(data.get("result"))[:300])
        return data.get("result", "")


# --------------------------------------------------------------------------- rendering

def cited(sentence: dict) -> str:
    text, ref = sentence["text"], sentence["cite"]
    return f"{text[:-1]} [{ref}]{text[-1]}" if ref else text


def references_block(node: dict) -> str:
    blocks = []
    for ref_id, ref in node["references"].items():
        lines = [f"--- [{ref_id}] origin={ref['origin']} ---"]
        if ref["pre_text"]:
            lines.append(f"PRE-INPUT CONTEXT (what the agent said before the user replied): {ref['pre_text']}")
        lines.append(f"TEXT:\n{ref['text']}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def numbered(node: dict) -> str:
    return "\n".join(f"{i}. {cited(s)}" for i, s in enumerate(node["sentences"], start=1))


def json_answer(answer: str, key: str):
    data = find_json_object(answer, lambda d: key in d)
    if data is None:
        raise ValueError(f"no {key!r} in answer: {answer[:200]!r}")
    return data[key]


# --------------------------------------------------------------------------- variations (each returns flagged
# sentence numbers, 1-based, and notes)

def v1_sentence_review(node, session):
    packet = ReviewPacket(node["id"], node["title"], "", "plan", " ".join(cited(s) for s in node["sentences"]),
                          tuple(ResolvedCitation(f"[{rid}]", r["origin"], r["text"], r["pre_text"], "")
                                for rid, r in node["references"].items()))
    session.say(opening_turn(packet))
    flagged, notes = [], {}
    total = len(node["sentences"])
    for number, sentence in enumerate(node["sentences"], start=1):
        answer = read_sentence_answer(session.say(sentence_turn(number, total, cited(sentence))))
        if answer.unsupported_claim:
            flagged.append(number)
            notes[number] = answer.reason
    return flagged, notes


DECOMPOSE = """You check a planning node for anything its writer guessed. Below are the node's numbered sentences and its included references.
STEP 1 now: break the sentences into atomic claims. An atomic claim is ONE requirement, decision, design choice, plan step, fact about how something works or is, or report of work done or results. A status note, to-do or question is not a claim. Keep each claim short and self-contained; cover every detail (numbers, names, conditions).
Reply with exactly one JSON object: {"claims": [{"sentence": <number>, "claim": "..."}]}

REFERENCES:
{refs}

SENTENCES:
{sentences}"""

CHECK_CLAIM = """Claim {k} of {n} (from sentence {s}): "{claim}"
Is every detail of this claim stated by an included reference (a user reference for requirements and decisions the user must make; a brief "yes" covers only what the agent's question offered)?
Reply with exactly one JSON object: {{"supported": true|false, "reason": "<=15 words"}}"""


def v2_atomic_claims(node, session):
    claims = json_answer(session.say(DECOMPOSE.replace("{refs}", references_block(node))
                                     .replace("{sentences}", numbered(node)), max_tokens=1500), "claims")
    flagged, notes = set(), {}
    for k, claim in enumerate(claims, start=1):
        answer = session.say(CHECK_CLAIM.format(k=k, n=len(claims), s=claim.get("sentence"), claim=claim.get("claim")))
        if json_answer(answer, "supported") is False:
            number = int(claim.get("sentence") or 0)
            flagged.add(number)
            notes.setdefault(number, []).append(claim.get("claim"))
    return sorted(flagged), {**notes, "_claims": len(claims)}


def v3_structure(node):
    """How an agent under a 'facts + requirements lists' rule would lay this node out (PLAN.md V3):
    cited sentences -> requirements (user-cited or kind requirement) or facts; uncited facts/requirements are listed
    uncited (code rejects them); uncited design/plan guesses and status lines stay in free text."""
    requirements, facts, free = [], [], []
    for number, s in enumerate(node["sentences"], start=1):
        origin = node["references"][s["cite"]]["origin"] if s["cite"] else None
        if s["kind"] == "status" or (s["cite"] is None and s["kind"] in ("design", "plan", "work")):
            free.append((number, s))
        elif s["kind"] == "requirement" or origin in USER_ORIGINS:
            requirements.append((number, s))
        else:
            facts.append((number, s))
    return requirements, facts, free


V3_OPEN = """You check a planning node for anything its writer guessed. The node lists its REQUIREMENTS (each must be backed by a user reference) and FACTS (each must be backed by its cited reference), then has FREE TEXT. I will ask about each item, then each free-text sentence.
Reply to this message with exactly {{"ready": true}}.

REFERENCES:
{refs}

REQUIREMENTS:
{reqs}

FACTS:
{facts}

FREE TEXT:
{free}"""

V3_ITEM = """{kind} {label}: "{text}" cites [{ref}].
Does the cited reference state every detail of it (a brief "yes" covers only what the agent's question offered)?
Reply with exactly one JSON object: {{"supported": true|false, "reason": "<=15 words"}}"""

V3_FREE = """Free-text sentence: "{text}"
Does this sentence make a claim (requirement, decision, design choice, plan step, fact, or report of work) that is not covered by a listed requirement or fact?
Reply with exactly one JSON object: {{"answer": "yes"|"no", "reason": "<=15 words"}}"""


def v3_facts_and_requirements(node, session):
    requirements, facts, free = v3_structure(node)
    flagged, notes = set(), {}
    # code checks first: every list item cites something; requirements cite a user reference
    for number, s in requirements + facts:
        if s["cite"] is None:
            flagged.add(number); notes[number] = "code: list item has no citation"
    for number, s in requirements:
        if s["cite"] and node["references"][s["cite"]]["origin"] not in USER_ORIGINS:
            flagged.add(number); notes[number] = "code: requirement cites no user reference"
    listing = lambda items, p: "\n".join(f"{p}{i}. {cited(s)}" for i, (_, s) in enumerate(items, 1)) or "(none)"
    session.say(V3_OPEN.format(refs=references_block(node), reqs=listing(requirements, "R"),
                               facts=listing(facts, "F"), free="\n".join(s["text"] for _, s in free) or "(none)"))
    for kind, items, prefix in (("Requirement", requirements, "R"), ("Fact", facts, "F")):
        for i, (number, s) in enumerate(items, 1):
            if number in flagged:
                continue
            answer = session.say(V3_ITEM.format(kind=kind, label=f"{prefix}{i}", text=s["text"], ref=s["cite"]))
            if json_answer(answer, "supported") is False:
                flagged.add(number); notes[number] = "model: item not supported"
    for number, s in free:
        if str(json_answer(session.say(V3_FREE.format(text=s["text"])), "answer")).lower() == "yes":
            flagged.add(number); notes[number] = "model: uncovered claim in free text"
    return sorted(flagged), notes


GUESS_HUNT = """You audit a planning node for guesswork. Below are the node's numbered sentences and every reference it includes.
List every sentence that states anything its writer would have had to guess: any requirement, decision, design choice, plan step, fact, number, or report of work or results that is not stated by an included reference (requirements and user decisions need a user reference; a brief "yes" covers only what the agent's question offered). Status notes, to-dos and questions are not guesses.
Reply with exactly one JSON object: {"guesses": [{"sentence": <number>, "why": "<=15 words"}]}

REFERENCES:
{refs}

SENTENCES:
{sentences}"""


def v4_guess_hunt(node, session):
    guesses = json_answer(session.say(GUESS_HUNT.replace("{refs}", references_block(node))
                                      .replace("{sentences}", numbered(node)), max_tokens=800), "guesses")
    flagged = sorted({int(g.get("sentence") or 0) for g in guesses})
    return flagged, {int(g.get("sentence") or 0): g.get("why") for g in guesses}


VARIATIONS = {"V1": v1_sentence_review, "V2": v2_atomic_claims, "V3": v3_facts_and_requirements, "V4": v4_guess_hunt}


# --------------------------------------------------------------------------- run + score

def run_one(backend, variation, node):
    session = GemmaSession() if backend == "gemma" else HaikuSession()
    start = time.time()
    try:
        flagged, notes = VARIATIONS[variation](node, session)
        error = None
    except Exception as exc:
        flagged, notes, error = [], {}, repr(exc)[:300]
    labels = {i: s["label"] for i, s in enumerate(node["sentences"], start=1)}
    return {"backend": backend, "variation": variation, "node": node["id"], "flagged": flagged,
            "guesses": [i for i, l in labels.items() if l == "guess"],
            "caught": [i for i in flagged if labels.get(i) == "guess"],
            "false_flags": [i for i in flagged if labels.get(i) == "backed"],
            "neutral_flags": [i for i in flagged if labels.get(i) == "neutral"],
            "calls": session.calls, "seconds": round(time.time() - start, 1), "error": error,
            "notes": {str(k): v for k, v in notes.items()}}


def main():
    backend, variations = sys.argv[1], sys.argv[2].split(",")
    nodes = json.loads((HERE / "nodes.json").read_text())
    jobs = [(backend, v, n) for v in variations for n in nodes]
    out_path = HERE / f"results_{backend}.jsonl"
    with out_path.open("a") as out, ThreadPoolExecutor(1 if backend == "gemma" else 6) as pool:
        for row in pool.map(lambda job: run_one(*job), jobs):
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(row["variation"], row["node"], "caught", row["caught"], "of", row["guesses"], "false",
                  row["false_flags"], "neutral", row["neutral_flags"], row["calls"], "calls", row["seconds"], "s",
                  row["error"] or "", flush=True)


if __name__ == "__main__":
    main()
