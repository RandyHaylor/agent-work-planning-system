"""Fakes for admin_login."""
from __future__ import annotations

from typing import Iterable, Optional

from planning_system.api_client import PlanningApiClientInterface
from planning_system.contract import Forbidden

from .interface import AdminLoginInterface, PasswordPrompt
from .types import MAX_PASSWORD_ATTEMPTS, LoginCancelled, LoginFailed, NoDisplay


class FakePasswordPrompt(PasswordPrompt):
    """Answers from a script (None = cancel); display=False raises NoDisplay."""

    def __init__(self, answers: Iterable[Optional[str]] = (), display: bool = True):
        self._answers = list(answers)
        self._display = display
        self.asked: list[str] = []

    def ask(self, message: str) -> Optional[str]:
        if not self._display:
            raise NoDisplay("no display available for the admin password window")
        self.asked.append(message)
        return self._answers.pop(0)


class FakeAdminLoginFlow(AdminLoginInterface):

    def __init__(self, api: PlanningApiClientInterface, prompt: PasswordPrompt):
        self._api = api
        self._prompt = prompt

    def login(self) -> str:
        for _attempt in range(MAX_PASSWORD_ATTEMPTS):
            password = self._prompt.ask("Planning admin password")
            if password is None:
                raise LoginCancelled("admin login cancelled")
            try:
                return self._api.start_admin_session(password)["token"]
            except Forbidden:
                continue
        raise LoginFailed(f"wrong password {MAX_PASSWORD_ATTEMPTS} times")
