"""Context-manager file lock that works on Linux/macOS (fcntl) and Windows (msvcrt)."""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_IS_WINDOWS = sys.platform.startswith("win")

if _IS_WINDOWS:
    import msvcrt
else:
    import fcntl


@contextmanager
def acquire_exclusive_file_lock(
    target_file_path: str | Path,
    poll_interval_seconds: float = 0.05,
    max_wait_seconds: float = 30.0,
) -> Iterator[None]:
    """Acquire an OS-level exclusive lock on a sibling .lock file. Creates parent dirs."""
    target_path = Path(target_file_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    lock_file_descriptor = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + max_wait_seconds
    try:
        while True:
            try:
                if _IS_WINDOWS:
                    msvcrt.locking(lock_file_descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(lock_file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Could not acquire lock on {lock_path} within {max_wait_seconds}s"
                    )
                time.sleep(poll_interval_seconds)
        try:
            yield
        finally:
            if _IS_WINDOWS:
                try:
                    msvcrt.locking(lock_file_descriptor, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                fcntl.flock(lock_file_descriptor, fcntl.LOCK_UN)
    finally:
        os.close(lock_file_descriptor)
