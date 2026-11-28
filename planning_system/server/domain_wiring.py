"""domain_wiring: builds the real domain services (DomainServicesFactory) over one transaction's Stores,
from the per-process pieces in DomainSettings. Composition, so it lives beside composition.py; the
command layer sees only `Services` (interfaces) and `ServicesFactory`."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from planning_system.document_extraction import DocumentExtractor
from planning_system.quick_json_reader import JsonReaderInterface
from planning_system.server.commands import Services, ServicesFactory
from planning_system.server.domain.access import PermissionPolicy, RulePermissionPolicy
from planning_system.server.domain.agent_registry import AgentRegistryService
from planning_system.server.domain.authentication import AdminSessionService, CredentialIssuerService
from planning_system.server.domain.citation_enforcement import CitationEnforcementService, ClaimPolicy
from planning_system.server.domain.content_review import DEFAULT_LEASE, ReviewLedgerService
from planning_system.server.domain.context_assembly import ContextAssemblerService
from planning_system.server.domain.project_tree import ProjectTreeService
from planning_system.server.domain.task_assignment import TaskAssignerService
from planning_system.server.domain.references import (Clock, Ingestion, ReaderService, ReferenceLibraryService,
                                                      SourceFetcher, TempCacheLifecycle)


class SystemClock:
    """now() in UTC; satisfies every domain module's Clock port (they all ask only now())."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DomainSettings:
    """Per-process pieces: config values, clock, policy, and the reader's collaborators
    (source fetcher, document extractor, quick-json-reader, fastReader scanner config)."""
    scanner_config: Mapping[str, Any]
    source_fetcher: Optional[SourceFetcher] = None
    document_extractor: Optional[DocumentExtractor] = None
    json_reader: Optional[JsonReaderInterface] = None
    temp_cache_ttl: timedelta = timedelta(hours=72)
    admin_session_ttl: timedelta = timedelta(hours=8)
    clock: Clock = field(default_factory=SystemClock)
    policy: PermissionPolicy = field(default_factory=RulePermissionPolicy)
    claim_policy: ClaimPolicy = field(default_factory=ClaimPolicy.default)
    review_lease: timedelta = DEFAULT_LEASE


class DomainServicesFactory(ServicesFactory):
    """Builds the real domain services over one transaction's stores."""

    def __init__(self, settings: DomainSettings):
        self._settings = settings

    def __call__(self, stores) -> Services:
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
            enforcement=CitationEnforcementService(references, s.claim_policy),
            reviews=ReviewLedgerService(stores.reviews, references, tree, s.clock, s.review_lease),
            reader=ReaderService(temp_cache, references, ingestion, s.scanner_config, s.json_reader))


__all__ = ["DomainServicesFactory", "DomainSettings", "SystemClock"]
