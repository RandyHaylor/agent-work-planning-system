"""Private: the reviewer prompt, adapted from SoT requirements_modification_reviewer.request_change_set_review.
One review per prompt, quotes inlined (no Read needed), strict JSON out."""
from __future__ import annotations

from .types import ReviewPacket

_CONTRACT = (
    "Review fast. One bullet-style fact-check, then commit. "
    "Reply with EXACTLY one JSON object, nothing before/after, no markdown fence:\n"
    '{"passed": true|false, "reason": "<=15 words", "suggested_title": null|"<noun phrase>"}\n\n'
)

_TITLE_RULE = (
    "TITLE RULE: the node title must be a 1-5 word NOUN PHRASE naming the TOPIC (1-50 chars). Sentences and "
    "rules are wrong shape. Examples:\n"
    '  Good: "vendor placement", "phrase character voice", "back end stack"\n'
    '  Bad shape (sentence/rule): "Phrases must be in-character" -> rewrite to something like '
    '"phrase character voice".\n'
    '  Bad scope (adds detail not in slice): cited="yes [to vendor on even floors]", '
    'title="vendor every other floor with stair exclusion" -> rewrite to something like "vendor placement".\n'
    "For wrong-shape or wrong-scope titles, do NOT fail -- set `suggested_title` to a generic noun phrase "
    "that stays within the cited slice. Otherwise `suggested_title` is null.\n\n"
)

_SUPPORTED_PATTERNS = (
    "EXPLICITLY-SUPPORTED PATTERNS (do NOT fail for any of these reasons):\n"
    " (1) BRIEF CONFIRMATION: CITED SLICE may be a brief confirmation such as 'yes', 'no', 'A', 'B', 'C', "
    "'go', 'ok', 'do it', etc. The actual requirement is the conjunction of the agent's question (visible in "
    "PRE-INPUT CONTEXT, what the agent said immediately before the user submitted) AND the user's "
    "confirmation. PASS when PRE-INPUT CONTEXT contains a clear question/proposal and the cited slice is an "
    "unambiguous affirmative/selection answer. Do NOT require the requirement statement to appear inside the "
    "user's submission text.\n"
    " (2) USER STATES THE REQUIREMENT DIRECTLY: if the CITED SLICE itself contains an unambiguous requirement "
    "statement (an instruction, rule, constraint, decision, preference), PASS -- the user is the source of "
    "truth. This holds EVEN IF the user's text partially contradicts, overrides, modifies, or sidesteps the "
    "agent's preceding question/proposal in PRE-INPUT CONTEXT. The pre-input is context, not a consistency "
    "check; user statements supersede prior agent framing.\n\n"
)

_TAG_RULES = {
    "requirement": "CLAIM TAG requirement: pass only if the cited user quote states or acknowledges the "
                   "requirement, and the claim adds nothing the user didn't approve.",
    "decision": "CLAIM TAG decision: pass only if the cited user quote states or acknowledges the decision, "
                "and the claim adds nothing the user didn't approve.",
    "technical": "CLAIM TAG technical: pass only if the cited slice corroborates the claim; fail if the claim "
                 "adds anything the slice doesn't say.",
    "documentation": "CLAIM TAG documentation: pass only if the cited document slice corroborates the claim; "
                     "fail if the claim adds anything the slice doesn't say.",
    "plan": "CLAIM TAG plan: every user-facing claim needs a user citation and every technical claim a "
            "reference citation; fail naming the unsupported sentence.",
    "note": "CLAIM TAG note: a note makes no requirement or technical claim. Fail it if it actually makes "
            "one (it should have been tagged and cited as such).",
}

_ONLY_SUBSTANTIVE = (
    "Only fail for substantive defects: the cited slice does not support the claim (it is a question, "
    "thinking-aloud, or a reaction with no directive content), the citation cuts off mid-meaning, or the claim "
    "does not match the cited slice.\n\n"
)


def build_review_prompt(packet: ReviewPacket) -> str:
    tag_rule = _TAG_RULES.get(packet.claim_tag, f"CLAIM TAG {packet.claim_tag}: the cited slices must support "
                                                "the claim; fail if the claim adds anything they don't say.")
    return (
        _CONTRACT + _TITLE_RULE + _SUPPORTED_PATTERNS + tag_rule + "\n" + _ONLY_SUBSTANTIVE
        + f"NODE TITLE: {packet.node_title}\n"
        + f"NODE CONTEXT SUMMARY: {packet.node_context_summary}\n"
        + f"CLAIM ({packet.claim_tag}):\n{packet.claim_text}\n\n"
        + "RESOLVED CONTEXT (quotes inlined; no Read needed):\n"
        + ("\n".join(_citation_block(i, c) for i, c in enumerate(packet.citations)) or "(no citations)\n")
    )


def _citation_block(index: int, citation) -> str:
    lines = [f"--- citation[{index}] {citation.citation} origin={citation.origin} ---"]
    if citation.pre_text:
        lines.append(f"PRE-INPUT CONTEXT (what the agent had said before this raw input):\n{citation.pre_text}")
    if citation.full_text:
        lines.append(f"FULL ENTRY:\n{citation.full_text}")
    lines.append(f"CITED SLICE (what this claim cites):\n{citation.quoted_text}\n")
    return "\n".join(lines)
