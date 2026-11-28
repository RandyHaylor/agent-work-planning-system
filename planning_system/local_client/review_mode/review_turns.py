"""Private: the review turn protocol: what each turn says and how its answer is read.
Opening turn (rules + claim + references) -> one turn per sentence (user 2026-11-27: "does this sentence make a
claim not fully supported by an included user or document reference") -> title turn. Replaces the one-shot
review_prompt (build log #55)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import ResolvedCitation, ReviewPacket, UnparseableVerdict
from .verdict_parser import find_json_object

SENTENCE_QUESTION = ("Does this sentence make a claim not fully supported by an included user or document "
                     "reference?")


# build log #60 (2): requirement and decision restatements must not drop or weaken what the user said
NOTHING_LOST_TAGS = frozenset({"requirement", "decision"})
NOTHING_LOST_QUESTION = (
    "Compare the FULL CLAIM with what the user said in the included user references (for a brief confirmation, "
    "with the proposal the user approved, shown as PRE-INPUT CONTEXT). Does the claim drop or weaken any "
    "condition, limit, exception or hedge the user stated (for example 'only', 'for now', 'unless ...', "
    "'at most ...', 'maybe', 'if ...', 'after ...', a number or a scope)?")


def needs_nothing_lost_check(packet: ReviewPacket) -> bool:
    return packet.claim_tag in NOTHING_LOST_TAGS


@dataclass(frozen=True)
class SentenceAnswer:
    unsupported_claim: bool    # True = "yes": the sentence makes a claim the references don't fully support
    reason: str


_RULES = (
    "Rules:\n"
    " - A brief confirmation ('yes', 'A', 'ok', 'go') supports exactly what the PRE-INPUT CONTEXT "
    "question or proposal offered, nothing more.\n"
    " - Any detail (number, version, product, extra item, extra behaviour, stronger wording) not stated in "
    "an included reference is not supported.\n"
    " - A sentence that contradicts a reference makes an unsupported claim.\n"
    " - Citation markers such as [ref-1:2-3] are not claims themselves.\n"
)


def opening_turn(packet: ReviewPacket) -> str:
    return (
        f"NEW REVIEW {packet.review_id}. Ignore every earlier review in this session.\n"
        "You check a planning item's claim against its included references. I will send the claim's sentences "
        f"one at a time. For each I ask: {SENTENCE_QUESTION}\n"
        + _RULES
        + 'Answer every sentence with exactly one JSON object, nothing else: '
        '{"answer": "yes"|"no", "reason": "<=15 words: what is unsupported; empty when no"}\n\n'
        + _claim_and_references(packet)
        + '\nReply now with exactly {"ready": true}.'
    )


def sentence_turn(number: int, total: int, sentence: str) -> str:
    return (f'Sentence {number} of {total}: "{sentence}"\n{SENTENCE_QUESTION}\n'
            'Reply with exactly {"answer": "yes"|"no", "reason": "..."}.')


def nothing_lost_turn() -> str:
    return (f"Now the whole claim. {NOTHING_LOST_QUESTION}\n"
            'Reply with exactly {"answer": "yes"|"no", "reason": "<=15 words: which condition was dropped or '
            'weakened; empty when no"}.')


def title_turn(node_title: str) -> str:
    return (_title_rules(node_title, "Last: ")
            + 'Reply with exactly {"suggested_title": null} if the title is fine, else '
            '{"suggested_title": "<noun phrase>"}.')


def bulk_turn(packet: ReviewPacket, sentences: list[str]) -> str:
    """One turn: the same rules and question as the per-sentence turns, asked of every numbered sentence at once,
    plus the title check."""
    numbered = "\n".join(f"{number}. {sentence}" for number, sentence in enumerate(sentences, start=1))
    nothing_lost = needs_nothing_lost_check(packet)
    return (
        f"NEW REVIEW {packet.review_id}. Ignore every earlier review in this session.\n"
        "You check a planning item's claim against its included references. Ask of EVERY numbered sentence "
        f"below: {SENTENCE_QUESTION}\n"
        + _RULES + "\n"
        + _claim_and_references(packet)
        + f"\nNUMBERED SENTENCES OF THE CLAIM:\n{numbered}\n\n"
        + _title_rules(packet.node_title, "Also: ")
        + (f"Also: {NOTHING_LOST_QUESTION} List each one in \"dropped_conditions\".\n" if nothing_lost else "")
        + 'Reply with exactly one JSON object, nothing else: {"unsupported": [{"sentence": <number>, '
        '"reason": "<=15 words: what is unsupported"}], '
        + ('"dropped_conditions": [{"condition": "<the user\'s words>", "reason": "<=15 words"}], '
           if nothing_lost else "")
        + '"suggested_title": null|"<noun phrase>"} '
        '(an empty "unsupported" list when every sentence is supported'
        + ('; an empty "dropped_conditions" list when nothing was dropped or weakened).' if nothing_lost else ").")
    )


def _claim_and_references(packet: ReviewPacket) -> str:
    return (f"CLAIM TAG: {packet.claim_tag}\n"
            f"NODE TITLE: {packet.node_title}\n"
            f"NODE CONTEXT SUMMARY: {packet.node_context_summary}\n"
            f"FULL CLAIM:\n{packet.claim_text}\n\n"
            "INCLUDED REFERENCES:\n"
            + ("\n".join(_reference_block(i, c) for i, c in enumerate(packet.citations)) or "(none)\n"))


def _title_rules(node_title: str, lead: str) -> str:
    return (
        f'{lead}the node title is "{node_title}". It must be a 1-5 word NOUN PHRASE naming the TOPIC (1-50 chars), '
        "staying within what the references say. Sentences and rules are the wrong shape.\n"
        '  Good: "vendor placement", "phrase character voice", "back end stack"\n'
        '  Bad shape: "Phrases must be in-character" -> "phrase character voice"\n'
        '  Bad scope: cited "yes [to vendor on even floors]", title "vendor every other floor with stair '
        'exclusion" -> "vendor placement"\n'
    )


@dataclass(frozen=True)
class BulkAnswer:
    unsupported: dict[int, str]          # sentence number -> reason
    suggested_title: Optional[str]
    dropped_conditions: tuple[str, ...] = ()   # "<condition>: <reason>" (nothing-lost check)


def read_bulk_answer(answer: str, sentence_count: int, expect_dropped_conditions: bool = False) -> BulkAnswer:
    def readable(d: dict) -> bool:
        return isinstance(d.get("unsupported"), list) and (
            not expect_dropped_conditions or isinstance(d.get("dropped_conditions"), list))

    data = find_json_object(answer, readable)
    if data is None:
        raise UnparseableVerdict(f"no bulk answer from reviewer: {answer[:300]!r}")
    unsupported = {}
    for item in data["unsupported"]:
        number = item.get("sentence") if isinstance(item, dict) else None
        if not isinstance(number, int) or not 1 <= number <= sentence_count:
            raise UnparseableVerdict(f"bulk answer names no valid sentence: {item!r}")
        reason = item.get("reason")
        unsupported[number] = reason.strip() if isinstance(reason, str) else ""
    title = data.get("suggested_title")
    dropped = tuple(_dropped_text(item) for item in data.get("dropped_conditions") or ()) \
        if expect_dropped_conditions else ()
    return BulkAnswer(unsupported, title.strip() if isinstance(title, str) and title.strip() else None, dropped)


def _dropped_text(item) -> str:
    if not isinstance(item, dict):
        return str(item)
    parts = [str(item.get(key) or "").strip() for key in ("condition", "reason")]
    return ": ".join(p for p in parts if p) or "a condition was dropped"


def read_sentence_answer(answer: str) -> SentenceAnswer:
    data = find_json_object(answer, lambda d: str(d.get("answer", "")).strip().lower() in ("yes", "no"))
    if data is None:
        raise UnparseableVerdict(f"no yes/no answer from reviewer: {answer[:300]!r}")
    reason = data.get("reason")
    return SentenceAnswer(str(data["answer"]).strip().lower() == "yes",
                          reason.strip() if isinstance(reason, str) else "")


def read_title_answer(answer: str) -> Optional[str]:
    data = find_json_object(answer, lambda d: "suggested_title" in d)
    if data is None:
        raise UnparseableVerdict(f"no title answer from reviewer: {answer[:300]!r}")
    title = data["suggested_title"]
    return title.strip() if isinstance(title, str) and title.strip() else None


def _reference_block(index: int, citation: ResolvedCitation) -> str:
    lines = [f"--- reference[{index}] {citation.citation} origin={citation.origin} ---"]
    if citation.pre_text:
        lines.append(f"PRE-INPUT CONTEXT (what the agent had said before this user input):\n{citation.pre_text}")
    if citation.full_text:
        lines.append(f"FULL ENTRY:\n{citation.full_text}")
    lines.append(f"CITED TEXT:\n{citation.quoted_text}\n")
    return "\n".join(lines)
