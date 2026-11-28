"""request_authorizer: resolves the facts a permission needs (node, ancestors, citing nodes, temp entry,
credential scope) through the domain, asks access/PermissionPolicy, raises Forbidden."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from planning_system.contract import Forbidden, NotFound, Principal
from planning_system.server.domain.access import (ADMIN, WORKER, CredentialScope, NodeFacts, ReferenceFacts,
                                                  TempEntryFacts)
from planning_system.server.domain.content_review import TAKEN
from planning_system.server.domain.references.citation_syntax import cites, parse_citation

from . import permissions as P
from .permissions import Permission
from .services import Services


class RequestAuthorizerInterface(ABC):
    @abstractmethod
    def check(self, principal: Optional[Principal], permission: Permission, services: Services) -> None:
        """Returns, or raises Forbidden (NotFound when a named node/reference doesn't exist).
        principal None passes only NoPrincipalNeeded."""


class TreeFacts:
    """Node facts read through ProjectTree (the project is the root of the node's ancestry)."""

    def __init__(self, services: Services):
        self._tree = services.tree

    def of(self, node_id: int) -> NodeFacts:
        return self.of_node(self._tree.get(node_id))

    def of_node(self, node) -> NodeFacts:
        ancestors = self._tree.ancestors(node.id)
        return NodeFacts(node.id, ancestors[0].id if ancestors else node.id, node.assignee,
                         frozenset(node.labels), node.state)


class RequestAuthorizer(RequestAuthorizerInterface):
    def __init__(self):
        self._rules: dict[type, Callable[[Principal, P.Permission, Services], bool]] = {
            P.Authenticated: lambda p, perm, s: True,
            P.RoleIs: lambda p, perm, s: p.role in perm.roles,
            P.CanReadNode: self._can_read_node,
            P.CanCreateNode: lambda p, perm, s: s.policy.can_create_node(p, TreeFacts(s).of(perm.parent_id)),
            P.CanEditNode: lambda p, perm, s: s.policy.can_edit_node(p, TreeFacts(s).of(perm.node_id)),
            P.CanMoveNode: self._can_move,
            P.CanSetState: lambda p, perm, s: s.policy.can_set_state(p, TreeFacts(s).of(perm.node_id),
                                                                       perm.new_state),
            P.CanAssign: self._can_assign,
            P.CanCreateSupplementaryTask: lambda p, perm, s: s.policy.can_create_supplementary_task(
                p, TreeFacts(s).of(perm.task_id)),
            P.CanAddContent: lambda p, perm, s: s.policy.can_add_content(p, TreeFacts(s).of(perm.node_id)),
            P.CanMint: self._can_mint,
            P.CanManageCredential: lambda p, perm, s: s.policy.can_revoke(
                p, s.issuer.credential_scope(perm.credential_id)),
            P.CanReadReaderItems: lambda p, perm, s: all(self._can_read_item(p, i, s) for i in perm.reader_ids),
            P.CanReadReference: lambda p, perm, s: self._can_read_reference(p, perm.reference_id, s),
            P.CanRenderCitation: lambda p, perm, s: self._can_read_reference(
                p, parse_citation(perm.citation).reference_id, s),
            P.CanSubmitUserQuote: lambda p, perm, s: s.policy.can_submit_user_quote(p),
            P.CanReviewProject: lambda p, perm, s: self._can_review(p, perm.project_id, s),
            P.CanReviewRecord: lambda p, perm, s: self._can_review(
                p, s.reviews.get(perm.review_id).project_id, s),
        }

    def check(self, principal, permission, services):
        if isinstance(permission, P.NoPrincipalNeeded):
            return
        if principal is None:
            raise Forbidden("authentication required")
        rule = self._rules.get(type(permission))
        if rule is None:
            raise TypeError(f"no rule for permission {permission!r}")
        if not rule(principal, permission, services):
            raise Forbidden(f"{principal.role} may not: {type(permission).__name__}")

    # rules needing more than one fact
    @staticmethod
    def _can_read_node(p, perm, s):
        facts = TreeFacts(s)
        ancestors = [facts.of_node(a) for a in s.tree.ancestors(perm.node_id)]
        return s.policy.can_read_node(p, facts.of(perm.node_id), ancestors)

    @staticmethod
    def _can_move(p, perm, s):
        facts = TreeFacts(s)
        if not s.policy.can_edit_node(p, facts.of(perm.node_id)):
            return False
        if perm.new_parent_id is None:            # becoming a project: admin only (no rule for parentless)
            return p.role == ADMIN
        return s.policy.can_edit_node(p, facts.of(perm.new_parent_id))

    @staticmethod
    def _can_assign(p, perm, s):
        node = TreeFacts(s).of(perm.node_id)
        return s.policy.can_assign(p, node) and s.policy.can_mint(
            p, CredentialScope("worker", node.project_id, node.node_id), "worker")

    @staticmethod
    def _can_mint(p, perm, s):
        if perm.project_id is not None:
            project = TreeFacts(s).of(perm.project_id)
            if project.project_id != perm.project_id:
                return False                      # project_id must name a project node
        if perm.scope_node_id is not None and (
                perm.project_id is None or TreeFacts(s).of(perm.scope_node_id).project_id != perm.project_id):
            return False                          # the scope node must sit in that project
        return s.policy.can_mint(p, CredentialScope(perm.role, perm.project_id, perm.scope_node_id), perm.role)

    def _can_read_item(self, p, reader_id, s) -> bool:
        try:
            entry = s.temp_cache.get(reader_id)
        except NotFound:
            return self._can_read_reference(p, reader_id, s)
        return s.policy.can_read_temp_entry(p, TempEntryFacts(entry.cache_id, entry.owner))

    @staticmethod
    def _can_review(p, project_id, s) -> bool:
        own_task = TreeFacts(s).of(p.scope_node_id) if p.role == WORKER and p.scope_node_id is not None else None
        return s.policy.can_review(p, project_id, own_task)

    @staticmethod
    def _holds_review_citing(p, reference_id, s) -> bool:
        """Build log #50: the review-task worker may read the content + quotes of a review it holds."""
        if p.role != WORKER or p.agent_id is None or p.project_id is None:
            return False
        for record in s.reviews.list(p.project_id, TAKEN):
            if record.reviewer != p.agent_id:
                continue
            if record.content_reference_id == reference_id or cites(
                    s.references.get(record.content_reference_id, follow_superseded=False).text, reference_id):
                return RequestAuthorizer._can_review(p, record.project_id, s)
        return False

    @staticmethod
    def _can_read_reference(p, reference_id, s) -> bool:
        ref = s.references.get(reference_id, follow_superseded=False)
        if p.agent_id is not None and ref.owner == p.agent_id:
            return True                           # the agent that cited it into references
        facts = TreeFacts(s)
        citing = [facts.of_node(node) for node in s.tree.citing_nodes(ref.id)]
        return s.policy.can_read_reference(p, ReferenceFacts(ref.id, ref.owner, ref.origin), citing) or \
            RequestAuthorizer._holds_review_citing(p, ref.id, s)
