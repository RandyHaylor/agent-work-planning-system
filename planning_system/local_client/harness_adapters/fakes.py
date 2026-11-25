"""In-memory fake harness adapter: records every session, prompt and environment."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Optional

from .ai_cli_adapter_interface import AiCliAdapterInterface, PersistentReviewerSessionHandle
from .types import HeadlessSessionSpec

Reply = Callable[["FakeSessionHandle", str], str]


class FakeSessionHandle(PersistentReviewerSessionHandle):

    def __init__(self, session_id: str, reply: Reply, spec: Optional[HeadlessSessionSpec] = None,
                 release: Optional[threading.Event] = None):
        self._session_id = session_id
        self._reply = reply
        self._release = release
        self.spec = spec
        self.prompts: list[str] = []
        self.alive = True

    @property
    def session_id(self) -> str:
        return self._session_id

    def send_prompt_and_await_response(self, prompt_text: str) -> str:
        self.prompts.append(prompt_text)
        if self._release is not None:
            self._release.wait(timeout=5)
        return self._reply(self, prompt_text)

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.alive = False


class FakeAiCliAdapter(AiCliAdapterInterface):
    """reply(handle, prompt) -> text decides every answer (default "ok").
    release: if given, prompts block until it is set (to prove callers don't wait)."""

    def __init__(self, reply: Optional[Reply] = None, release: Optional[threading.Event] = None):
        self._reply = reply or (lambda handle, prompt: "ok")
        self._release = release
        self.sessions: list[FakeSessionHandle] = []
        self.injections: list[str] = []

    def get_current_session_id(self) -> str:
        return "fake-current-session"

    def register_user_prompt_submit_hook(self, hook_callable: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.hook = hook_callable

    def inject_into_next_user_turn(self, injection_text: str) -> None:
        self.injections.append(injection_text)

    def inject_into_subagent_spawn(self, injection_text: str) -> None:
        self.injections.append(injection_text)

    def spawn_persistent_reviewer_session(self, priming_prompt_text, allowed_read_paths, allowed_tool_names,
                                          reviewer_model_name, streaming_event_appender=None):
        handle = FakeSessionHandle(str(uuid.uuid4()), self._reply)
        handle.prompts.append(priming_prompt_text)
        self.sessions.append(handle)
        return handle

    def spawn_headless_session(self, spec: HeadlessSessionSpec) -> FakeSessionHandle:
        handle = FakeSessionHandle(spec.session_id, self._reply, spec, self._release)
        self.sessions.append(handle)
        return handle


class SecondFakeAiCliAdapter(FakeAiCliAdapter):
    """A distinct adapter class, to prove another harness (e.g. Codex) plugs in with no other change."""
