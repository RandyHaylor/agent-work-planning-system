"""application: builds the FastAPI app: error mapping, the contract dependencies filled in, routers
mounted from config. Protocol only."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from fastapi import FastAPI

from planning_system.configuration import ConfigSection
from planning_system.server.commands.command_runner import CommandRunnerInterface
from planning_system.server.domain.authentication import CredentialAuthenticator

from . import dependencies
from .credential_dependency import principal_dependency
from .error_mapping import install_error_handlers
from .router_mounting import mount_routers, router_specs


def create_app(section: ConfigSection, runner: CommandRunnerInterface,
               authenticator: CredentialAuthenticator,
               extra_overrides: Optional[Mapping[Any, Any]] = None) -> FastAPI:
    """extra_overrides: further dependency overrides (e.g. dependencies.guidance_service)."""
    app = FastAPI(title="planning system")
    install_error_handlers(app)
    app.dependency_overrides[dependencies.current_principal] = principal_dependency(authenticator)
    app.dependency_overrides[dependencies.command_runner] = lambda: runner
    app.dependency_overrides.update(extra_overrides or {})
    mount_routers(app, router_specs(section))
    return app
