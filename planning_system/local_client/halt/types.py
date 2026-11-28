"""halt types: the refusal a halted client raises, and one line of a halt report."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from planning_system.errors import Halted

TERMINATED = "terminated"        # gone after SIGTERM
KILLED = "killed"                # still there after the grace period: SIGKILL
ALREADY_GONE = "already_gone"    # nothing to signal
NO_PID = "no_pid"                # recorded without a pid (nothing to kill)


class ClientHalted(Halted):
    """This client is halted (`planning halt`); nothing new starts until `planning resume`."""

    def __init__(self, detail: str = ""):
        super().__init__("this client is halted (`planning halt`); run `planning resume` to allow new sessions"
                         + (f": {detail}" if detail else ""))


@dataclass(frozen=True)
class KilledSession:
    agent_id: str
    kind: str
    pid: Optional[int]
    outcome: str
