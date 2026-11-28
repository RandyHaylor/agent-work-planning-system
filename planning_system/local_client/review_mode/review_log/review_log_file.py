"""ReviewLogFile: the client's review log, one JSONL record per review attempt, one file per UTC day
(`<client home>/review-log/YYYY-MM-DD.jsonl`)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class ReviewLogFile:

    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def append(self, record: dict) -> Path:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{str(record.get('logged_at') or '')[:10] or 'undated'}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return path

    def recent(self, review_id: Optional[str] = None, last: int = 20) -> list[dict]:
        """The newest `last` records (oldest first), only that review's when review_id is given."""
        records = []
        for path in sorted(self._directory.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if review_id is None or record.get("review_id") == review_id:
                    records.append(record)
        return records[-last:] if last > 0 else records
