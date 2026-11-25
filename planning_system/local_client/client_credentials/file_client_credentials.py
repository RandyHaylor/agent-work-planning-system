"""Quote key in a file (mode 0600) under the client's config dir. Level 6 scaffold: hollow."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .interface import ClientCredentialsInterface

QUOTE_KEY_FILE_NAME = "quote_key"


class FileClientCredentials(ClientCredentialsInterface):

    def __init__(self, config_directory: Path):
        self._config_directory = config_directory

    def read_quote_key(self) -> Optional[str]:
        raise NotImplementedError("level 7")

    def write_quote_key(self, token: str) -> None:
        raise NotImplementedError("level 7")
