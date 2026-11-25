"""review_packet_builder (private): one review record -> a packet with the claim and every cited quote
resolved and inlined (SoT's "no Read needed" pattern), so a reviewer needs no tools."""
from __future__ import annotations

from planning_system.contract import DomainError
from planning_system.server.domain.references.citation_format import citations_in
from planning_system.server.domain.references.citing_and_rendering import slice_lines
from planning_system.server.domain.references.types import (ORIGIN_PROPOSAL_RESPONSE, ORIGIN_USER_EXCHANGE,
                                                            Citation)

from .types import ResolvedCitation, ReviewPacket, ReviewRecord

USER_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)


class ReviewPacketBuilder:
    def __init__(self, references, tree):
        self._references, self._tree = references, tree

    def build(self, record: ReviewRecord) -> ReviewPacket:
        claim_text = self._references.get(record.content_reference_id, follow_superseded=False).text
        node = self._tree.get(record.node_id)
        citations = tuple(self._resolve(c) for c in citations_in(claim_text))
        return ReviewPacket(record.id, node.title, node.context_summary, record.claim_tag, claim_text, citations)

    def _resolve(self, citation: Citation) -> ResolvedCitation:
        try:
            ref = self._references.get(citation.reference_id, follow_superseded=False)
            quoted = slice_lines(ref.text, citation.start_line, citation.end_line)
        except DomainError as error:            # checked at write time; kept visible if it broke since
            return ResolvedCitation(citation, "unresolvable", f"UNRESOLVABLE: {error}", "", "")
        lines = ref.text.splitlines()
        # a stored user exchange is "<pre_text>\n<user message>": what precedes the quote is the context
        pre_text = "\n".join(lines[:citation.start_line - 1]) if ref.origin == ORIGIN_USER_EXCHANGE else ""
        full_text = ref.text if ref.origin in USER_ORIGINS else ""
        return ResolvedCitation(citation, ref.origin, quoted, pre_text, full_text)
