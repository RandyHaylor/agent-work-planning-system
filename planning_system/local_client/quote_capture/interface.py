"""Public interfaces of quote_capture: capture to the local cache; sync one exchange when referenced."""
from abc import ABC, abstractmethod

from .types import Exchange, LocalExchangeId, ReferenceId


class ExchangeCapture(ABC):
    """What the harness hooks call. Writes only to the local client cache; nothing is sent."""

    @abstractmethod
    def capture_prompt(self, session_id: str, user_message: str) -> LocalExchangeId:
        """Verbatim prompt; pre-text = the preceding agent output (also after an interrupted turn)."""

    @abstractmethod
    def capture_question_answer(self, session_id: str, question: str, answer: str) -> LocalExchangeId: ...

    @abstractmethod
    def read(self, local_exchange_id: LocalExchangeId) -> Exchange: ...


class ReferenceSync(ABC):
    @abstractmethod
    def sync(self, local_exchange_id: LocalExchangeId) -> ReferenceId:
        """Reads the exchange from the local cache and sends it to the server's store_user_exchange
        with the quote key; returns the server's reference id (same content = same reference)."""
