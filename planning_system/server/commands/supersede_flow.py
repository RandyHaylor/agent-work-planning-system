"""supersede_flow: the steps of 05-spec-reference-supersede.md (approved) that compose candidates, the tree and the
review ledger, shared by the commands that trigger them (like content_submission for content writes):
candidate -> a trial review of every content item citing the old reference -> when all are decided, a requirement
request task before the earliest affected task (one content item per discrepancy) -> confirm (supersede + reopen
the citing items' reviews) or reject. Model checks run on review-mode clients, never here."""
from __future__ import annotations

from typing import Optional

from planning_system.errors import Invalid
from planning_system.server.domain.citation_enforcement import CLAIM_TAGS, OPEN_ITEMS
from planning_system.server.domain.content_review import (FAILED, PENDING, TAKEN, TARGET_QUOTE_CHECK, TARGET_TRIAL,
                                                          ReviewRecord)
from planning_system.server.domain.project_tree import REQUIREMENT_REQUEST
from planning_system.server.domain.references import (FOUND_QUOTE_CHECK, FOUND_SAME_SOURCE, KIND_DOCUMENT,
                                                      ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE, ORIGIN_PROPOSAL_RESPONSE,
                                                      ORIGIN_USER_EXCHANGE, SupersedeCandidate)

USER_ORIGINS = (ORIGIN_USER_EXCHANGE, ORIGIN_PROPOSAL_RESPONSE)
DOCUMENT_ORIGINS = (ORIGIN_DOCUMENT, ORIGIN_KNOWLEDGE_BASE)
REQUEST_TITLE = "evidence update confirmation"
SUPERSEDE_TAGS = ("note", "supersede")


def claim_tag_of(tags) -> Optional[str]:
    """The item's reviewed claim tag (open_items are never reviewed)."""
    return next((t for t in CLAIM_TAGS if t in tags and t != OPEN_ITEMS), None)


def items_citing(services, project_id: int, reference_id: str) -> dict:
    """(node id, content item id) -> tags, for every current item in the project citing the reference (a
    requirement request's own supersede items are records, not claims: skipped)."""
    return {(c.node_id, c.content_reference_id): c.tags for c in services.tree.project_citations(project_id)
            if c.citation.reference_id == reference_id and SUPERSEDE_TAGS[1] not in c.tags}


def project_of_node(services, node_id: int) -> int:
    ancestors = services.tree.ancestors(node_id)
    return ancestors[0].id if ancestors else node_id


# ---- candidates

def open_candidate(services, project_id: int, old_id: str, new_id: str, found_by: str, proposed_by: Optional[str],
                   reason: str = "") -> SupersedeCandidate:
    candidate, created = services.candidates.propose(project_id, old_id, new_id, found_by, proposed_by, reason)
    if created:
        _open_trials(services, candidate)
    return candidate


def _open_trials(services, candidate: SupersedeCandidate) -> None:
    citing = items_citing(services, candidate.project_id, candidate.old_reference_id)
    for (node_id, item_id), tags in sorted(citing.items()):
        services.reviews.open_trial(candidate.project_id, node_id, item_id, claim_tag_of(tags) or "",
                                    candidate.old_reference_id, candidate.new_reference_id, candidate.id)
    if not citing:
        _finish_trials(services, candidate)


def same_source_candidates(services, principal, new_reference_id: str) -> list[SupersedeCandidate]:
    """Spec 2: the same URL or file cited again with different content -> a candidate per current older copy."""
    new = services.references.get(new_reference_id, follow_superseded=False)
    locator = new.metadata.get("locator")
    if new.origin not in DOCUMENT_ORIGINS or not locator:
        return []
    found = []
    for old in services.related.related(locator, "", exclude_id=new.id).same_source:
        if old.origin not in DOCUMENT_ORIGINS:
            continue
        project_id = principal.project_id if principal is not None else None
        if project_id is None:
            citing = services.tree.citing_nodes(old.id)
            project_id = project_of_node(services, citing[0].id) if citing else None
        if project_id is not None:
            found.append(open_candidate(services, project_id, old.id, new.id, FOUND_SAME_SOURCE, None,
                                        f"{locator} loaded again with different content"))
    return found


# ---- the all-quotes check (spec 2, approved change (a))

def open_quote_checks(services, project_id: int, node_id: int, item_id: str, citations) -> list[ReviewRecord]:
    """A user quote cited for the first time in the project is checked against every user quote cited there."""
    cited = services.tree.project_citations(project_id)
    opened = []
    for reference_id in dict.fromkeys(c.reference_id for c in citations):
        if services.references.get(reference_id, follow_superseded=False).origin not in USER_ORIGINS:
            continue
        elsewhere = [c for c in cited if c.citation.reference_id == reference_id and c.content_reference_id != item_id]
        others = [c for c in cited if c.citation.reference_id != reference_id and services.references.get(
            c.citation.reference_id, follow_superseded=False).origin in USER_ORIGINS]
        if not elsewhere and others:
            opened.append(services.reviews.open_quote_check(project_id, node_id, item_id, reference_id))
    return opened


# ---- after a verdict

def after_verdict(services, record: ReviewRecord) -> None:
    if record.target_kind == TARGET_QUOTE_CHECK:
        for old_id in record.findings:
            try:
                open_candidate(services, record.project_id, old_id, record.against_reference_id, FOUND_QUOTE_CHECK,
                               None, f"the all-quotes check: {record.reason}")
            except Invalid:
                continue                  # e.g. the reviewer named a quote that is superseded by now
    elif record.target_kind == TARGET_TRIAL and record.candidate_id:
        _finish_trials(services, services.candidates.get(record.candidate_id))


def _finish_trials(services, candidate: SupersedeCandidate) -> None:
    if candidate.status != "proposed":
        return
    trials = services.reviews.for_candidate(candidate.id)
    if any(t.status in (PENDING, TAKEN) for t in trials):
        return
    request = _requirement_request(services, candidate, trials)
    services.candidates.mark_trial_reviewed(candidate.id, request.id if request is not None else None)


def _requirement_request(services, candidate: SupersedeCandidate, trials: list[ReviewRecord]):
    """Spec 4: one requirement request per candidate, inserted before the earliest affected task (lowest node id
    that accepts a sibling), one content item per discrepancy. None when nothing is affected."""
    who = ("the planner may confirm it (the user can override)" if candidate.kind == KIND_DOCUMENT
           else "only the user confirms it")
    summary = (f"Confirm or reject supersede candidate {candidate.id}: {candidate.new_reference_id} replaces "
               f"{candidate.old_reference_id} ({candidate.kind}, found by {candidate.found_by}); {who}. "
               f"`planning references confirm-supersede {candidate.id}` or "
               f"`planning references reject-supersede {candidate.id} --reason ...`")
    for node_id in sorted({t.node_id for t in trials}):
        try:
            request = services.tree.insert_before(node_id, REQUEST_TITLE, (REQUIREMENT_REQUEST,), summary)
        except Invalid:
            continue
        services.tree.add_content(request.id, _pair_text(services, candidate), SUPERSEDE_TAGS)
        for trial in trials:
            if trial.status == FAILED:
                services.tree.add_content(request.id, (
                    f"Discrepancy: node {trial.node_id}, content {trial.content_reference_id} would no longer hold "
                    f"against {candidate.new_reference_id}: {trial.reason}"), SUPERSEDE_TAGS)
        return request
    return None


def _pair_text(services, candidate: SupersedeCandidate) -> str:
    def whole(reference_id):
        count = max(1, len(services.references.get(reference_id, follow_superseded=False).text.splitlines()))
        return f"[{reference_id}:1-{count}]"
    return (f"Supersede candidate {candidate.id}: old {whole(candidate.old_reference_id)}, "
            f"new {whole(candidate.new_reference_id)}. Reason: {candidate.reason or 'none given'}")


# ---- confirm

def reopen_citing_reviews(services, candidate: SupersedeCandidate) -> list[ReviewRecord]:
    """Spec 5: each claim citing the old reference is reviewed again, now against the newer version (the packet
    builder resolves a superseded citation to the newest version)."""
    citing = items_citing(services, candidate.project_id, candidate.old_reference_id)
    reopened = [services.reviews.open(candidate.project_id, node_id, item_id, claim_tag_of(tags))
                for (node_id, item_id), tags in sorted(citing.items()) if claim_tag_of(tags)]
    for node_id in sorted({node_id for node_id, _ in citing}):
        services.reviews.open_node(candidate.project_id, node_id)
    return reopened
