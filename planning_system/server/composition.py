"""The server's own composition root (not main): from its config section it builds storage, domain
services, CommandRunner, FastAPI app and bootstrap, and offers the commands `run`, `bootstrap` and
`set-admin-password`. Named in config/server.json as the server component's factory.

Config keys read here (each child section goes to the module that owns it): storage, http_api,
authentication.admin_session_hours, references.temp_cache_ttl_hours, citation_enforcement.claim_policy,
content_review.lease_minutes, source_fetching,
document_extraction, quick_json_reader, prompt_builder.store_folder (all optional except storage)."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI

from planning_system.configuration import ConfigSection
from planning_system.document_extraction import build_document_extractor
from planning_system.fastreader.cli import DEFAULT_CONFIG_PATH as SCANNER_CONFIG_PATH
from planning_system.fastreader.scanner import load_config
from planning_system.prompt_builder.ai_prompt_builder.rule_catalog import RuleCatalog
from planning_system.prompt_builder.role_guidance import GuidanceComposer, RolePresetMap, SessionInjections
from planning_system.quick_json_reader import build_json_reader
from planning_system.server.adapters.http_source_fetcher import (HttpFetchSettings, HttpSourceFetcher,
                                                                 build_http_client)
from planning_system.server.adapters.uploaded_file_source import UploadedFileSource
from planning_system.server.adapters.web_search_source import WebSearchSource
from planning_system.server.commands import CommandRunner, RequestAuthorizer
from planning_system.server.domain_wiring import DomainServicesFactory, DomainSettings
from planning_system.server.domain.citation_enforcement import ClaimPolicy
from planning_system.server.domain.authentication import CredentialAuthenticatorService
from planning_system.server.domain.authentication import CredentialAuthenticator
from planning_system.server.domain.references import (SourceFetcher, UploadRequest, UrlRequest,
                                                      WebSearchRequest)
from planning_system.server.domain.references import TempCacheLifecycle
from planning_system.server.http_api import create_app, serve
from planning_system.server.http_api import dependencies as http_dependencies


class SourceFetcherByRequest(SourceFetcher):
    """One SourceFetcher for Ingestion: hands each request to the adapter for its kind."""

    def __init__(self, by_type: dict[type, SourceFetcher]):
        self._by_type = dict(by_type)

    def fetch(self, request):
        return self._by_type[type(request)].fetch(request)


def default_source_fetcher(section: ConfigSection) -> SourceFetcher:
    settings = HttpFetchSettings.from_config(section.as_dict())
    http = HttpSourceFetcher(build_http_client(settings), settings.max_bytes)
    return SourceFetcherByRequest({UrlRequest: http, UploadRequest: UploadedFileSource(settings.max_bytes),
                                   WebSearchRequest: WebSearchSource(http)})


class TransactionalAuthenticator(CredentialAuthenticator):
    """Authenticates a Bearer token in its own read-only transaction (it runs before the command's)."""

    def __init__(self, storage, clock):
        self._storage, self._clock = storage, clock

    def authenticate(self, presented_token):
        with self._storage.transactions.read_only() as conn:
            credentials = self._storage.stores_for(conn).credentials
            return CredentialAuthenticatorService(credentials, self._clock).authenticate(presented_token)


def _child(section: ConfigSection, name: str) -> ConfigSection:
    return section.child(name) if section.has(name) else ConfigSection(name, {})


def domain_settings(section: ConfigSection, source_fetcher: Optional[SourceFetcher] = None) -> DomainSettings:
    """The per-process pieces from config; `source_fetcher` replaces the network adapters (tests)."""
    references = _child(section, "references")
    authentication = _child(section, "authentication")
    content_review = _child(section, "content_review")
    return DomainSettings(
        claim_policy=ClaimPolicy.from_mapping(_child(section, "citation_enforcement").get("claim_policy", None)),
        review_lease=timedelta(minutes=float(content_review.get("lease_minutes", 10))),
        scanner_config=load_config(SCANNER_CONFIG_PATH),
        source_fetcher=source_fetcher or default_source_fetcher(_child(section, "source_fetching")),
        document_extractor=build_document_extractor(_child(section, "document_extraction").as_dict()),
        json_reader=build_json_reader(_child(section, "quick_json_reader").as_dict()),
        temp_cache_ttl=timedelta(hours=float(references.get("temp_cache_ttl_hours", 72))),
        admin_session_ttl=timedelta(hours=float(authentication.get("admin_session_hours", 8))))


def guidance_service_factory(section: ConfigSection) -> Callable[[], GuidanceComposer]:
    store_folder = _child(section, "prompt_builder").get("store_folder", None)
    catalog = RuleCatalog(user_folder=Path(store_folder)) if store_folder else RuleCatalog()
    composer = GuidanceComposer(catalog, RolePresetMap(), SessionInjections())
    return lambda: composer


def build_app(section: ConfigSection, storage, settings: DomainSettings) -> FastAPI:
    """storage: anything with `transactions` and `stores_for(conn)` (Storage, or the in-memory one)."""
    runner = CommandRunner(storage.transactions, storage.stores_for, DomainServicesFactory(settings),
                           RequestAuthorizer())
    return create_app(_child(section, "http_api"), runner, TransactionalAuthenticator(storage, settings.clock),
                      {http_dependencies.guidance_service: guidance_service_factory(section)})


def purge_expired_temp_cache(storage, settings: DomainSettings) -> int:
    """Temp cache TTL purge at server start (build log #17)."""
    with storage.transactions.read_write() as conn:
        stores = storage.stores_for(conn)
        return TempCacheLifecycle(stores.temp_cache, stores.references, settings.clock,
                                  settings.temp_cache_ttl).purge_expired()


class ServerComponent:
    def __init__(self, section: ConfigSection):
        self._section = section

    def commands(self) -> dict[str, Callable[[list[str]], int]]:
        return {"run": self.run, "bootstrap": self.bootstrap,
                "set-admin-password": self.set_admin_password}

    def run(self, args: list[str]) -> int:
        """purge expired temp cache (log #17) -> create_storage -> DomainServicesFactory ->
        CommandRunner -> create_app (with guidance_service override) -> serve."""
        from planning_system.server.storage import create_storage
        storage = create_storage(self._section.child("storage"))
        settings = domain_settings(self._section)
        purged = purge_expired_temp_cache(storage, settings)
        print(f"temp cache: purged {purged} expired item(s)", file=sys.stderr)
        serve(build_app(self._section, storage, settings), _child(self._section, "http_api"))
        return 0

    def bootstrap(self, args: list[str]) -> int:
        """Bootstrapper(storage, PostgresDatabaseSetup, PasswordHashSetup, TerminalPasswordPrompt)."""
        from planning_system.server.bootstrap.commands import bootstrap_command
        return bootstrap_command(self._section.child("storage"))

    def set_admin_password(self, args: list[str]) -> int:
        from planning_system.server.bootstrap.commands import set_admin_password_command
        return set_admin_password_command(self._section.child("storage"))


def create_server(section: ConfigSection) -> ServerComponent:
    return ServerComponent(section)


__all__ = ["ServerComponent", "SourceFetcherByRequest", "TransactionalAuthenticator", "build_app",
           "create_server", "domain_settings", "purge_expired_temp_cache"]
