from __future__ import annotations

import threading
import time

from source_of_truth.cross_platform_file_lock import acquire_exclusive_file_lock


def test_acquire_exclusive_file_lock_serializes_concurrent_writers(tmp_path):
    target_file_path = tmp_path / "shared_resource.json"
    target_file_path.write_text("[]")
    observed_overlap = {"value": False}
    currently_inside_lock_count = {"value": 0}

    def writer_thread_function():
        with acquire_exclusive_file_lock(target_file_path):
            currently_inside_lock_count["value"] += 1
            if currently_inside_lock_count["value"] > 1:
                observed_overlap["value"] = True
            time.sleep(0.05)
            currently_inside_lock_count["value"] -= 1

    threads = [threading.Thread(target=writer_thread_function) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert observed_overlap["value"] is False
