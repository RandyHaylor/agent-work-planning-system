"""Contract tests for quote_capture (spec: planning/05-spec-quote-capture.md); mocked server."""
import pytest

from planning_system.local_client.quote_capture.exchange_capture import ExchangeCaptureService
from planning_system.local_client.quote_capture.fakes import (FakeExchangeCapture,
                                                              FakeReferenceSync, FixedClock,
                                                              InMemoryExchangeCache,
                                                              RecordingServer, ScriptedAdapter,
                                                              StaticCredentials)
from planning_system.local_client.quote_capture.ports import HarnessAdapterPort
from planning_system.local_client.quote_capture.reference_sync import ReferenceSyncService



class Env:
    def __init__(self, kind, adapter=None):
        self.kind = kind
        self.cache = InMemoryExchangeCache()
        self.server = RecordingServer()
        self.credentials = StaticCredentials("quote-key-1")
        self.adapter = adapter or ScriptedAdapter()
        capture_cls = FakeExchangeCapture if kind == "fake" else ExchangeCaptureService
        sync_cls = FakeReferenceSync if kind == "fake" else ReferenceSyncService
        self.capture = capture_cls(self.adapter, self.cache, FixedClock())
        self.sync = sync_cls(self.cache, self.server, self.credentials)


@pytest.fixture(params=["fake", pytest.param("real")])
def kind(request):
    return request.param


@pytest.fixture
def env(kind):
    return Env(kind)


def test_1_prompt_captured_verbatim_with_pre_text_nothing_sent(env):
    env.adapter.preceding["s1"] = "Agent: shall I use Postgres?"
    prompt = "  yes, Postgres -- exactly as typed\n"
    exchange = env.capture.read(env.capture.capture_prompt("s1", prompt))
    assert exchange.user_message == prompt
    assert exchange.pre_text == "Agent: shall I use Postgres?"
    assert exchange.kind == "prompt"
    assert env.server.calls == []


def test_2_interrupted_turn_still_yields_pre_text(env):
    env.adapter.preceding["s1"] = "Agent: I was halfway through expla"   # partial, interrupted
    exchange = env.capture.read(env.capture.capture_prompt("s1", "stop, do X instead"))
    assert exchange.pre_text == "Agent: I was halfway through expla"


def test_3_question_dialog_answer_captured(env):
    local_id = env.capture.capture_question_answer("s1", "Which database?", "Postgres")
    exchange = env.capture.read(local_id)
    assert (exchange.kind, exchange.pre_text, exchange.user_message) == \
        ("question_answer", "Which database?", "Postgres")
    assert env.server.calls == []


def test_4_citing_syncs_exactly_that_exchange_with_quote_key(env):
    env.capture.capture_prompt("s1", "not this one")
    target = env.capture.capture_prompt("s1", "this one")
    ref_id = env.sync.sync(target)
    assert ref_id
    assert len(env.server.calls) == 1
    credential, session_id, user_message, _ = env.server.calls[0]
    assert (credential, session_id, user_message) == ("quote-key-1", "s1", "this one")


def test_5_syncing_twice_gives_the_same_reference(env):
    local_id = env.capture.capture_prompt("s1", "same")
    assert env.sync.sync(local_id) == env.sync.sync(local_id)


class OtherHarnessAdapter(HarnessAdapterPort):
    """A second harness (e.g. Codex later) implementing the same interface."""

    def get_current_session_id(self):
        return "codex-session"

    def get_preceding_agent_output(self, session_id):
        return f"output from {session_id}"


def test_6_second_adapter_swaps_in_unchanged(kind):
    env = Env(kind, adapter=OtherHarnessAdapter())
    sid = env.adapter.get_current_session_id()
    exchange = env.capture.read(env.capture.capture_prompt(sid, "hello"))
    assert exchange.pre_text == "output from codex-session"
    assert env.sync.sync(exchange.local_id)
