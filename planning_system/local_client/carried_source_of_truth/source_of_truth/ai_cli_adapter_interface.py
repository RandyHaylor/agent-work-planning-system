"""Abstract interface that any AI-CLI adapter must implement.

The source-of-truth core depends only on this interface; concrete adapters
(e.g. Claude Code) implement it. This is what makes the system AI-CLI-portable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class PersistentReviewerSessionHandle(ABC):
    """Opaque handle to a long-lived reviewer subprocess/session."""

    @property
    @abstractmethod
    def session_id(self) -> str: ...

    @abstractmethod
    def send_prompt_and_await_response(self, prompt_text: str) -> str: ...

    @abstractmethod
    def is_alive(self) -> bool: ...

    @abstractmethod
    def terminate(self) -> None: ...


class AiCliAdapterInterface(ABC):
    @abstractmethod
    def get_current_session_id(self) -> str: ...

    @abstractmethod
    def register_user_prompt_submit_hook(
        self, hook_callable: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None: ...

    @abstractmethod
    def inject_into_next_user_turn(self, injection_text: str) -> None: ...

    @abstractmethod
    def inject_into_subagent_spawn(self, injection_text: str) -> None: ...

    @abstractmethod
    def spawn_persistent_reviewer_session(
        self,
        priming_prompt_text: str,
        allowed_read_paths: list[str],
        allowed_tool_names: list[str],
        reviewer_model_name: str,
        streaming_event_appender: Optional[Callable[[str, str], None]] = None,
    ) -> PersistentReviewerSessionHandle: ...
