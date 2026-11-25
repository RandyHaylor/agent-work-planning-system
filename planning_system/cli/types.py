"""cli types (spec: planning/05-spec-cli.md)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from planning_system.admin_login import AdminLoginInterface
from planning_system.api_client import ClientSettings, PlanningApiClientInterface
from planning_system.local_client import LocalClientInterface

EXIT_OK = 0
EXIT_SERVER_ERROR = 1
EXIT_USAGE = 2

# Where a command's one call goes.
TARGET_API = "api"                 # one PlanningApiClient method
TARGET_LOCAL = "local"             # one LocalClient method
TARGET_LOGIN = "login"             # admin_login popup -> prints PLANNING_TOKEN=...
TARGET_HELP = "help"               # fastReader-style help text
TARGET_GUIDANCE_EDITOR = "guidance_editor"   # launches prompt_builder's website locally


@dataclass(frozen=True)
class Arg:
    """One argparse argument. name starting with '--' is an option, otherwise positional.
    kind: str | int | ints (1+) | strs (0+) | flag | remainder."""
    name: str
    dest: str
    kind: str = "str"
    required: bool = False
    default: Any = None
    help: str = ""


@dataclass(frozen=True)
class CommandSpec:
    """One line of the spec's command list: words -> one call. `mapper` names an argument mapper for the few
    commands whose arguments are not passed straight through (e.g. load URL|FILE)."""
    words: tuple[str, ...]
    target: str
    method: Optional[str] = None
    arguments: tuple[Arg, ...] = ()
    fixed: Mapping[str, Any] = field(default_factory=dict)
    mapper: Optional[str] = None
    authenticated: bool = True
    help: str = ""


@dataclass(frozen=True)
class CliDependencies:
    """Everything the cli calls, injected so tests use fakes."""
    api_factory: Callable[[ClientSettings], PlanningApiClientInterface]
    local_client_factory: Callable[[ClientSettings], LocalClientInterface]
    admin_login_factory: Callable[[PlanningApiClientInterface], AdminLoginInterface]
    settings_from_environment: Callable[[Mapping[str, str]], ClientSettings]
    launch_guidance_editor: Callable[[], None]
