"""TrialReview: the supersede trial review (05-spec-reference-supersede.md 3). One turn: the claim, the old cited
lines, the diff-matched lines in the newer copy AND the whole newer copy (approved change (b)); a deprecation or
warning about the claimed thing counts as no longer supported. Prompt: experiment TRIAL (P3) in
planning/experiments/supersede/run.py, with that rule added."""
from __future__ import annotations

from .review_conversation import ReviewConversation
from .review_method import ReviewMethod
from .types import ReviewPacket, UnparseableVerdict, Verdict
from .verdict_parser import find_json_object

TRIAL = ("NEW REVIEW {review_id}. Ignore every earlier review in this session.\n"
         "A planning claim cited lines of an OLD copy of a reference. A NEW copy of the same source was found. "
         "Decide whether the NEW copy still supports every detail of the claim, and whether the NEW copy looks "
         "like an error, login, loading or placeholder page instead of real content. A deprecation or warning "
         "about the claimed thing in the NEW copy means the claim is no longer supported.\n\n"
         "CLAIM: {claim}\n\nCITED OLD LINES:\n{old_lines}\n\n"
         "THE SAME LINES IN THE NEW COPY (matched by diff):\n{new_lines}\n\nWHOLE NEW COPY:\n{new_copy}\n\n"
         'Reply with exactly one JSON object: {{"still_supported": true|false, "broken_page": true|false, '
         '"reason": "<=15 words"}}')
DELETED = "(every cited line was deleted)"


class TrialReview(ReviewMethod):

    def run(self, packet: ReviewPacket, conversation: ReviewConversation) -> Verdict:
        old_lines = "\n".join(c.old_text for c in packet.comparisons) or "(no lines cited)"
        new_lines = "\n".join(c.new_text or DELETED for c in packet.comparisons) or DELETED
        answer = conversation.say(TRIAL.format(review_id=packet.review_id, claim=packet.claim_text,
                                               old_lines=old_lines, new_lines=new_lines,
                                               new_copy=packet.against_text))
        data = find_json_object(answer, lambda d: isinstance(d.get("still_supported"), bool))
        if data is None:
            raise UnparseableVerdict(f"no trial answer from reviewer: {answer[:300]!r}")
        reason = str(data.get("reason") or "").strip()
        new = packet.against_reference_id
        if data.get("broken_page") is True:
            return Verdict(False, f"the new copy {new} looks like an error or placeholder page: {reason}")
        if data["still_supported"]:
            return Verdict(True, f"still supported by {new}: {reason}")
        return Verdict(False, f"no longer supported by {new}: {reason}")
