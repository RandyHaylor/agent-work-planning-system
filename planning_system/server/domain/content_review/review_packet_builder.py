"""review_packet_builder (private): one review record -> a packet with everything a reviewer needs resolved and
inlined (SoT's "no Read needed" pattern), so a reviewer needs no tools.
- content: the claim and every cited quote. A citation of a superseded reference (only possible after a confirmed
  supersede reopened the review) is resolved to the newest version, the range mapped with difflib.
- node (guess screen, build log #60 (5)): title, summary, every current content item and the quotes all of them
  cite (each distinct citation once).
- trial (supersede spec 3): the claim, its quotes, and for each citation of the older reference the old lines,
  the diff-matched lines in the newer copy, and the whole newer copy (approved change (b)).
- quote_check (supersede spec 2, change (a)): the new user statement as cited, and every OTHER user quote cited
  anywhere in the project."""
from __future__ import annotations

from planning_system.errors import DomainError
from planning_system.server.domain.references.citation_syntax import citations_in
from planning_system.server.domain.references.citation_syntax import slice_lines
from planning_system.server.domain.references import (ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE, Citation,
                                                      map_line_range)

from .types import (TARGET_NODE, TARGET_QUOTE_CHECK, TARGET_TRIAL, Comparison, PacketContentItem,
                    ResolvedCitation, ReviewPacket, ReviewRecord)

USER_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)


class ReviewPacketBuilder:
    def __init__(self, references, tree):
        self._references, self._tree = references, tree

    def build(self, record: ReviewRecord) -> ReviewPacket:
        builders = {TARGET_NODE: self._node_packet, TARGET_TRIAL: self._trial_packet,
                    TARGET_QUOTE_CHECK: self._quote_check_packet}
        return builders.get(record.target_kind, self._content_packet)(record)

    def _content_packet(self, record: ReviewRecord) -> ReviewPacket:
        claim_text = self._text(record.content_reference_id)
        node = self._tree.get(record.node_id)
        citations = tuple(self._resolve(c) for c in citations_in(claim_text))
        return ReviewPacket(record.id, node.title, node.context_summary, record.claim_tag, claim_text, citations)

    def _node_packet(self, record: ReviewRecord) -> ReviewPacket:
        node = self._tree.get(record.node_id)
        items = tuple(PacketContentItem(c.reference_id, tuple(sorted(c.tags)), self._text(c.reference_id))
                      for c in self._tree.content(record.node_id))
        seen, citations = set(), []
        for text in (node.title, node.context_summary, *(item.text for item in items)):
            for citation in citations_in(text):
                if citation not in seen:
                    seen.add(citation)
                    citations.append(self._resolve(citation))
        return ReviewPacket(record.id, node.title, node.context_summary, "", "", tuple(citations), TARGET_NODE,
                            items)

    def _trial_packet(self, record: ReviewRecord) -> ReviewPacket:
        base = self._content_packet(record)
        old_text, new_text = self._text(record.replaces_reference_id), self._text(record.against_reference_id)
        comparisons = tuple(self._compare(c, old_text, new_text) for c in citations_in(base.claim_text)
                            if c.reference_id == record.replaces_reference_id)
        return ReviewPacket(base.review_id, base.node_title, base.node_context_summary, base.claim_tag,
                            base.claim_text, base.citations, TARGET_TRIAL,
                            against_reference_id=record.against_reference_id, against_text=new_text,
                            comparisons=comparisons)

    def _quote_check_packet(self, record: ReviewRecord) -> ReviewPacket:
        node = self._tree.get(record.node_id)
        new_id = record.against_reference_id
        subject = next((self._resolve(c) for c in citations_in(self._text(record.content_reference_id))
                        if c.reference_id == new_id), None)
        earlier, seen = [], set()
        for cited in self._tree.project_citations(record.project_id):
            citation = cited.citation
            if citation.reference_id == new_id or citation in seen:
                continue
            seen.add(citation)
            ref = self._references.get(citation.reference_id, follow_superseded=False)
            if ref.origin in USER_ORIGINS and not ref.superseded_by:
                earlier.append(self._resolve(citation))
        return ReviewPacket(record.id, node.title, node.context_summary, "", "", tuple(earlier), TARGET_QUOTE_CHECK,
                            against_reference_id=new_id, subject=subject)

    def _text(self, reference_id) -> str:
        return self._references.get(reference_id, follow_superseded=False).text

    def _resolve(self, citation: Citation) -> ResolvedCitation:
        return resolve_citation(self._references, citation)

    @staticmethod
    def _compare(citation: Citation, old_text: str, new_text: str) -> Comparison:
        old = slice_lines(old_text, citation.start_line, citation.end_line)
        mapped = map_line_range(old_text, new_text, citation.start_line, citation.end_line)
        if mapped.start is None:
            return Comparison(citation, old, "", None, None)
        return Comparison(citation, old, slice_lines(new_text, mapped.start, mapped.end), mapped.start, mapped.end)


def resolve_citation(references, citation: Citation) -> ResolvedCitation:
    try:
        ref = references.get(citation.reference_id, follow_superseded=False)
        start, end, note = citation.start_line, citation.end_line, ""
        if ref.superseded_by:                     # reopened after a confirmed supersede: read the newest version
            current = references.get(ref.id, follow_superseded=True)
            mapped = map_line_range(ref.text, current.text, start, end)
            if mapped.start is None:
                return ResolvedCitation(citation, current.origin,
                                        f"(superseded by {current.id}: the cited lines are gone from it)", "", "")
            ref, start, end = current, mapped.start, mapped.end
            note = f"(superseded by {current.id}; lines {start}-{end} of it) "
        quoted = note + slice_lines(ref.text, start, end)
    except DomainError as error:            # checked at write time; kept visible if it broke since
        return ResolvedCitation(citation, "unresolvable", f"UNRESOLVABLE: {error}", "", "")
    lines = ref.text.splitlines()
    # a stored user exchange is "<pre_text>\n<user message>": what precedes the quote is the context
    pre_text = "\n".join(lines[:start - 1]) if ref.origin == ORIGIN_USER_EXCHANGE else ""
    full_text = ref.text if ref.origin in USER_ORIGINS else ""
    return ResolvedCitation(citation, ref.origin, quoted, pre_text, full_text)
