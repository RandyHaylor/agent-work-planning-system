"""FastAPI dependencies every module router uses. Signatures are the contract;
the core server fills in the bodies. Other modules import these names only.

- current_principal: reads the Bearer token, returns a Principal (raises Forbidden if unknown).
- command_runner: returns the CommandRunner; it owns the transaction
  (permission check -> transaction, read-only for reads -> run). Build log #13.
"""
from fastapi import Depends

from planning_system.contract import Principal


def current_principal() -> Principal:  # filled in by the core server
    raise NotImplementedError


def authenticated_principal(principal: Principal = Depends(current_principal)) -> Principal:
    """Override for a module router's own principal placeholder (e.g. prompt_builder's), so that
    module need not import the server: `overrides[module.current_principal] = authenticated_principal`."""
    return principal


def command_runner():  # -> planning_system.server.commands.CommandRunner; filled in by the core server
    raise NotImplementedError
