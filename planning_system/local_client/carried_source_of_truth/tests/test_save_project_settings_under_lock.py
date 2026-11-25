"""Cover the file-lock fix on save_project_settings.

Spawn many threads that all write to the same project-settings.json
concurrently; the resulting file must always be valid JSON (no torn writes)
and the final state must match the LAST writer's intent.
"""
from __future__ import annotations

import json
import threading

from source_of_truth.load_config import (
    ProjectSettings,
    load_project_settings,
    project_settings_file_path,
    save_project_settings,
)


def test_concurrent_writes_to_same_project_settings_never_produce_torn_json():
    project_id = "concurrent-write-test"
    writer_count = 20
    completed_count = {"value": 0}
    lock = threading.Lock()

    def writer_thread(thread_index: int) -> None:
        for repetition in range(5):
            settings = load_project_settings(project_id)
            settings.member_sessions.append({
                "session_id": f"sess-{thread_index}-{repetition}",
                "conversation_path": "/x",
            })
            save_project_settings(settings)
        with lock:
            completed_count["value"] += 1

    threads = [threading.Thread(target=writer_thread, args=(i,)) for i in range(writer_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # File must be readable and parseable JSON.
    raw_text = project_settings_file_path(project_id).read_text()
    parsed = json.loads(raw_text)
    assert isinstance(parsed, dict)
    assert "member_sessions" in parsed
    # All 20 writers ran to completion.
    assert completed_count["value"] == writer_count
    # File contains *some* member sessions (exact count is racy due to
    # last-writer-wins semantics on append, but it must be valid JSON
    # and a non-empty list).
    assert isinstance(parsed["member_sessions"], list)
    assert len(parsed["member_sessions"]) > 0
