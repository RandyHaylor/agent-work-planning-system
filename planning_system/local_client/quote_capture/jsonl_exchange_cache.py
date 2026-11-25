"""jsonl_exchange_cache: the local client cache as one append-only JSON-lines file (one exchange per line).

Appends are single O_APPEND writes, so hooks firing in parallel sessions do not interleave lines.
"""
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .ports import LocalExchangeCachePort
from .types import Exchange


class JsonlExchangeCache(LocalExchangeCachePort):
    def __init__(self, cache_file: Path):
        self._cache_file = Path(cache_file)

    def append(self, exchange: Exchange) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        row = {**asdict(exchange), "captured_at": exchange.captured_at.isoformat()}
        line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
        descriptor = os.open(self._cache_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, line)
        finally:
            os.close(descriptor)

    def get(self, local_id) -> Optional[Exchange]:
        return next((e for e in self._all() if e.local_id == local_id), None)

    def recent(self, last: int) -> list[Exchange]:
        exchanges = self._all()
        return exchanges[-last:] if last > 0 else []

    def _all(self) -> list[Exchange]:
        try:
            lines = self._cache_file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        exchanges = []
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                row["captured_at"] = datetime.fromisoformat(row["captured_at"])
                exchanges.append(Exchange(**row))
            except (ValueError, TypeError, KeyError):
                continue   # a torn or foreign line never blocks reading the rest
        return exchanges
