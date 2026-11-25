"""Quote key in a file (mode 0600) under the client's config dir."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .interface import ClientCredentialsInterface

QUOTE_KEY_FILE_NAME = "quote_key"
OWNER_ONLY = 0o600


class FileClientCredentials(ClientCredentialsInterface):

    def __init__(self, config_directory: Path):
        self._config_directory = Path(config_directory)

    @property
    def _key_file(self) -> Path:
        return self._config_directory / QUOTE_KEY_FILE_NAME

    def read_quote_key(self) -> Optional[str]:
        try:
            return self._key_file.read_text(encoding="utf-8").strip() or None
        except FileNotFoundError:
            return None

    def write_quote_key(self, token: str) -> None:
        self._config_directory.mkdir(parents=True, exist_ok=True)
        temporary = self._key_file.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, OWNER_ONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
        os.chmod(temporary, OWNER_ONLY)   # in case the file already existed with wider bits
        os.replace(temporary, self._key_file)
