"""Private: the whole-node guess screen's one turn and how its answer is read (build log #60 (5)). The question is
experiment prompt V4 (planning/experiments/node_validation/run.py GUESS_HUNT: 22/23 guesses on gemma, 23/23 on
Haiku, one call per node), adapted: statements instead of sentences, so the node's title and context summary are
screened too, and open items are named as not guesses (build log #61)."""
from __future__ import annotations

from dataclasses import dataclass

from .review_turns import reference_block
from .types import ReviewPacket, UnparseableVerdict
from .verdict_parser import find_json_object

SCREEN_MAX_TOKENS = 800          # the experiment's budget for the guess list

GUESS_HUNT = """NEW REVIEW {review_id}. Ignore every earlier review in this session.
You audit a planning node for guesswork. Below are the node's numbered statements (its title, its context summary and every content item) and every reference the node includes.
List every statement that states anything its writer would have had to guess: any requirement, decision, design choice, plan step, fact, number, or report of work or results that is not stated by an included reference (requirements and user decisions need a user reference; a brief "yes" covers only what the agent's question offered, shown as PRE-INPUT CONTEXT). Status notes, to-dos, questions, open items (lines starting RESEARCH:, ASK USER: or VERIFY WITH USER:) and a title that only names a topic are not guesses.
Reply with exactly one JSON object: {{"guesses": [{{"statement": <number>, "why": "<=15 words"}}]}} (an empty list when nothing was guessed).

REFERENCES:
{refs}
STATEMENTS:
{statements}"""


@dataclass(frozen=True)
class Statement:
    source: str          # "title", "context summary" or "<reference id> <tags>"
    text: str

    def shown(self) -> str:
        return f'[{self.source}] "{self.text}"'


def screen_turn(packet: ReviewPacket, statements: list[Statement]) -> str:
    refs = "\n".join(reference_block(i, c) for i, c in enumerate(packet.citations)) or "(none)\n"
    numbered = "\n".join(f"{n}. [{s.source}] {s.text}" for n, s in enumerate(statements, start=1))
    return GUESS_HUNT.format(review_id=packet.review_id, refs=refs, statements=numbered)


def read_guesses(answer: str, statement_count: int) -> dict[int, str]:
    """statement number -> why; UnparseableVerdict when there is no guess list or a number is out of range."""
    data = find_json_object(answer, lambda d: isinstance(d.get("guesses"), list))
    if data is None:
        raise UnparseableVerdict(f"no guess list from reviewer: {answer[:300]!r}")
    found = {}
    for item in data["guesses"]:
        number = item.get("statement") if isinstance(item, dict) else None
        if not isinstance(number, int) or not 1 <= number <= statement_count:
            raise UnparseableVerdict(f"guess names no valid statement: {item!r}")
        why = item.get("why")
        found[number] = why.strip() if isinstance(why, str) else ""
    return found
