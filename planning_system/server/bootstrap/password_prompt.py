"""password_prompt: carried read_password. PLANNING_ADMIN_PASSWORD overrides (with a warning); else
getpass twice with the policy check and the carried "SAVE THIS PASSWORD" warning."""
from __future__ import annotations

import getpass
import os
import sys
from typing import Callable, Mapping, Optional, TextIO

from planning_system.contract import Invalid

from .ports import PasswordPrompt

ENV_OVERRIDE = "PLANNING_ADMIN_PASSWORD"
MIN_PASSWORD_LEN = 8

PASSWORD_WARNING = """
==================================================================
  WARNING: SAVE THIS PASSWORD SOMEWHERE SECURE. DO NOT FORGET IT.

  It is the only way to act as admin on this server. It is stored
  only as a hash and cannot be recovered or reset without it.
==================================================================
"""


def check_password_policy(password: str) -> Optional[str]:
    if len(password) < MIN_PASSWORD_LEN:
        return f"password must be at least {MIN_PASSWORD_LEN} characters"
    return None


class TerminalPasswordPrompt(PasswordPrompt):
    def __init__(self, environ: Optional[Mapping[str, str]] = None,
                 read_secret: Callable[[str], str] = getpass.getpass,
                 out: TextIO = sys.stdout, err: TextIO = sys.stderr):
        self._environ = os.environ if environ is None else environ
        self._read, self._out, self._err = read_secret, out, err

    def ask(self, purpose="Admin password"):
        override = self._environ.get(ENV_OVERRIDE)
        if override is not None:
            print(f"warning: admin password taken from {ENV_OVERRIDE} (non-interactive)", file=self._err)
            problem = check_password_policy(override)
            if problem:
                raise Invalid(problem)
            return override
        print(PASSWORD_WARNING, file=self._out)
        while True:
            password = self._read(f"{purpose} (min {MIN_PASSWORD_LEN} chars): ")
            problem = check_password_policy(password)
            if problem:
                print(problem, file=self._out)
                continue
            if self._read("Repeat: ") != password:
                print("passwords do not match", file=self._out)
                continue
            return password
