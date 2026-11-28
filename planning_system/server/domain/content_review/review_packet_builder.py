"""review_packet_builder (private): one review record -> a packet with everything a reviewer needs resolved and
inlined (SoT's "no Read needed" pattern), so a reviewer needs no tools.
- content record: the claim and every cited quote.
- node record (guess screen, build log #60 (5)): title, summary, every current content item and the quotes all
  of them cite (each distinct citation once)."""
from __future__ import annotations

from planning_system.errors import DomainError
from planning_system.server.domain.references.citation_syntax import citations_in
from planning_system.server.domain.references.citation_syntax import slice_lines
from planning_system.server.domain.references import ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE, Citation

from .types import TARGET_NODE, PacketContentItem, ResolvedCitation, ReviewPacket, ReviewRecord

USER_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)


class ReviewPacketBuilder:
    def __init__(self, references, tree):
        self._references, self._tree = references, tree

    def build(self, record: ReviewRecord) -> ReviewPacket:
        if record.target_kind == TARGET_NODE:
            return self._node_packet(record)
        claim_text = self._references.get(record.content_reference_id, follow_superseded=False).text
        node = self._tree.get(record.node_id)
        citations = tuple(self._resolve(c) for c in citations_in(claim_text))
        return ReviewPacket(record.id, node.title, node.context_summary, record.claim_tag, claim_text, citations)

    def _node_packet(self, record: ReviewRecord) -> ReviewPacket:
        node = self._tree.get(record.node_id)
        items = tuple(PacketContentItem(c.reference_id, tuple(sorted(c.tags)),
                                        self._references.get(c.reference_id, follow_superseded=False).text)
                      for c in self._tree.content(record.node_id))
        seen, citations = set(), []
        for text in (node.title, node.context_summary, *(item.text for item in items)):
            for citation in citations_in(text):
                if citation not in seen:
                    seen.add(citation)
                    citations.append(self._resolve(citation))
        return ReviewPacket(record.id, node.title, node.context_summary, "", "", tuple(citations), TARGET_NODE,
                            items)

    def _resolve(self, citation: Citation) -> ResolvedCitation:
        return resolve_citation(self._references, citation)


def resolve_citation(references, citation: Citation) -> ResolvedCitation:
    try:
        ref = references.get(citation.reference_id, follow_superseded=False)
        quoted = slice_lines(ref.text, citation.start_line, citation.end_line)
    except DomainError as error:            # checked at write time; kept visible if it broke since
        return ResolvedCitation(citation, "unresolvable", f"UNRESOLVABLE: {error}", "", "")
    lines = ref.text.splitlines()
    # a stored user exchange is "<pre_text>\n<user message>": what precedes the quote is the context
    pre_text = "\n".join(lines[:citation.start_line - 1]) if ref.origin == ORIGIN_USER_EXCHANGE else ""
    full_text = ref.text if ref.origin in USER_ORIGINS else ""
    return ResolvedCitation(citation, ref.origin, quoted, pre_text, full_text)
