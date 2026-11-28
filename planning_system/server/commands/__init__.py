"""commands: every action, reads and writes (spec: 05-spec-commands.md).

Public: CommandRunner, Command / ReadCommand / WriteCommand, Access, Services, every command class
(see catalog.ROUTES for the route table).
"""
from .catalog import CORE_ROUTES, REFERENCE_ROUTES, ROUTES
from .command import Access, Command, ReadCommand, WriteCommand
from .command_runner import CommandRunner, CommandRunnerInterface
from .request_authorizer import RequestAuthorizer, RequestAuthorizerInterface
from .services import Services, ServicesFactory

__all__ = ["Access", "CORE_ROUTES", "Command", "CommandRunner", "CommandRunnerInterface",
           "REFERENCE_ROUTES", "ROUTES", "ReadCommand", "RequestAuthorizer",
           "RequestAuthorizerInterface", "Services", "ServicesFactory", "WriteCommand"]

globals().update({cls.__name__: cls for cls in ROUTES.values()})
__all__ += sorted(cls.__name__ for cls in ROUTES.values())
