"""client_credentials contract, on [fake, real]."""
from __future__ import annotations

import os
import stat

import pytest

from planning_system.local_client.client_credentials import FileClientCredentials
from planning_system.local_client.client_credentials.fakes import InMemoryClientCredentials

XFAIL_REAL = pytest.mark.xfail(strict=False, reason="level 7")


@pytest.fixture(params=[pytest.param(InMemoryClientCredentials, id="fake"),
                        pytest.param(FileClientCredentials, id="real", marks=XFAIL_REAL)])
def credentials_class(request):
    return request.param


def test_absent_key_reads_none(credentials_class, tmp_path):
    assert credentials_class(tmp_path).read_quote_key() is None


def test_write_then_read(credentials_class, tmp_path):
    credentials = credentials_class(tmp_path)
    credentials.write_quote_key("qk-1")
    assert credentials.read_quote_key() == "qk-1"


@XFAIL_REAL
def test_real_file_is_owner_only(tmp_path):
    FileClientCredentials(tmp_path).write_quote_key("qk-1")
    files = list(tmp_path.rglob("*"))
    assert files and all(stat.S_IMODE(os.stat(f).st_mode) == 0o600 for f in files if f.is_file())
