"""pi: our tiny pi harness (`pi --mode rpc`, JSONL commands on stdin; modelled on Unharness's pi_harness.py)."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional, Sequence

from .prompted_backend import PromptedReviewerBackend

DEFAULT_PI_MODEL = "gemma4-31b-jang-q3:latest"


class PiBackend(PromptedReviewerBackend):
    name = "pi"

    def __init__(self, model: str = DEFAULT_PI_MODEL, pi_directory: Optional[Path] = None,
                 command: Optional[Sequence[str]] = None, timeout_seconds: float = 180.0,
                 extra_environment: Optional[Mapping[str, str]] = None):
        self._model = model
        self._pi_directory = pi_directory
        self._command = command
        self._timeout = timeout_seconds
        self._extra_environment = dict(extra_environment or {})

    @property
    def launch_command(self) -> list[str]:
        raise NotImplementedError

    @property
    def launch_environment(self) -> dict[str, str]:
        raise NotImplementedError

    def _ask(self, prompt: str) -> str:
        raise NotImplementedError
