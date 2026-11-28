"""StreamDeadlineWatch: the reviewer wait loop's deadline and heartbeat, on a fake clock (no subprocess)."""
from planning_system.local_client.harness_adapters.claude_code.ai_cli_adapter_claude_code import (
    StreamDeadlineWatch,
)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_expires_only_after_the_timeout():
    clock = FakeClock()
    watch = StreamDeadlineWatch(10, 3, clock)
    clock.now = 110.0
    assert not watch.expired()
    clock.now = 110.1
    assert watch.expired()


def test_heartbeat_after_silence_then_rescheduled():
    clock = FakeClock()
    watch = StreamDeadlineWatch(10, 3, clock)
    clock.now = 103.0
    assert watch.heartbeat_message() is None
    clock.now = 103.5
    assert watch.heartbeat_message() == "no stream events for 3.5s (timeout in 6.5s)"
    assert watch.heartbeat_message() is None
    clock.now = 106.6
    assert watch.heartbeat_message() == "no stream events for 6.6s (timeout in 3.4s)"


def test_an_event_resets_the_silence():
    clock = FakeClock()
    watch = StreamDeadlineWatch(10, 3, clock)
    clock.now = 102.0
    watch.event_arrived()
    clock.now = 105.0
    assert watch.heartbeat_message() is None
    clock.now = 105.5
    assert watch.heartbeat_message() == "no stream events for 3.5s (timeout in 4.5s)"
