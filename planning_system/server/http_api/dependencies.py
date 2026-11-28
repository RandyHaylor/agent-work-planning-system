"""FastAPI dependencies every http_api router uses. Signatures are the contract;
the core server fills in the bodies.

- current_principal: reads the Bearer token, returns a Principal (raises Forbidden if unknown).
- command_runner: returns the CommandRunner; it owns the transaction
  (permission check -> transaction, read-only for reads -> run). Build log #13.
- guidance_service: returns prompt_builder's GuidanceService (guidance is read from files, log #25).
"""
from planning_system.contract import Principal


def current_principal() -> Principal:  # filled in by the core server
    raise NotImplementedError


def command_runner():  # -> planning_system.server.commands.CommandRunner; filled in by the core server
    raise NotImplementedError


def guidance_service():  # -> planning_system.prompt_builder GuidanceService; filled in by composition
    raise NotImplementedError
