"""raw_input_log_writer: appends each exchange to the local client cache (as in SoT).

Carried from SoT raw_input_log_writer.py: pre-text is kept to its last PRE_TEXT_CAPTURE_CHAR_LIMIT characters
(SoT's default capture window). Local ids are short random hex (SoT counted entries in one JSON file; the
cache port here is append/get only).
"""
import uuid

from .ports import Clock, LocalExchangeCachePort
from .types import Exchange

PRE_TEXT_CAPTURE_CHAR_LIMIT = 2000
LOCAL_ID_LENGTH = 8


def truncate_pre_text_to_capture_limit(pre_text: str, capture_char_limit: int = PRE_TEXT_CAPTURE_CHAR_LIMIT) -> str:
    if len(pre_text) <= capture_char_limit:
        return pre_text
    return pre_text[-capture_char_limit:]


class RawInputLogWriter:
    def __init__(self, cache: LocalExchangeCachePort, clock: Clock):
        self._cache = cache
        self._clock = clock

    def append(self, session_id, kind, user_message, pre_text):
        """Returns the new local exchange id."""
        exchange = Exchange(local_id=self._new_local_id(), session_id=session_id, kind=kind,
                            user_message=user_message, pre_text=truncate_pre_text_to_capture_limit(pre_text),
                            captured_at=self._clock.now())
        self._cache.append(exchange)
        return exchange.local_id

    def _new_local_id(self) -> str:
        while True:
            local_id = uuid.uuid4().hex[:LOCAL_ID_LENGTH]
            if self._cache.get(local_id) is None:
                return local_id
