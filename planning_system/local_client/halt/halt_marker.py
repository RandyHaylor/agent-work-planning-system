"""HaltMarker: a file under the client home; while it exists this client starts nothing (build log #68)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .types import ClientHalted


class HaltMarker:

    def __init__(self, marker_file: Path):
        self._marker_file = Path(marker_file)

    def set(self) -> None:
        self._marker_file.parent.mkdir(parents=True, exist_ok=True)
        self._marker_file.write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")

    def clear(self) -> bool:
        """True when the client was halted."""
        try:
            self._marker_file.unlink()
        except FileNotFoundError:
            return False
        return True

    def is_set(self) -> bool:
        return self._marker_file.exists()

    def ensure_not_halted(self) -> None:
        try:
            since = self._marker_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return
        raise ClientHalted(f"halted since {since}")
