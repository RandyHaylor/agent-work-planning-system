"""In-memory quote key store; counts reads so tests can prove who reads it."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .interface import ClientCredentialsInterface


class InMemoryClientCredentials(ClientCredentialsInterface):

    def __init__(self, config_directory: Optional[Path] = None, quote_key: Optional[str] = None):
        self._quote_key = quote_key
        self.reads = 0

    def read_quote_key(self) -> Optional[str]:
        self.reads += 1
        return self._quote_key

    def write_quote_key(self, token: str) -> None:
        self._quote_key = token
