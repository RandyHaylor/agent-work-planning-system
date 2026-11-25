"""Test support: in-memory local cache, a mocked server, fake harness adapters and fake interfaces."""
import hashlib
import itertools
from datetime import datetime, timezone

from planning_system.contract import NotFound

from .interface import ExchangeCapture, ReferenceSync
from .ports import (ClientCredentialsPort, Clock, HarnessAdapterPort, LocalExchangeCachePort,
                    ServerReferencesPort)
from .types import KIND_PROMPT, KIND_QUESTION_ANSWER, Exchange


class FixedClock(Clock):
    def now(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class InMemoryExchangeCache(LocalExchangeCachePort):
    def __init__(self):
        self.rows: dict[str, Exchange] = {}

    def append(self, exchange):
        self.rows[exchange.local_id] = exchange

    def get(self, local_id):
        return self.rows.get(local_id)


class RecordingServer(ServerReferencesPort):
    """Mocked server: records every call (with the credential used); same content = same reference."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._by_hash: dict[str, str] = {}

    def store_user_exchange(self, credential, session_id, user_message, pre_text):
        self.calls.append((credential, session_id, user_message, pre_text))
        digest = hashlib.sha256(f"{pre_text}\n{user_message}".encode()).hexdigest()
        return self._by_hash.setdefault(digest, f"ref-{len(self._by_hash) + 1}")


class StaticCredentials(ClientCredentialsPort):
    def __init__(self, key="quote-key-1"):
        self.key = key

    def quote_key(self):
        return self.key


class ScriptedAdapter(HarnessAdapterPort):
    """A harness whose transcript holds the preceding agent output per session."""

    def __init__(self, session_id="s1"):
        self.session_id = session_id
        self.preceding: dict[str, str] = {}

    def get_current_session_id(self):
        return self.session_id

    def get_preceding_agent_output(self, session_id):
        return self.preceding.get(session_id, "")


class FakeExchangeCapture(ExchangeCapture):
    _ids = itertools.count(1)

    def __init__(self, adapter, cache, clock):
        self._adapter, self._cache, self._clock = adapter, cache, clock

    def _append(self, session_id, kind, user_message, pre_text):
        exchange = Exchange(f"local-{next(self._ids)}", session_id, kind, user_message, pre_text,
                            self._clock.now())
        self._cache.append(exchange)
        return exchange.local_id

    def capture_prompt(self, session_id, user_message):
        return self._append(session_id, KIND_PROMPT, user_message,
                            self._adapter.get_preceding_agent_output(session_id))

    def capture_question_answer(self, session_id, question, answer):
        return self._append(session_id, KIND_QUESTION_ANSWER, answer, question)

    def read(self, local_exchange_id):
        exchange = self._cache.get(local_exchange_id)
        if exchange is None:
            raise NotFound(local_exchange_id)
        return exchange


class FakeReferenceSync(ReferenceSync):
    def __init__(self, cache, server, credentials):
        self._cache, self._server, self._credentials = cache, server, credentials

    def sync(self, local_exchange_id):
        exchange = self._cache.get(local_exchange_id)
        if exchange is None:
            raise NotFound(local_exchange_id)
        return self._server.store_user_exchange(self._credentials.quote_key(), exchange.session_id,
                                                exchange.user_message, exchange.pre_text)
