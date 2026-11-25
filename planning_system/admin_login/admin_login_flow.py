"""admin_login_flow: prompt -> api_client.start_admin_session -> token; retries a wrong password up to 3 times.

Level 6 scaffold: hollow.
"""
from __future__ import annotations

from planning_system.api_client import PlanningApiClientInterface

from .interface import AdminLoginInterface, PasswordPrompt


class AdminLoginFlow(AdminLoginInterface):

    def __init__(self, api: PlanningApiClientInterface, prompt: PasswordPrompt):
        self._api = api
        self._prompt = prompt

    def login(self) -> str:
        raise NotImplementedError("level 7")
