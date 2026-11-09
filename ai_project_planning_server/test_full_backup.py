"""Unit tests for full backup: retention rules and the encrypt/decrypt round trip. No database."""
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization

from ai_project_planning_server import full_backup as FB


def _ts(day: int, hour: int = 0, year: int = 2026, month: int = 1) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_retention_keeps_last_ten_task_backups():
    entries = [(_ts(1) + timedelta(minutes=i), i) for i in range(25)]  # 25 task backups, same day
    keep = FB.select_to_keep(entries)
    assert set(range(15, 25)) <= keep          # the 10 most recent task completions
    assert 0 in keep                            # oldest of the day, week, month
    assert not any(i in keep for i in range(1, 15))


def test_retention_keeps_oldest_per_day_week_month():
    entries = []
    for day in range(1, 32):                    # January 2026, three backups a day, manual ones
        for hour in (3, 12, 20):
            entries.append((_ts(day, hour), None))
    keep = FB.select_to_keep(entries)
    kept = sorted(entries[i][0] for i in keep)
    assert len(kept) == 31                      # exactly one per day
    assert all(t.hour == 3 for t in kept)       # the oldest that day


def test_retention_week_and_month_survive_when_days_are_sparse():
    entries = [(_ts(2, 1), 1), (_ts(2, 9), 2), (_ts(20, 1), 3), (_ts(20, 9), 4), (_ts(5, 1, month=2), 5)]
    keep = FB.select_to_keep(entries, keep_last_tasks=1)
    assert keep == {0, 2, 4}                    # oldest per day covers week and month too; last task is index 4


def test_retention_empty():
    assert FB.select_to_keep([]) == set()


def test_private_key_password_roundtrip():
    private_pem, public_pem = FB.generate_keypair()
    blob = FB.encrypt_private_key(private_pem, "correct horse battery")
    assert FB.decrypt_private_key(blob, "correct horse battery") == private_pem
    try:
        FB.decrypt_private_key(blob, "wrong")
        assert False, "wrong password must fail"
    except FB.FullBackupError:
        pass


def test_backup_file_roundtrip_and_tamper_detection():
    private_pem, public_pem = FB.generate_keypair()
    data = b"PGDMP" + bytes(range(256)) * 10
    blob = FB.encrypt_bytes(data, public_pem, task_node_id=42, timestamp="20260109T120000Z")
    header = FB.read_header(blob)
    assert header.task_node_id == 42 and header.timestamp == "20260109T120000Z" and header.version == 1
    key = serialization.load_pem_private_key(private_pem, password=None)
    got_header, got = FB.decrypt_bytes(blob, key)
    assert got == data and got_header == header
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    try:
        FB.decrypt_bytes(tampered, key)
        assert False, "tampering must be detected"
    except FB.FullBackupError:
        pass
    # the header is authenticated too
    nl = blob.index(b"\n", len(FB.MAGIC))
    forged = FB.MAGIC + blob[len(FB.MAGIC):nl].replace(b'"task_node_id": 42', b'"task_node_id": 43') + blob[nl:]
    try:
        FB.decrypt_bytes(forged, key)
        assert False, "header tampering must be detected"
    except FB.FullBackupError:
        pass


def test_apply_retention_spares_the_backup_just_written(tmp_path):
    older = tmp_path / FB.file_name("20260109T010000Z", 1)
    newer_manual = tmp_path / FB.file_name("20260109T120000Z", None)
    older.write_bytes(b"x")
    newer_manual.write_bytes(b"x")
    assert FB.apply_retention(tmp_path, just_written=newer_manual) == []
    assert FB.apply_retention(tmp_path) == [newer_manual]  # without protection the same-day manual one goes


def test_file_names_parse(tmp_path):
    p = tmp_path / FB.file_name("20260109T120000Z", 7)
    p.write_bytes(b"x")
    (tmp_path / FB.file_name("20260110T120000Z", None)).write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    files = FB.list_backups(tmp_path)
    assert [(b.task_node_id, b.timestamp.day) for b in files] == [(7, 9), (None, 10)]
