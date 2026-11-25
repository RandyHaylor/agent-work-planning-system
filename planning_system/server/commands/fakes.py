"""Test support for commands and their consumers.

- fake_services(): Services over the domain fakes and in-memory stores (one shared world).
- FixedServicesFactory: returns the same Services for any Stores.
- FakeRequestAuthorizer: a working authorizer over the fakes (facts from services, rules from policy).
- RecordingCommandRunner: records (command, principal); returns a set result or raises a set error.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from planning_system.contract import Forbidden, NotFound, Principal
from planning_system.server.domain.access.fakes import TablePermissionPolicy
from planning_system.server.domain.access.types import (CredentialScope, NodeFacts, ReferenceFacts,
                                                        TempEntryFacts)
from planning_system.server.domain.agent_registry.fakes import FakeAgentRegistry
from planning_system.server.domain.agent_registry.fakes import FakeClock as RegistryClock
from planning_system.server.domain.authentication.fakes import FakeAuthentication
from planning_system.server.domain.authentication.fakes import FakeClock as AuthClock
from planning_system.server.domain.context_assembly.fakes import FakeContextAssembler
from planning_system.server.domain.project_tree.fakes import FakeProjectTree, TickingClock
from planning_system.server.domain.references.fakes import FakeClock as ReferenceClock
from planning_system.server.domain.references.fakes import FakeReferenceLibrary, FakeTempCache
from planning_system.server.domain.task_assignment.fakes import FakeTaskAssigner
from planning_system.server.storage.fakes import in_memory_stores

from . import permissions as P
from .command_runner import CommandRunnerInterface
from .request_authorizer import RequestAuthorizerInterface
from .services import Services, ServicesFactory


def fake_services(stores=None) -> Services:
    stores = stores or in_memory_stores()
    policy = TablePermissionPolicy()
    references = FakeReferenceLibrary(stores.references)
    tree = FakeProjectTree(stores.tree, references, TickingClock())
    auth = FakeAuthentication(stores.credentials, policy, AuthClock())
    agents = FakeAgentRegistry(stores.agent_registry, RegistryClock())
    return Services(tree=tree, references=references,
                    temp_cache=FakeTempCache(stores.temp_cache, stores.references, ReferenceClock()),
                    context=FakeContextAssembler(tree, references), agents=agents, issuer=auth,
                    admin_sessions=auth, policy=policy,
                    task_assigner=FakeTaskAssigner(tree, auth, agents))


class FixedServicesFactory(ServicesFactory):
    def __init__(self, services: Services):
        self.services = services
        self.calls = 0

    def __call__(self, stores):
        self.calls += 1
        return self.services


def node_facts(services: Services, node_id: int) -> NodeFacts:
    node = services.tree.get(node_id)
    ancestors = services.tree.ancestors(node_id)
    project_id = ancestors[0].id if ancestors else node.id
    return NodeFacts(node.id, project_id, node.assignee)


class FakeRequestAuthorizer(RequestAuthorizerInterface):
    def check(self, principal, permission, services):
        if isinstance(permission, P.NoPrincipalNeeded):
            return
        if principal is None:
            raise Forbidden("authentication required")
        if not self._allowed(principal, permission, services):
            raise Forbidden(f"{principal.role} may not: {type(permission).__name__}")

    def _allowed(self, p: Principal, perm, s: Services) -> bool:
        policy = s.policy
        if isinstance(perm, P.Authenticated):
            return True
        if isinstance(perm, P.RoleIs):
            return p.role in perm.roles
        if isinstance(perm, P.CanReadNode):
            facts = node_facts(s, perm.node_id)
            return policy.can_read_node(p, facts, ())
        if isinstance(perm, P.CanCreateNode):
            return policy.can_create_node(p, node_facts(s, perm.parent_id))
        if isinstance(perm, P.CanEditNode):
            return policy.can_edit_node(p, node_facts(s, perm.node_id))
        if isinstance(perm, P.CanMoveNode):
            target_ok = perm.new_parent_id is None and p.role == "admin" or (
                perm.new_parent_id is not None and policy.can_edit_node(p, node_facts(s, perm.new_parent_id)))
            return policy.can_edit_node(p, node_facts(s, perm.node_id)) and target_ok
        if isinstance(perm, P.CanSetState):
            return policy.can_set_state(p, node_facts(s, perm.node_id), perm.new_state)
        if isinstance(perm, P.CanAssign):
            facts = node_facts(s, perm.node_id)
            return policy.can_assign(p, facts) and policy.can_mint(
                p, CredentialScope("worker", facts.project_id, facts.node_id), "worker")
        if isinstance(perm, P.CanCreateSupplementaryTask):
            return policy.can_create_supplementary_task(p, node_facts(s, perm.task_id))
        if isinstance(perm, P.CanAddContent):
            return policy.can_add_content(p, node_facts(s, perm.node_id))
        if isinstance(perm, P.CanMint):
            return policy.can_mint(p, CredentialScope(perm.role, perm.project_id, perm.scope_node_id), perm.role)
        if isinstance(perm, P.CanManageCredential):
            return p.role in ("admin", "planner")      # the issuer re-checks the credential's own scope
        if isinstance(perm, P.CanReadReaderItems):
            return all(self._can_read_item(p, item, s) for item in perm.reader_ids)
        if isinstance(perm, P.CanReadReference):
            return self._can_read_reference(p, perm.reference_id, s)
        if isinstance(perm, P.CanRenderCitation):
            return True                                 # no citation parser scaffolded yet (gap)
        if isinstance(perm, P.CanSubmitUserQuote):
            return policy.can_submit_user_quote(p)
        raise TypeError(f"unknown permission {perm!r}")

    def _can_read_item(self, p, reader_id, s) -> bool:
        try:
            entry = s.temp_cache.get(reader_id)
        except NotFound:
            return self._can_read_reference(p, reader_id, s)
        return s.policy.can_read_temp_entry(p, TempEntryFacts(entry.cache_id, entry.owner))

    def _can_read_reference(self, p, reference_id, s) -> bool:
        ref = s.references.get(reference_id, follow_superseded=False)
        # No domain query yet for "nodes citing this reference" (gap); the owner stands in for it.
        if p.agent_id is not None and ref.owner == p.agent_id:
            return True
        return s.policy.can_read_reference(p, ReferenceFacts(ref.id, ref.owner), ())


@dataclass
class RecordingCommandRunner(CommandRunnerInterface):
    result: Any = None
    error: Optional[BaseException] = None
    respond: Optional[Callable[[Any, Optional[Principal]], Any]] = None
    calls: list = field(default_factory=list)

    def run(self, command, principal):
        self.calls.append((command, principal))
        if self.error is not None:
            raise self.error
        if self.respond is not None:
            return self.respond(command, principal)
        return self.result

    @property
    def last(self):
        return self.calls[-1]
