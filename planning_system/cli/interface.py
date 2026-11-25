"""Public interface of cli."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Sequence, TextIO


class CommandLineInterface(ABC):

    @abstractmethod
    def run(self, argv: Sequence[str], environment: Mapping[str, str], stdout: TextIO, stderr: TextIO) -> int:
        """Parse argv -> one call -> print its JSON. Exit 0 ok, 1 server error (message on stderr), 2 usage."""
