"""services: Services, the domain facades built over the Stores of one transaction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from planning_system.server.domain.access.interface import PermissionPolicy
from planning_system.server.domain.agent_registry.interface import AgentRegistry
from planning_system.server.domain.authentication.interface import AdminSessions, CredentialIssuer
from planning_system.server.domain.context_assembly.interface import ContextAssembler
from planning_system.server.domain.project_tree.interface import ProjectTree
from planning_system.server.domain.references.interface import ReferenceLibrary, TempCache
from planning_system.server.domain.task_assignment.interface import TaskAssigner
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
    # The fastReader / quick-json-reader / document_extraction views (spec: references-and-reader,
    # fastreader-adaptation) have no scaffolded interface yet; typed loosely until they do.
    reader: Optional[Any] = None


class ServicesFactory(ABC):
    @abstractmethod
    def __call__(self, stores: Stores) -> Services: ...


class DomainServicesFactory(ServicesFactory):
    """Builds the real domain services (ProjectTreeService, ReferenceLibraryService, ...) over stores.
    Holds the per-process pieces: config values, clock, policy, reader."""

    def __init__(self, settings: Any = None):
        self._settings = settings

    def __call__(self, stores):
        raise NotImplementedError("level 7")
