"""services: Services, the domain facades built over the Stores of one transaction, and the factory
that builds the real ones (DomainServicesFactory) from the per-process pieces in DomainSettings."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from planning_system.server.domain.access.interface import PermissionPolicy
from planning_system.server.domain.access.permission_policy import RulePermissionPolicy
from planning_system.server.domain.agent_registry.interface import AgentRegistry
from planning_system.server.domain.agent_registry.registry import AgentRegistryService
from planning_system.server.domain.authentication.admin_session import AdminSessionService
from planning_system.server.domain.authentication.credential_issuer import CredentialIssuerService
from planning_system.server.domain.authentication.interface import AdminSessions, CredentialIssuer
from planning_system.server.domain.context_assembly.context_assembler import ContextAssemblerService
from planning_system.server.domain.context_assembly.interface import ContextAssembler
from planning_system.server.domain.project_tree.interface import ProjectTree
from planning_system.server.domain.project_tree.project_tree import ProjectTreeService
from planning_system.server.domain.references.ingestion import Ingestion
from planning_system.server.domain.references.interface import Reader, ReferenceLibrary, TempCache
from planning_system.server.domain.references.reader_service import ReaderService
from planning_system.server.domain.references.reference_library import ReferenceLibraryService
from planning_system.server.domain.references.temp_cache_lifecycle import TempCacheLifecycle
from planning_system.server.domain.task_assignment.interface import TaskAssigner
from planning_system.server.domain.task_assignment.task_assigner import TaskAssignerService
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
    reader: Optional[Reader] = None


class ServicesFactory(ABC):
    @abstractmethod
    def __call__(self, stores: Stores) -> Services: ...


class SystemClock:
    """now() in UTC; satisfies every domain module's Clock port (they all ask only now())."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DomainSettings:
    """Per-process pieces: config values, clock, policy, and the reader's collaborators
    (source fetcher, document extractor, quick-json-reader, fastReader scanner config)."""
    scanner_config: Mapping[str, Any]
    source_fetcher: Any = None
    document_extractor: Any = None
    json_reader: Any = None
    temp_cache_ttl: timedelta = timedelta(hours=72)
    admin_session_ttl: timedelta = timedelta(hours=8)
    clock: Any = field(default_factory=SystemClock)
    policy: PermissionPolicy = field(default_factory=RulePermissionPolicy)


class DomainServicesFactory(ServicesFactory):
    """Builds the real domain services over one transaction's stores."""

    def __init__(self, settings: DomainSettings):
        self._settings = settings

    def __call__(self, stores):
        s = self._settings
        temp_cache = TempCacheLifecycle(stores.temp_cache, stores.references, s.clock, s.temp_cache_ttl)
        ingestion = Ingestion(stores.references, s.source_fetcher, s.document_extractor, temp_cache)
        references = ReferenceLibraryService(stores.references, ingestion)
        tree = ProjectTreeService(stores.tree, references, s.clock)
        agents = AgentRegistryService(stores.agent_registry, s.clock)
        issuer = CredentialIssuerService(stores.credentials, s.policy)
        return Services(
            tree=tree, references=references, temp_cache=temp_cache,
            context=ContextAssemblerService(tree, references), agents=agents, issuer=issuer,
            admin_sessions=AdminSessionService(stores.credentials, s.clock, s.admin_session_ttl),
            policy=s.policy, task_assigner=TaskAssignerService(tree, issuer, agents),
            reader=ReaderService(temp_cache, references, ingestion, s.scanner_config, s.json_reader))
