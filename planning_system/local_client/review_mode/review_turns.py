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


@dataclass(frozen=True)
class SentenceAnswer:
    unsupported_claim: bool    # True = "yes": the sentence makes a claim the references don't fully support
    reason: str


def opening_turn(packet: ReviewPacket) -> str:
    return (
        f"NEW REVIEW {packet.review_id}. Ignore every earlier review in this session.\n"
        "You check a planning item's claim against its included references. I will send the claim's sentences "
        f"one at a time. For each I ask: {SENTENCE_QUESTION}\n"
        "Rules:\n"
        " - A brief confirmation ('yes', 'A', 'ok', 'go') supports exactly what the PRE-INPUT CONTEXT "
        "question or proposal offered, nothing more.\n"
        " - Any detail (number, version, product, extra item, extra behaviour, stronger wording) not stated in "
        "an included reference is not supported.\n"
        " - A sentence that contradicts a reference makes an unsupported claim.\n"
        " - Citation markers such as [ref-1:2-3] are not claims themselves.\n"
        'Answer every sentence with exactly one JSON object, nothing else: '
        '{"answer": "yes"|"no", "reason": "<=15 words: what is unsupported; empty when no"}\n\n'
        f"CLAIM TAG: {packet.claim_tag}\n"
        f"NODE TITLE: {packet.node_title}\n"
        f"NODE CONTEXT SUMMARY: {packet.node_context_summary}\n"
        f"FULL CLAIM:\n{packet.claim_text}\n\n"
        "INCLUDED REFERENCES:\n"
        + ("\n".join(_reference_block(i, c) for i, c in enumerate(packet.citations)) or "(none)\n")
        + '\nReply now with exactly {"ready": true}.'
    )


def sentence_turn(number: int, total: int, sentence: str) -> str:
    return (f'Sentence {number} of {total}: "{sentence}"\n{SENTENCE_QUESTION}\n'
            'Reply with exactly {"answer": "yes"|"no", "reason": "..."}.')


def title_turn(node_title: str) -> str:
    return (
        f'Last: the node title is "{node_title}". It must be a 1-5 word NOUN PHRASE naming the TOPIC (1-50 chars), '
        "staying within what the references say. Sentences and rules are the wrong shape.\n"
        '  Good: "vendor placement", "phrase character voice", "back end stack"\n'
        '  Bad shape: "Phrases must be in-character" -> "phrase character voice"\n'
        '  Bad scope: cited "yes [to vendor on even floors]", title "vendor every other floor with stair '
        'exclusion" -> "vendor placement"\n'
        'Reply with exactly {"suggested_title": null} if the title is fine, else '
        '{"suggested_title": "<noun phrase>"}.'
    )


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
