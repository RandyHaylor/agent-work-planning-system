"""ProcessKiller: SIGTERM to every target at once, wait a short grace, SIGKILL whatever is left. A target is a
whole process group (pid = group id) or a single pid. Does not wait for anything to finish its work."""
from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .types import ALREADY_GONE, KILLED, NO_PID, TERMINATED

DEFAULT_GRACE_SECONDS = 3.0
POLL_SECONDS = 0.05


@dataclass(frozen=True)
class KillTarget:
    pid: Optional[int]
    process_group: bool


class ProcessKiller:

    def __init__(self, grace_seconds: float = DEFAULT_GRACE_SECONDS, clock: Callable[[], float] = time.monotonic):
        self._grace_seconds = grace_seconds
        self._clock = clock

    def kill_all(self, targets: Sequence[KillTarget]) -> list[str]:
        """One outcome per target, in order."""
        outcomes: list[Optional[str]] = []
        for target in targets:
            if target.pid is None:
                outcomes.append(NO_PID)
            elif not self._signal(target, signal.SIGTERM):
                outcomes.append(ALREADY_GONE)
            else:
                outcomes.append(None)
        deadline = self._clock() + self._grace_seconds
        while self._clock() < deadline and any(o is None and _alive(t) for o, t in zip(outcomes, targets)):
            time.sleep(POLL_SECONDS)
        return [outcome or (KILLED if _alive(target) and self._signal(target, _SIGKILL) else TERMINATED)
                for outcome, target in zip(outcomes, targets)]

    @staticmethod
    def _signal(target: KillTarget, number: int) -> bool:
        """False when there was nothing to signal."""
        try:
            if target.process_group and hasattr(os, "killpg"):
                os.killpg(target.pid, number)
            else:
                os.kill(target.pid, number)
        except ProcessLookupError:
            return False
        except PermissionError:
            return False
        return True


_SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)


def _alive(target: KillTarget) -> bool:
    """A live (non-zombie) process is the target pid or, for a group, any member of the group. Linux reads /proc so
    exited-but-unreaped members (zombies) do not count; elsewhere a signal-0 probe."""
    if Path("/proc/self/stat").exists():
        return any(True for _ in live_members(target.pid)) if target.process_group else _live_pid(target.pid)
    try:
        if target.process_group and hasattr(os, "killpg"):
            os.killpg(target.pid, 0)
        else:
            os.kill(target.pid, 0)
    except OSError:
        return False
    return True


def live_members(process_group: int):
    """pids of non-zombie processes in the group (Linux /proc)."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        stat = _stat_fields(entry)
        if stat is not None and stat[2] != "Z" and int(stat[4]) == process_group:
            yield int(entry.name)


def _live_pid(pid: int) -> bool:
    stat = _stat_fields(Path("/proc") / str(pid))
    return stat is not None and stat[2] != "Z"


def _stat_fields(entry: Path) -> Optional[list[str]]:
    """/proc/<pid>/stat split after the command name (which may hold spaces): [pid, comm, state, ppid, pgrp, ...]."""
    try:
        text = (entry / "stat").read_text()
    except OSError:
        return None
    head, _, tail = text.rpartition(")")
    pid, _, comm = head.partition(" (")
    return [pid, comm, *tail.split()]
