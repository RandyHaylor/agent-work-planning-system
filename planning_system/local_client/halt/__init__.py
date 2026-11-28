"""halt: stop everything this client started, now (build log #68). Public: SessionHalter (`planning halt` /
`planning resume`), ClientSessionTracker (registers review loops and reviewer processes; refuses new starts while
halted), HaltMarker, ProcessKiller, ClientHalted, client_session_control (wiring under the client home)."""
from __future__ import annotations

from ..client_paths import ClientPaths
from ..task_runner import RunningSessionsRegistry
from .halt_marker import HaltMarker
from .process_killer import KillTarget, ProcessKiller, live_members
from .session_halter import SessionHalter
from .session_tracker import ClientSessionTracker
from .types import ALREADY_GONE, KILLED, NO_PID, TERMINATED, ClientHalted, KilledSession


def client_session_control(paths: ClientPaths) -> tuple[ClientSessionTracker, SessionHalter]:
    """The tracker and halter over this install's registry and halt marker."""
    registry = RunningSessionsRegistry(paths.running_sessions_file)
    marker = HaltMarker(paths.halt_marker_file)
    return ClientSessionTracker(registry, marker), SessionHalter(registry, marker)


__all__ = ["ALREADY_GONE", "ClientHalted", "ClientSessionTracker", "HaltMarker", "KILLED", "KillTarget",
           "KilledSession", "NO_PID", "ProcessKiller", "SessionHalter", "TERMINATED", "client_session_control",
           "live_members"]
