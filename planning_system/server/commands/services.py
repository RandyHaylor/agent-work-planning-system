"""services: Services, the domain facades (interfaces only) built over the Stores of one transaction,
and the ServicesFactory port. The real factory (DomainServicesFactory) is composition and lives in
planning_system/server/domain_wiring.py."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from planning_system.server.domain.access import PermissionPolicy
from planning_system.server.domain.agent_registry import AgentRegistry
from planning_system.server.domain.authentication import AdminSessions, CredentialIssuer
from planning_system.server.domain.citation_enforcement import CitationEnforcement
from planning_system.server.domain.content_review import ReviewLedger
from planning_system.server.domain.context_assembly import ContextAssembler
from planning_system.server.domain.project_tree import ProjectTree
from planning_system.server.domain.references import Reader, ReferenceLibrary, TempCache
from planning_system.server.domain.task_assignment import TaskAssigner
from planning_system.server.storage.storage import Stores


@dataclass(frozen=True)
class Services:
    tree: ProjectTree
    references: ReferenceLibrary
    temp_cache: TempCache
    context: ContextAssembler
    agents: AgentRegistry
    issuer: CredentialIssuer
    admin_sessions: AdminSessions
    policy: PermissionPolicy
    task_assigner: TaskAssigner
    enforcement: CitationEnforcement
    reviews: ReviewLedger
    reader: Optional[Reader] = None


class ServicesFactory(ABC):
    @abstractmethod
    def __call__(self, stores: Stores) -> Services: ...
