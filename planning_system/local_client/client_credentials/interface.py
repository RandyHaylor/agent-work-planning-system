"""client_credentials: the install's quote key (read only by quote_capture's ReferenceSync)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ClientCredentialsInterface(ABC):

    @abstractmethod
    def read_quote_key(self) -> Optional[str]:
        """The stored quote key, or None if this install has none."""

    @abstractmethod
    def write_quote_key(self, token: str) -> None:
        """Stores the quote key (file mode 0600 under the client's config dir)."""
