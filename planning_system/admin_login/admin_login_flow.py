"""admin_login_flow: prompt -> api_client.start_admin_session -> token; retries a wrong password up to 3 times."""
from __future__ import annotations

from planning_system.api_client import PlanningApiClientInterface
from planning_system.contract import Forbidden

from .interface import AdminLoginInterface, PasswordPrompt
from .types import MAX_PASSWORD_ATTEMPTS, LoginCancelled, LoginFailed

FIRST_MESSAGE = "Planning admin password"
RETRY_MESSAGE = "Wrong password. Planning admin password"


class AdminLoginFlow(AdminLoginInterface):

    def __init__(self, api: PlanningApiClientInterface, prompt: PasswordPrompt):
        self._api = api
        self._prompt = prompt

    def login(self) -> str:
        message = FIRST_MESSAGE
        for _attempt in range(MAX_PASSWORD_ATTEMPTS):
            password = self._prompt.ask(message)
            if password is None:
                raise LoginCancelled("admin login cancelled")
            try:
                return self._api.start_admin_session(password)["token"]
            except Forbidden:
                message = RETRY_MESSAGE
            finally:
                password = None
        raise LoginFailed(f"wrong password {MAX_PASSWORD_ATTEMPTS} times")
