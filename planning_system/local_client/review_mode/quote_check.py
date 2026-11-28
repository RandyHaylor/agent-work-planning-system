"""QuoteCheck: the all-quotes check (05-spec-reference-supersede.md 2, approved change (a)). ONE call lists the new
user statement and every user quote cited in the project and asks which ones it changes (experiment prompt Q2 in
planning/experiments/supersede/run.py: 11/11 changes, 0/109 false alarms on gemma); batched when the quotes don't
fit one prompt. The changed quotes are returned as findings (reference ids); the server turns them into
supersede candidates."""
from __future__ import annotations

from .review_conversation import ReviewConversation
from .review_method import ReviewMethod
from .types import ResolvedCitation, ReviewPacket, UnparseableVerdict, Verdict
from .verdict_parser import find_json_object

DEFAULT_BATCH_SIZE = 40          # quotes per call
CHECK_MAX_TOKENS = 600           # the experiment's budget for the list

CHANGE_RULE = ("A statement CHANGES an earlier quote if it replaces, contradicts, narrows, widens, adds to, removes "
               "from, or makes more specific what that quote required. Repeating or agreeing with it, or talking "
               "about something else, is not a change.")
ALL_QUOTES = ("NEW REVIEW {review_id}. Ignore every earlier review in this session.\n"
              "You check whether a user's NEW STATEMENT changes any requirement they gave earlier. " + CHANGE_RULE +
              '\n\nNEW STATEMENT:\n{new}\n\nEARLIER QUOTES:\n{quotes}\n\nList every earlier quote the new statement '
              'changes. Reply with exactly one JSON object: {{"changed": [{{"quote": "U1", "reason": "<=15 words"}}]}} '
              '(empty list if none).')


def _statement(quote: ResolvedCitation) -> str:
    return f'Agent asked: "{quote.pre_text}"\nUser answered: "{quote.quoted_text}"'


def _quote_line(label: str, quote: ResolvedCitation) -> str:
    return f'[{label}] agent asked: "{quote.pre_text}" / user answered: "{quote.quoted_text}"'


class QuoteCheck(ReviewMethod):

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        self._batch_size = batch_size

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        quotes = {f"U{n}": quote for n, quote in enumerate(packet.citations, start=1)}
        if packet.subject is None or not quotes:
            return Verdict(True, "no earlier user quotes to compare")
        labels = list(quotes)
        changed: dict[str, str] = {}
        for start in range(0, len(labels), self._batch_size):
            batch = labels[start:start + self._batch_size]
            prompt = ALL_QUOTES.format(review_id=packet.review_id, new=_statement(packet.subject),
                                       quotes="\n".join(_quote_line(label, quotes[label]) for label in batch))
            changed.update(self._read(conversation.say(prompt, max_tokens=CHECK_MAX_TOKENS), batch))
        if not changed:
            return Verdict(True, f"changes none of {len(labels)} earlier quotes")
        ordered = sorted(changed, key=labels.index)
        reason = "; ".join(f"changes {label} ({quotes[label].reference_id}): {changed[label]}" for label in ordered)
        findings = tuple(dict.fromkeys(quotes[label].reference_id for label in ordered))
        return Verdict(False, reason, None, findings)

    @staticmethod
    def _read(answer: str, batch: list[str]) -> dict[str, str]:
        data = find_json_object(answer, lambda d: isinstance(d.get("changed"), list))
        if data is None:
            raise UnparseableVerdict(f"no changed-quotes list from reviewer: {answer[:300]!r}")
        found = {}
        for item in data["changed"]:
            label = str(item.get("quote", "")).strip() if isinstance(item, dict) else ""
            if label not in batch:
                raise UnparseableVerdict(f"changed-quotes answer names no listed quote: {item!r}")
            found[label] = str(item.get("reason") or "").strip()
        return found
